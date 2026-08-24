"""
WhatsApp Channel Adapter (Mock/Simulator Mode)
Since we don't have Meta Business API credentials,
this adapter simulates WhatsApp behavior:
- Inbound messages come from our WhatsApp Clone UI via REST API
- Outbound messages are stored in DB for UI to fetch and display
"""
import os
import logging
from app.channels.base import ChannelAdapter, ChannelMessage, ChannelResponse, Channel, Modality

logger = logging.getLogger(__name__)


class WhatsAppAdapter(ChannelAdapter):
    """
    WhatsApp Clone adapter.
    In SIMULATOR mode: accepts messages from our React WhatsApp UI.
    In PRODUCTION mode: swap _send_text() with Meta Graph API calls.
    """

    def normalize_inbound(self, raw_payload: dict) -> ChannelMessage:
        """
        Normalize message from our WhatsApp Clone UI.
        UI sends: {from_number, message_type, text, audio_path, file_path, language}
        """
        msg_type = raw_payload.get("message_type", "text")
        wa_number = raw_payload.get("from_number", "simulator")

        if msg_type == "text":
            return ChannelMessage(
                channel=Channel.WHATSAPP,
                citizen_identifier=wa_number,
                modality=Modality.TEXT,
                text_content=raw_payload.get("text", ""),
                language=raw_payload.get("language"),
            )
        elif msg_type == "audio":
            return ChannelMessage(
                channel=Channel.WHATSAPP,
                citizen_identifier=wa_number,
                modality=Modality.VOICE,
                raw_audio_path=raw_payload.get("audio_path"),
                language=raw_payload.get("language"),
            )
        elif msg_type in ("image", "document"):
            return ChannelMessage(
                channel=Channel.WHATSAPP,
                citizen_identifier=wa_number,
                modality=Modality.DOCUMENT,
                text_content=raw_payload.get("caption"),
                attachment_path=raw_payload.get("file_path"),
                attachment_type=msg_type,
                language=raw_payload.get("language"),
            )
        return ChannelMessage(
            channel=Channel.WHATSAPP,
            citizen_identifier=wa_number,
            modality=Modality.TEXT,
            text_content=raw_payload.get("text", ""),
        )

    def send_response(self, wa_number: str, response: ChannelResponse) -> bool:
        """
        In simulator mode: response is returned directly to the UI.
        No actual sending needed — the API handler returns the response.
        """
        logger.debug(f"[WhatsApp→{wa_number}]: {response.text_content[:80]}...")
        return True

    def send_notification(self, wa_number: str, notification_type: str,
                          data: dict) -> bool:
        """
        In production: POST to Meta Graph API with template message.
        In simulator: stored in DB via NotificationService.
        """
        logger.info(f"[WhatsApp Notification→{wa_number}] {notification_type}: {data}")
        return True
