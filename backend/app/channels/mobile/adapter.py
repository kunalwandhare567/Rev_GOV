"""
Phase 2 — Mobile Channel Adapter
Handles mobile app (Android/iOS PWA) API requests.
Similar to web but optimized for:
  - Smaller payloads (mobile bandwidth)
  - Push notification hooks
  - Offline-first sync (partial submissions)
  - Voice-first interaction (uses STT)
"""
from typing import Optional, Dict, Any
from app.channels.base import (
    ChannelAdapter, ChannelMessage, ChannelResponse, Channel, MessageType, EventType
)


class MobileAdapter(ChannelAdapter):
    """
    Mobile App / PWA channel adapter.
    Supports offline sync, push notifications, and compact responses.
    """

    channel = Channel.MOBILE

    def normalize_inbound(self, raw: Dict[str, Any]) -> ChannelMessage:
        """
        Normalize a mobile app request into a ChannelMessage.

        Expected raw keys:
          - device_id: str (unique device identifier)
          - citizen_ref: str (from stored session)
          - text: str
          - voice_transcript: str (pre-transcribed by on-device STT)
          - action: str
          - fields: dict (partial form fields from mobile form)
          - offline_payload: dict (queued-while-offline submissions)
          - language: str
          - push_token: str (Firebase/APNS for push notifications)
        """
        citizen_ref = raw.get("citizen_ref") or raw.get("device_id", "")
        text = raw.get("text") or raw.get("voice_transcript") or ""
        language = raw.get("language", "en")
        fields = raw.get("fields") or {}
        offline_payload = raw.get("offline_payload")

        # Handle offline sync payload
        if offline_payload and not text:
            text = f"[OFFLINE_SYNC] {offline_payload}"

        # Handle partial form fields
        if fields and not text:
            text = f"[MOBILE_FORM] {fields}"

        msg_type = MessageType.TEXT
        if raw.get("doc_base64") or raw.get("file_ref"):
            msg_type = MessageType.DOCUMENT
        elif raw.get("voice_transcript"):
            msg_type = MessageType.VOICE

        return ChannelMessage(
            citizen_identifier=citizen_ref,
            channel=Channel.MOBILE.value,
            message_type=msg_type.value,
            text_content=text,
            language=language,
            metadata={
                "device_id": raw.get("device_id"),
                "push_token": raw.get("push_token"),
                "fields": fields,
                "offline_payload": offline_payload,
                "app_version": raw.get("app_version", "1.0"),
                "source": "MOBILE_APP",
            },
        )

    def format_outbound(self, response: ChannelResponse) -> Dict[str, Any]:
        """
        Compact mobile response — optimized for low bandwidth.
        Excludes large HTML; uses structured field prompts.
        """
        return {
            "msg": response.text_content,          # Shorter key for mobile
            "opts": response.quick_replies or [],   # Compact options
            "field": response.metadata.get("current_slot"),
            "tid": response.metadata.get("tracking_id"),
            "aid": response.metadata.get("application_id"),
            "pct": response.metadata.get("progress_percent", 0),
            "state": response.metadata.get("status"),
            "upload": response.metadata.get("requires_upload", False),
            "pay": response.metadata.get("requires_payment", False),
            # Push notification payload (sent separately by notification service)
            "push": {
                "title": "RevenueSeva",
                "body": response.text_content[:100],
            } if response.metadata.get("send_push") else None,
            "channel": "MOBILE",
        }

    def can_handle_voice(self) -> bool:
        return True   # Mobile has on-device mic

    def can_handle_documents(self) -> bool:
        return True   # Mobile camera + gallery

    def max_message_length(self) -> int:
        return 500    # Short messages for mobile UI
