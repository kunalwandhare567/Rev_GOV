"""
Channel Adapter Base Layer
All channels normalize to ChannelMessage / ChannelResponse.
Business logic never has if-channel checks — only adapters do.
"""
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum
from abc import ABC, abstractmethod


class Channel(str, Enum):
    WHATSAPP = "WHATSAPP"
    WEB = "WEB"
    MOBILE = "MOBILE"
    IVR = "IVR"
    EMAIL = "EMAIL"
    SYSTEM = "SYSTEM"


class Modality(str, Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"
    DTMF = "DTMF"
    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"


class EventType(str, Enum):
    APPLICATION_CREATED = "APPLICATION_CREATED"
    FIELD_UPDATED = "FIELD_UPDATED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    OCR_STARTED = "OCR_STARTED"
    OCR_COMPLETED = "OCR_COMPLETED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    MISMATCH_DETECTED = "MISMATCH_DETECTED"
    MISMATCH_RESOLVED = "MISMATCH_RESOLVED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    REVIEW_CONFIRMED = "REVIEW_CONFIRMED"
    SUBMITTED_FOR_VERIFICATION = "SUBMITTED_FOR_VERIFICATION"
    VERIFICATION_STATUS_CHANGED = "VERIFICATION_STATUS_CHANGED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    APPROVED = "APPROVED"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
    FINAL_SUBMISSION = "FINAL_SUBMISSION"
    APPLICATION_COMPLETED = "APPLICATION_COMPLETED"


@dataclass
class ChannelMessage:
    """
    Normalized internal message format.
    All channel adapters convert their native format to this.
    Business logic only works with ChannelMessage — never raw payloads.
    """
    channel: Channel
    citizen_identifier: str          # WhatsApp number, session token, phone, etc.
    modality: Modality
    text_content: Optional[str] = None      # Text or STT-converted text
    raw_audio_path: Optional[str] = None    # Path to downloaded/recorded audio
    attachment_path: Optional[str] = None   # Path to uploaded document/image
    attachment_type: Optional[str] = None   # "image", "pdf", "audio"
    language: Optional[str] = None          # Detected or declared language code
    application_ref: Optional[str] = None   # application_id if continuing
    tracking_id: Optional[str] = None       # If querying by tracking ID
    metadata: dict = field(default_factory=dict)  # Channel-specific extras


@dataclass
class ChannelResponse:
    """
    Normalized response.
    Channel adapters convert this to their native format.
    """
    text_content: str
    audio_file_path: Optional[str] = None    # TTS response audio path
    attachments: List[dict] = field(default_factory=list)
    action: Optional[str] = None             # "send_web_link", "show_options", etc.
    action_data: dict = field(default_factory=dict)
    language: str = "en"
    options: List[dict] = field(default_factory=list)  # Quick reply options
    # [{"id": "1", "label": "Use document name"}, {"id": "2", "label": "Keep my name"}]


class ChannelAdapter(ABC):
    """Abstract base class — each channel implements this."""

    @abstractmethod
    def normalize_inbound(self, raw_payload: dict) -> ChannelMessage:
        """Convert channel-native payload to ChannelMessage."""
        ...

    @abstractmethod
    def send_response(self, recipient_id: str, response: ChannelResponse) -> bool:
        """Send ChannelResponse back to citizen via this channel."""
        ...

    def send_notification(self, recipient_id: str, notification_type: str,
                          data: dict) -> bool:
        """Send a proactive notification (override in channels that support it)."""
        return False
