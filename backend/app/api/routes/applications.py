import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.rules_engine.engine import ServiceSpecLoader

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/services")
def list_services():
    """List all available certificate services (from YAML specs)."""
    services = ServiceSpecLoader.list_services()
    return {"status": "ok", "count": len(services), "services": services}


@router.get("/services/{service_id}")
def get_service(service_id: str):
    """Get detailed spec for a specific service."""
    spec = ServiceSpecLoader.get(service_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    return {
        "id": spec.id,
        "name": spec.name,
        "department": spec.department,
        "sla_days": spec.sla_days,
        "fee": {"amount": spec.fee_amount, "currency": spec.fee_currency},
        "waiver_conditions": spec.waiver_conditions,
        "slots": [
            {
                "name": s.name,
                "type": s.type,
                "required": s.required,
                "classification": s.classification,
                "prompt": s.prompt,
            }
            for s in spec.slots
        ],
        "required_docs": spec.required_docs,
        "eligibility_rules": spec.eligibility_rules,
    }


@router.get("/status/{application_number}")
def get_application_status(application_number: str, db: Session = Depends(get_db)):
    """Check status of a specific application by application number."""
    repo = ApplicationRepository(db)
    app = repo.get_by_number(application_number)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    cert = None
    if app.certificate:
        cert = {
            "certificate_number": app.certificate.certificate_number,
            "issue_date": app.certificate.issue_date.isoformat(),
        }

    slots_data = repo.get_fields(app.id, decrypt=True)

    return {
        "application": {
            "application_number": app.application_number,
            "service_type":   app.service_id,   # service_id is the service type key
            "service_name":   app.service.name_en if app.service else None,
            "sla_days":       app.service.sla_days if app.service else None,
            "status":         app.status,
            "payment_status": app.payment_status,
            "fee_paid_amount": (app.payments[0].amount if app.payments else None),
            "fee_waiver":     False,
            "payment_reference": (app.payments[0].transaction_id if app.payments else None),
            "channel":        app.channel_origin,
            "language":       app.language,
            "consent_given":  app.consent_given,
            "anomaly_score":  app.anomaly_score,
            "literacy_level": None,
            "citizen_ref":    app.citizen_ref,
            "slots_data":     slots_data,
            "submitted_at":   app.submitted_at.isoformat() if app.submitted_at else None,
            "completed_at":   app.completed_at.isoformat() if app.completed_at else None,
            "created_at":     app.created_at.isoformat(),
            "certificate":    cert,
            "documents":      [
                {
                    "id": d.id,
                    "doc_type": d.doc_type,
                    "filename": os.path.basename(d.file_ref) if d.file_ref else "",
                    "file_ref": f"/data/uploads/{os.path.basename(d.file_ref)}" if d.file_ref and not d.file_ref.startswith("mock") else d.file_ref,
                    "is_verified": d.verification_status == "VERIFIED",
                    "verification_status": d.verification_status,
                    "mismatch_fields": d.mismatch_fields,
                    "extracted_fields": d.extracted_fields,
                    "confidence_score": d.confidence_score,
                    "uploaded_at": d.created_at.isoformat(),
                }
                for d in (app.documents or [])
            ],
            "eligibility_result": {},
            "conversation_log":   [],
        }
    }



@router.get("/citizen/{citizen_identifier}")
def get_citizen_applications(
    citizen_identifier: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get all applications for a citizen."""
    citizen_repo = CitizenRepository(db)
    citizen = citizen_repo.resolve_or_create(citizen_identifier)
    app_repo = ApplicationRepository(db)
    apps = app_repo.get_by_citizen(citizen.citizen_ref, limit=limit)

    return {
        "citizen_ref": citizen.citizen_ref,
        "count": len(apps),
        "applications": [
            {
                "application_number": a.application_number,
                "service_id": a.service_id,
                "status": a.status,
                "payment_status": a.payment_status,
                "created_at": a.created_at.isoformat(),
            }
            for a in apps
        ],
    }


@router.get("/recent")
def get_recent_applications(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get recent applications (admin/officer view)."""
    repo = ApplicationRepository(db)
    return {"applications": repo.get_recent_applications(limit=limit)}


from pydantic import BaseModel

class StatusUpdateRequest(BaseModel):
    status: str
    note: str = ""

@router.patch("/status/{application_number}")
def update_application_status(
    application_number: str,
    body: StatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update application status (officer action)."""
    status = body.status
    valid_statuses = ["UNDER_REVIEW", "APPROVED", "REJECTED", "ESCALATED"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    repo = ApplicationRepository(db)
    app = repo.get_by_number(application_number)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = app.status
    updated = repo.update_status(app.id, status)

    # Write audit log
    from app.data_layer.repositories.audit_repo import AuditRepository
    AuditRepository(db).write(
        event_type="STATUS_UPDATE",
        actor="OFFICER",
        application_id=app.id,
        action=f"Status updated: {old_status} to {status}. Note: {body.note}",
        outcome="SUCCESS",
        metadata={"application_number": application_number, "new_status": status, "note": body.note},
    )

    return {
        "application_number": application_number,
        "old_status": old_status,
        "new_status": status,
        "updated": True,
    }


@router.post("/status/{application_number}/simulate-approve")
def simulate_approve_application(application_number: str, db: Session = Depends(get_db)):
    """Simulate government officer approval for testing/demo purposes."""
    repo = ApplicationRepository(db)
    app = repo.get_by_number(application_number)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = app.status
    # Move to APPROVED
    repo.update_status(app.id, "APPROVED")

    # Write audit log
    from app.data_layer.repositories.audit_repo import AuditRepository
    AuditRepository(db).write(
        event_type="STATUS_UPDATE",
        actor="SYSTEM_SIMULATOR",
        application_id=app.id,
        action=f"Status auto-approved via simulator: {old_status} to APPROVED",
        outcome="SUCCESS",
        metadata={"application_number": application_number, "new_status": "APPROVED"},
    )

    return {
        "application_number": application_number,
        "old_status": old_status,
        "new_status": "APPROVED",
        "updated": True,
    }


@router.post("/validate-eligibility")

def validate_eligibility_endpoint(
    service_id: str,
    slots: dict,
    language: str = "en",
    db: Session = Depends(get_db),
):
    """Validate eligibility for a service before full application."""
    spec = ServiceSpecLoader.get(service_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Service not found")

    from app.rules_engine.engine import EligibilityChecker, FeeCalculator
    eligibility = EligibilityChecker.check(spec, slots, language)
    fee = FeeCalculator.calculate(spec, slots)

    return {
        "eligible": eligibility.valid,
        "errors": eligibility.errors,
        "warnings": eligibility.warnings,
        "fee": {
            "base": fee.base_fee,
            "discount": fee.discount,
            "final": fee.final_fee,
            "waiver_reason": fee.waiver_reason,
        },
    }
