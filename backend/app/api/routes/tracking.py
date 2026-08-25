"""
Tracking Route — Public status lookup by tracking ID
GET  /api/v1/tracking/{tracking_id}       → Public status (no auth)
GET  /api/v1/applications/{id}/timeline   → Full event timeline (auth required)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.event_repo import EventRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.get("/{tracking_id}")
async def get_status_by_tracking_id(tracking_id: str, db: Session = Depends(get_db)):
    """
    Public status lookup — no authentication required.
    Returns application status, progress, and service info.
    Does NOT return any PII.
    """
    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_tracking_id(tracking_id) or app_repo.get_by_number(tracking_id)

    if not app:
        raise HTTPException(status_code=404, detail=f"No application found with tracking ID: {tracking_id}")

    service_name = {}
    if app.service:
        service_name = {
            "en": app.service.name_en,
            "hi": app.service.name_hi or app.service.name_en,
            "mr": app.service.name_mr or app.service.name_en,
        }

    # Get timeline (no PII)
    event_repo = EventRepository(db)
    events = event_repo.get_for_application(app.id)
    timeline = [
        {
            "event_type": e.event_type,
            "source_channel": e.source_channel,
            "timestamp": e.created_at.isoformat(),
        }
        for e in events
    ]

    return {
        "tracking_id": app.tracking_id,
        "application_number": app.application_number,
        "service": service_name,
        "status": app.status,
        "progress_percent": app.progress_percent,
        "channel_origin": app.channel_origin,
        "last_channel": app.last_channel,
        "language": app.language,
        "payment_status": app.payment_status,
        "validation_summary": app.validation_summary,
        "overall_match_score": app.overall_match_score,
        "created_at": app.created_at.isoformat(),
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "approved_at": app.approved_at.isoformat() if app.approved_at else None,
        "completed_at": app.completed_at.isoformat() if app.completed_at else None,
        "timeline": timeline,
        "disclaimer": "This is a data match score and does not verify document authenticity.",
    }
