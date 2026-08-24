"""
Phase 12 completion — Wire SSE EventBus publish to application status changes.
Also wires payment completion, OCR completion, and document mismatch events.

This file is a mixin/helper imported by routes that need to broadcast events.
"""
from app.api.routes.stream import bus
from app.channels.base import EventType
import logging

logger = logging.getLogger(__name__)


def broadcast_status_change(application_id: str, new_status: str, progress: int = None,
                             channel: str = "WEB", tracking_id: str = None) -> None:
    """Publish status change to all SSE subscribers for this application."""
    bus.publish_sync(application_id, {
        "type": "status_changed",
        "application_id": application_id,
        "tracking_id": tracking_id,
        "status": new_status,
        "progress": progress,
        "channel": channel,
        "event_type": EventType.VERIFICATION_STATUS_CHANGED.value,
    })


def broadcast_payment_complete(application_id: str, txn_id: str, amount: float,
                                tracking_id: str = None) -> None:
    """Publish payment completion to SSE subscribers."""
    bus.publish_sync(application_id, {
        "type": "payment_completed",
        "application_id": application_id,
        "tracking_id": tracking_id,
        "txn_id": txn_id,
        "amount": amount,
        "status": "PAYMENT_COMPLETED",
        "progress": 85,
        "event_type": EventType.PAYMENT_COMPLETED.value,
    })


def broadcast_ocr_complete(application_id: str, doc_id: str, match_score: float,
                            mismatch_fields: list, tracking_id: str = None) -> None:
    """Publish OCR completion result to SSE subscribers."""
    event_type = EventType.MISMATCH_DETECTED.value if mismatch_fields else EventType.OCR_COMPLETED.value
    bus.publish_sync(application_id, {
        "type": "ocr_completed",
        "application_id": application_id,
        "tracking_id": tracking_id,
        "doc_id": doc_id,
        "match_score": match_score,
        "mismatch_fields": mismatch_fields,
        "has_mismatch": len(mismatch_fields) > 0,
        "event_type": event_type,
    })


def broadcast_mismatch_resolved(application_id: str, doc_id: str, field: str,
                                  tracking_id: str = None) -> None:
    """Publish mismatch resolution to SSE subscribers."""
    bus.publish_sync(application_id, {
        "type": "mismatch_resolved",
        "application_id": application_id,
        "tracking_id": tracking_id,
        "doc_id": doc_id,
        "field": field,
        "event_type": EventType.MISMATCH_RESOLVED.value,
    })
