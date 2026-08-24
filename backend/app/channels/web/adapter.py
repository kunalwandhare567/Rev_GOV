"""
Phase 2 — Web Channel Adapter
Normalizes web portal form submissions into the standard ChannelMessage format.
Handles session-based citizens (JWT), multi-step form submissions, and file uploads.
"""
from typing import Optional, Dict, Any
from app.channels.base import (
    ChannelAdapter, ChannelMessage, ChannelResponse, Channel, MessageType, EventType
)


class WebAdapter(ChannelAdapter):
    """
    Web Portal channel adapter.
    Handles form-based multi-step application submission.
    """

    channel = Channel.WEB

    def normalize_inbound(self, raw: Dict[str, Any]) -> ChannelMessage:
        """
        Normalize a web portal request into a ChannelMessage.

        Expected raw keys:
          - citizen_ref: str (from session/JWT)
          - text: str (free text from chat box or step notes)
          - action: str (e.g., 'SUBMIT_STEP', 'UPLOAD_DOC', 'SELECT_SERVICE')
          - step_data: dict (form field values for this step)
          - file_refs: list[str] (uploaded file paths)
          - language: str
        """
        citizen_ref = raw.get("citizen_ref") or raw.get("citizen_identifier", "")
        text = raw.get("text") or raw.get("message") or ""
        action = raw.get("action", "TEXT")
        step_data = raw.get("step_data") or {}
        file_refs = raw.get("file_refs") or []
        language = raw.get("language", "en")

        # Build enriched text if step_data provided
        if step_data and not text:
            text = f"[FORM_STEP] {action}: {step_data}"

        msg_type = MessageType.TEXT
        if file_refs:
            msg_type = MessageType.DOCUMENT
        elif action == "UPLOAD_DOC":
            msg_type = MessageType.DOCUMENT

        return ChannelMessage(
            citizen_identifier=citizen_ref,
            channel=Channel.WEB.value,
            message_type=msg_type.value,
            text_content=text,
            language=language,
            metadata={
                "action": action,
                "step_data": step_data,
                "file_refs": file_refs,
                "source": "WEB_PORTAL",
            },
        )

    def format_outbound(self, response: ChannelResponse) -> Dict[str, Any]:
        """
        Format orchestrator response for the web portal frontend.
        Web supports rich HTML, progress bars, and multi-field forms.
        """
        return {
            "message": response.text_content,
            "options": response.quick_replies or [],
            "form_fields": response.metadata.get("form_fields", []),
            "next_step": response.metadata.get("next_step"),
            "tracking_id": response.metadata.get("tracking_id"),
            "application_id": response.metadata.get("application_id"),
            "progress_percent": response.metadata.get("progress_percent", 0),
            "status": response.metadata.get("status"),
            "requires_upload": response.metadata.get("requires_upload", False),
            "requires_payment": response.metadata.get("requires_payment", False),
            "channel": "WEB",
        }

    def can_handle_voice(self) -> bool:
        return False  # Web uses text; IVR handles voice

    def can_handle_documents(self) -> bool:
        return True

    def max_message_length(self) -> int:
        return 10_000  # Web has no practical limit
