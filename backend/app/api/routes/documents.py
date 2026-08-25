"""
Documents API route — extended endpoints for ApplicationReview page
GET  /api/v1/applications/{id}/documents
GET  /api/v1/applications/{id}/fields
PUT  /api/v1/applications/{id}/fields/{field_name}
POST /api/v1/applications/{id}/documents/{doc_id}/resolve
POST /api/v1/applications/{id}/submit
GET  /api/v1/applications/{id}
"""
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from jose import jwt, JWTError

from app.core.database import get_db
from app.core.config import settings
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.document_repo import DocumentRepository
from app.data_layer.repositories.event_repo import EventRepository
from app.channels.base import EventType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["applications-v2"])


def _verify_app_access(request: Request, app_citizen_ref: str):
    """Verify that citizen accessing this application is the owner (or admin/officer)."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            role = payload.get("role")
            if role in ("ADMIN", "OFFICER", "admin", "officer"):
                return
            token_citizen_ref = payload.get("citizen_ref")
            if token_citizen_ref and token_citizen_ref != app_citizen_ref:
                raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this application.")
        except HTTPException:
            raise
        except JWTError:
            pass


@router.get("/{application_id}")
def get_application_by_id(application_id: str, request: Request, db: Session = Depends(get_db)):
    """Get application by UUID (for ApplicationReview page)."""
    repo = ApplicationRepository(db)
    app = repo.get_by_id(application_id) or repo.get_by_number(application_id) or repo.get_by_tracking_id(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    _verify_app_access(request, app.citizen_ref)

    event_repo = EventRepository(db)
    events = event_repo.get_for_application(app.id)

    return {
        "id": app.id,
        "tracking_id": app.tracking_id,
        "application_number": app.application_number,
        "service_id": app.service_id,
        "service_name": app.service.name_en if app.service else app.service_id,
        "service": {
            "en": app.service.name_en if app.service else app.service_id,
            "hi": app.service.name_hi if app.service else app.service_id,
            "mr": app.service.name_mr if app.service else app.service_id,
        } if app.service else {},
        "status": app.status,
        "current_step": app.current_step,
        "progress_percent": app.progress_percent or 0,
        "channel_origin": app.channel_origin,
        "last_channel": app.last_channel,
        "language": app.language,
        "payment_status": app.payment_status,
        "overall_match_score": app.overall_match_score,
        "validation_summary": app.validation_summary,
        "created_at": app.created_at.isoformat(),
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "approved_at": app.approved_at.isoformat() if hasattr(app, 'approved_at') and app.approved_at else None,
        "completed_at": app.completed_at.isoformat() if app.completed_at else None,
        "timeline": [
            {
                "event_type": e.event_type,
                "source_channel": e.source_channel,
                "timestamp": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


@router.get("/{application_id}/documents")
def get_documents(application_id: str, request: Request, db: Session = Depends(get_db)):
    """Get all documents for an application with OCR match scores."""
    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_id(application_id) or app_repo.get_by_number(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    _verify_app_access(request, app.citizen_ref)

    doc_repo = DocumentRepository(db)
    docs = doc_repo.get_by_application(app.id)
    return [
        {
            "id": d.id,
            "doc_id": d.id,
            "document_id": d.id,
            "doc_type": d.doc_type,
            "document_type": d.doc_type,
            "upload_channel": d.upload_channel or "WEB",
            "verification_status": d.verification_status,
            "confidence_score": d.confidence_score or 1.0,
            "overall_match_score": d.overall_match_score,
            "extracted_fields": d.extracted_fields or {},
            "field_match_scores": d.field_match_scores or {},
            "mismatch_fields": d.mismatch_fields or [],
            "matched_fields": getattr(d, "matched_fields", []) or [],
            "mismatch_resolutions": d.mismatch_resolutions or {},
            "raw_ocr": {
                "text": getattr(d, "raw_ocr_text", "") or "",
                "fields": getattr(d, "raw_extracted_fields", {}) or {},
            },
            "raw_ocr_text": getattr(d, "raw_ocr_text", "") or "",
            "raw_extracted_fields": getattr(d, "raw_extracted_fields", {}) or {},
            "normalized_ocr": {
                "fields": getattr(d, "normalized_fields", {}) or d.extracted_fields or {},
                "confidence": getattr(d, "normalization_confidence", {}) or {},
            },
            "normalized_fields": getattr(d, "normalized_fields", {}) or d.extracted_fields or {},
            "normalization_confidence": getattr(d, "normalization_confidence", {}) or {},
            "normalization_status": getattr(d, "normalization_status", "DETERMINISTIC"),
            "matching": {
                "score": d.overall_match_score or 0.0,
                "status": d.verification_status,
                "matched_fields": getattr(d, "matched_fields", []) or [],
                "mismatched_fields": d.mismatch_fields or [],
            },
            "filename": os.path.basename(d.file_ref) if d.file_ref else "",
            "file_ref": f"/data/uploads/{os.path.basename(d.file_ref)}" if d.file_ref and not d.file_ref.startswith("mock") else d.file_ref,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/{application_id}/fields")
def get_application_fields(application_id: str, request: Request, db: Session = Depends(get_db)):
    """Get all fields with provenance metadata."""
    repo = ApplicationRepository(db)
    app = repo.get_by_id(application_id) or repo.get_by_number(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    _verify_app_access(request, app.citizen_ref)

    fields_with_provenance = repo.get_fields_with_provenance(app.id)
    # Convert to dict keyed by field_name
    return {
        f["field_name"]: {
            "value": f["value"],
            "source": f["source"],
            "confirmed": f["confirmed"],
            "version": f["version"],
            "classification": f["classification"],
            "updated_at": f["updated_at"],
        }
        for f in fields_with_provenance
    }


class FieldUpdateRequest(BaseModel):
    value: str
    source: str = "WEB_EDIT"
    override_reason: Optional[str] = None


@router.put("/{application_id}/fields/{field_name}")
def update_field(
    application_id: str,
    field_name: str,
    body: FieldUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update a single field (with provenance tracking)."""
    repo = ApplicationRepository(db)
    app = repo.get_by_id(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    repo.save_field(
        application_id=application_id,
        field_name=field_name,
        field_value=body.value,
        source=body.source,
        override_reason=body.override_reason,
    )

    event_repo = EventRepository(db)
    event_repo.create_event(
        application_id=application_id,
        citizen_ref=app.citizen_ref,
        event_type=EventType.FIELD_UPDATED.value,
        source_channel="WEB",
        event_data={"field": field_name, "source": body.source},
    )

    return {"field_name": field_name, "updated": True, "source": body.source}


class MismatchResolveRequest(BaseModel):
    field: str
    resolution: str   # USE_OCR | USE_APPLICATION | MANUAL
    manual_value: Optional[str] = None


@router.post("/{application_id}/documents/{doc_id}/resolve")
def resolve_mismatch(
    application_id: str,
    doc_id: str,
    body: MismatchResolveRequest,
    db: Session = Depends(get_db),
):
    """Resolve a field mismatch between OCR data and application data."""
    doc_repo = DocumentRepository(db)
    app_repo = ApplicationRepository(db)

    doc = doc_repo.get(doc_id)
    if not doc or doc.application_id != application_id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Resolve in document
    doc_repo.resolve_mismatch(doc_id, body.field, body.resolution)

    # If USE_OCR, update the application field with OCR value
    if body.resolution == "USE_OCR":
        ocr_value = (doc.extracted_fields or {}).get(body.field)
        if ocr_value:
            app = app_repo.get_by_id(application_id)
            app_repo.save_field(
                application_id=application_id,
                field_name=body.field,
                field_value=str(ocr_value),
                source="OCR_RESOLUTION",
                confirmed=True,
            )

    elif body.resolution == "MANUAL" and body.manual_value:
        app = app_repo.get_by_id(application_id)
        app_repo.save_field(
            application_id=application_id,
            field_name=body.field,
            field_value=body.manual_value,
            source="MANUAL_RESOLUTION",
            confirmed=True,
        )

    # Record event
    app = app_repo.get_by_id(application_id)
    event_repo = EventRepository(db)
    event_repo.create_event(
        application_id=application_id,
        citizen_ref=app.citizen_ref if app else "",
        event_type=EventType.MISMATCH_RESOLVED.value,
        source_channel="WEB",
        event_data={"doc_id": doc_id, "field": body.field, "resolution": body.resolution},
    )

    all_resolved = doc_repo.all_mismatches_resolved(doc_id)
    return {
        "resolved": True,
        "field": body.field,
        "resolution": body.resolution,
        "all_mismatches_resolved": all_resolved,
    }


@router.post("/{application_id}/submit")
def submit_for_verification(application_id: str, db: Session = Depends(get_db)):
    """Submit application for government verification."""
    repo = ApplicationRepository(db)
    app = repo.get_by_id(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if app.status not in ("FINAL_REVIEW", "OCR_VALIDATION", "DOCUMENT_COLLECTION"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit application in status: {app.status}"
        )

    repo.update_status(application_id, "SUBMITTED_FOR_VERIFICATION")
    repo.update_progress(application_id, 70, "SUBMITTED_FOR_VERIFICATION")
    repo.update_last_channel(application_id, "WEB")

    event_repo = EventRepository(db)
    event_repo.create_event(
        application_id=application_id,
        citizen_ref=app.citizen_ref,
        event_type=EventType.SUBMITTED_FOR_VERIFICATION.value,
        source_channel="WEB",
    )

    return {
        "submitted": True,
        "tracking_id": app.tracking_id,
        "message": "Application submitted for government verification. You will be notified of any updates.",
    }
