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


from fastapi import Request
from jose import jwt, JWTError
from app.core.config import settings
from app.api.routes.auth import get_current_citizen
from app.core.security import verify_application_ownership


@router.get("/my-applications")
def get_my_applications(
    current_citizen = Depends(get_current_citizen),
    db: Session = Depends(get_db),
):
    """
    Get all applications belonging ONLY to the authenticated citizen.
    Backend authorization is strictly enforced.
    """
    repo = ApplicationRepository(db)
    apps = repo.get_by_citizen(current_citizen.citizen_ref, limit=50)

    return {
        "status": "ok",
        "citizen_id": current_citizen.citizen_ref,
        "count": len(apps),
        "applications": [
            {
                "id": a.id,
                "application_number": a.application_number,
                "tracking_id": a.tracking_id,
                "service_id": a.service_id,
                "service_name": a.service.name_en if a.service else a.service_id,
                "status": a.status,
                "progress_percent": a.progress_percent,
                "payment_status": a.payment_status,
                "channel_origin": a.channel_origin,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in apps
        ]
    }


@router.get("/citizen/{citizen_ref}")
def get_applications_by_citizen_ref(
    citizen_ref: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Backward-compatible citizen application lookup route.
    If authenticated with JWT, validates ownership.
    Returns canonical list of applications for the citizen.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            token_ref = payload.get("citizen_ref")
            role = payload.get("role")
            if token_ref and token_ref != citizen_ref and role not in ("ADMIN", "OFFICER"):
                raise HTTPException(status_code=403, detail="Access forbidden: citizen ID mismatch")
        except JWTError:
            pass

    repo = ApplicationRepository(db)
    apps = repo.get_by_citizen(citizen_ref, limit=limit)
    return {
        "status": "ok",
        "citizen_id": citizen_ref,
        "count": len(apps),
        "applications": [
            {
                "id": a.id,
                "application_number": a.application_number,
                "tracking_id": a.tracking_id,
                "service_id": a.service_id,
                "service_name": a.service.name_en if a.service else a.service_id,
                "status": a.status,
                "progress_percent": a.progress_percent,
                "payment_status": a.payment_status,
                "channel_origin": a.channel_origin,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in apps
        ]
    }


@router.get("/status/{application_number}")
def get_application_status(
    application_number: str,
    current_citizen = Depends(get_current_citizen),
    db: Session = Depends(get_db),
):
    """Check status of a specific application by application number with ownership verification."""
    repo = ApplicationRepository(db)
    app = repo.get_by_number(application_number) or repo.get_by_id(application_number)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Enforce backend authorization: citizen can only view their own application
    verify_application_ownership(app.id, current_citizen.citizen_ref, db)

    cert = None
    if app.certificate:
        cert = {
            "certificate_number": app.certificate.certificate_number,
            "issue_date": app.certificate.issue_date.isoformat(),
        }

    slots_data = repo.get_fields(app.id, decrypt=True)

    return {
        "application": {
            "id":                 app.id,
            "application_number": app.application_number,
            "tracking_id":        app.tracking_id,
            "service_type":       app.service_id,   # service_id is the service type key
            "service_name":       app.service.name_en if app.service else None,
            "sla_days":           app.service.sla_days if app.service else None,
            "status":             app.status,
            "payment_status":     app.payment_status,
            "fee_paid_amount":    (app.payments[0].amount if app.payments else None),
            "fee_waiver":         False,
            "payment_reference":  (app.payments[0].transaction_id if app.payments else None),
            "channel":            app.channel_origin,
            "language":           app.language,
            "consent_given":      app.consent_given,
            "anomaly_score":      app.anomaly_score,
            "literacy_level":     None,
            "citizen_ref":        app.citizen_ref,
            "slots_data":         slots_data,
            "submitted_at":       app.submitted_at.isoformat() if app.submitted_at else None,
            "completed_at":       app.completed_at.isoformat() if app.completed_at else None,
            "created_at":         app.created_at.isoformat(),
            "certificate":        cert,
            "documents":          [
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
    current_citizen = Depends(get_current_citizen),
    db: Session = Depends(get_db),
):
    """Get all applications for a citizen with authorization guard."""
    citizen_repo = CitizenRepository(db)
    target_citizen = citizen_repo.get_by_identifier(citizen_identifier) or citizen_repo.get_by_ref(citizen_identifier)
    
    if not target_citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")
        
    if target_citizen.citizen_ref != current_citizen.citizen_ref:
        raise HTTPException(status_code=403, detail="Forbidden: You cannot access another citizen's applications.")

    app_repo = ApplicationRepository(db)
    apps = app_repo.get_by_citizen(target_citizen.citizen_ref, limit=limit)

    return {
        "citizen_ref": target_citizen.citizen_ref,
        "count": len(apps),
        "applications": [
            {
                "application_number": a.application_number,
                "tracking_id": a.tracking_id,
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
    """Update application status (officer action). Broadcasts via SSE."""
    status = body.status
    valid_statuses = ["UNDER_REVIEW", "APPROVED", "REJECTED", "ESCALATED",
                      "PAYMENT_COMPLETED", "SUBMITTED_FOR_VERIFICATION", "CERTIFICATE_READY"]
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

    # Push chat message into citizen's conversation session
    try:
        from app.data_layer.repositories.session_repo import SessionRepository
        session_repo = SessionRepository(db)
        session = session_repo.load_session(app.citizen_ref)
        if session:
            status_msgs = {
                "APPROVED": f"🎉 Great news! Your application **{application_number}** has been **APPROVED** by the officer! Your certificate will be issued shortly.",
                "REJECTED": f"❌ Your application **{application_number}** was **REJECTED** by the officer. Reason: {body.note or 'Details do not match requirements'}",
                "UNDER_REVIEW": f"📋 Your application **{application_number}** is now **UNDER REVIEW** by an officer.",
                "ESCALATED": f"🆘 Your application **{application_number}** has been **ESCALATED** to a senior officer.",
                "CERTIFICATE_READY": f"📜 Congratulations! Your certificate for application **{application_number}** is **READY** to download!",
            }
            msg_text = status_msgs.get(status)
            if msg_text:
                session_repo.add_message(session.id, "ASSISTANT", msg_text)
                logger.info(f"Officer status update '{status}' saved to citizen session {session.id}")
    except Exception as e:
        logger.warning(f"Could not store officer status update message: {e}")

    # ── Phase 12: Broadcast SSE event to all connected clients ──
    try:
        from app.core.events import broadcast_status_change
        PROGRESS_MAP = {
            "UNDER_REVIEW": 60, "APPROVED": 100, "REJECTED": 100,
            "ESCALATED": 65, "PAYMENT_COMPLETED": 85,
            "SUBMITTED_FOR_VERIFICATION": 90, "CERTIFICATE_READY": 100,
        }
        broadcast_status_change(
            application_id=app.id,
            new_status=status,
            progress=PROGRESS_MAP.get(status),
            channel="OFFICER_WEB",
            tracking_id=app.tracking_id,
        )
    except Exception as e:
        logger.warning(f"SSE broadcast failed (non-critical): {e}")

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
    repo.update_status(app.id, "APPROVED")

    from app.data_layer.repositories.audit_repo import AuditRepository
    AuditRepository(db).write(
        event_type="STATUS_UPDATE",
        actor="SYSTEM_SIMULATOR",
        application_id=app.id,
        action=f"Status auto-approved via simulator: {old_status} to APPROVED",
        outcome="SUCCESS",
        metadata={"application_number": application_number, "new_status": "APPROVED"},
    )

    # ── Phase 12: SSE broadcast ──
    try:
        from app.core.events import broadcast_status_change
        broadcast_status_change(app.id, "APPROVED", 100, "SYSTEM", app.tracking_id)
    except Exception as e:
        logger.warning(f"SSE broadcast failed: {e}")

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


@router.get("/{application_number}/readiness")
def get_application_readiness(
    application_number: str,
    db: Session = Depends(get_db),
):
    """
    Phase 7 — Compute and return Application Readiness Score.

    Returns a 0-100 score based on 5 components:
      1. Field Completeness     (30 pts)
      2. Document Coverage      (25 pts)
      3. OCR Validation         (20 pts)
      4. Eligibility            (15 pts)
      5. Cross-field Consistency (10 pts)

    Frontend NEVER calculates this — always fetches from backend.
    Score ≥ 75 and no blocking issues → can_submit = true.
    """
    from app.services.readiness_engine import ReadinessEngine
    from app.rules_engine.engine import EligibilityChecker

    repo = ApplicationRepository(db)
    app = repo.get_by_number(application_number)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application '{application_number}' not found")

    service_id = getattr(app, "service_id", None)
    filled_slots = dict(getattr(app, "submitted_data", None) or {})

    # Get required slots and docs from YAML
    try:
        spec = ServiceSpecLoader.get(service_id)
        required_slots = [s.name for s in spec.slots if s.required]
        required_docs = list(spec.required_docs or [])
    except Exception:
        required_slots = []
        required_docs = []

    # Get uploaded documents
    uploaded_docs = []
    if app.documents:
        uploaded_docs = [
            getattr(d, "doc_type", getattr(d, "document_type", "")) or ""
            for d in app.documents
        ]

    # Get OCR results
    ocr_results = []
    if app.documents:
        for doc in app.documents:
            ocr_status = getattr(doc, "ocr_status", None) or getattr(doc, "validation_status", "PENDING")
            match_score = getattr(doc, "match_score", 0) or 0
            ocr_results.append({
                "doc_type": getattr(doc, "doc_type", "") or "",
                "status": ocr_status,
                "overall_match_score": float(match_score),
            })

    # Run eligibility check
    eligibility_result = None
    try:
        spec = ServiceSpecLoader.get(service_id)
        elig = EligibilityChecker.check(spec, filled_slots)
        eligibility_result = {
            "eligible": elig.valid,
            "reason": "; ".join(elig.errors) if elig.errors else "Eligible",
        }
    except Exception:
        pass

    engine = ReadinessEngine()
    result = engine.compute(
        service_id=service_id or "",
        filled_slots=filled_slots,
        required_slots=required_slots,
        required_docs=required_docs,
        uploaded_docs=uploaded_docs,
        ocr_results=ocr_results,
        eligibility_result=eligibility_result,
    )

    return result.to_dict()


@router.get("/{application_number}/evidence-graph")
def get_evidence_graph(
    application_number: str,
    db: Session = Depends(get_db),
):
    """
    Phase 7 (Gap Fix) — Evidence Graph.

    Returns a structured JSON showing:
    - Which document supports which declared field
    - Which fields have conflicts between declared and OCR values
    - Which fields are fully verified
    - Which fields have missing evidence

    This helps the admin and citizen understand validation confidence.
    """
    repo = ApplicationRepository(db)
    app = repo.get_by_number(application_number)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application '{application_number}' not found")

    filled_slots = dict(getattr(app, "submitted_data", None) or {})
    graph = {"fields": {}, "documents": [], "summary": {}}

    # Initialize field nodes from declared data
    for field_name, declared_value in filled_slots.items():
        graph["fields"][field_name] = {
            "declared_value": declared_value,
            "doc_sources": [],      # which docs have this field
            "verified": False,
            "conflicting": False,
            "missing_evidence": True,
            "confidence": None,
        }

    # Populate from document OCR results
    if app.documents:
        for doc in app.documents:
            doc_type = getattr(doc, "doc_type", "") or ""
            ocr_status = getattr(doc, "ocr_status", "PENDING") or "PENDING"
            match_result = getattr(doc, "match_result", None)

            doc_node = {
                "doc_type": doc_type,
                "status": ocr_status,
                "fields_extracted": [],
                "fields_matched": [],
                "fields_mismatched": [],
            }

            if match_result and isinstance(match_result, dict):
                # Fields that matched
                for f in match_result.get("matched_fields", []):
                    fname = f.get("field", "")
                    doc_node["fields_matched"].append(fname)
                    if fname in graph["fields"]:
                        graph["fields"][fname]["verified"] = True
                        graph["fields"][fname]["missing_evidence"] = False
                        graph["fields"][fname]["confidence"] = f.get("score", 100)
                        graph["fields"][fname]["doc_sources"].append(doc_type)

                # Fields that mismatched
                for f in match_result.get("mismatched_fields", []):
                    fname = f.get("field", "")
                    doc_node["fields_mismatched"].append(fname)
                    if fname in graph["fields"]:
                        graph["fields"][fname]["conflicting"] = True
                        graph["fields"][fname]["missing_evidence"] = False
                        graph["fields"][fname]["confidence"] = f.get("score", 0)
                        graph["fields"][fname]["doc_sources"].append(doc_type)

            graph["documents"].append(doc_node)

    # Summary
    all_fields = graph["fields"]
    total = len(all_fields)
    verified = sum(1 for f in all_fields.values() if f["verified"])
    conflicting = sum(1 for f in all_fields.values() if f["conflicting"])
    missing_evidence = sum(1 for f in all_fields.values() if f["missing_evidence"])

    graph["summary"] = {
        "total_fields": total,
        "verified_fields": verified,
        "conflicting_fields": conflicting,
        "missing_evidence_fields": missing_evidence,
        "verification_coverage_pct": round((verified / total * 100) if total > 0 else 0, 1),
    }

    return graph


@router.get("/current")
def get_current_application(
    citizen_identifier: str = Query(...),
    service_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Phase 12 — Application Deduplication.

    Returns the most recent active (non-terminal) application for a citizen.
    Used by the web portal to load the same application started on WhatsApp.
    Prevents duplicate applications across channels.
    """
    repo = ApplicationRepository(db)
    citizen_repo = CitizenRepository(db)

    citizen = citizen_repo.get_by_identifier(citizen_identifier)
    if not citizen:
        return {"found": False, "application": None}

    # Try service-specific lookup first
    terminal_states = ["COMPLETED", "REJECTED"]
    apps = repo.get_by_citizen_ref(citizen.citizen_ref)

    if apps:
        # Filter: non-terminal, optionally by service
        active = [
            a for a in apps
            if a.status not in terminal_states
            and (not service_id or getattr(a, "service_id", None) == service_id)
        ]
        # Sort: most recent first
        active.sort(key=lambda a: getattr(a, "created_at", ""), reverse=True)

        if active:
            app = active[0]
            return {
                "found": True,
                "application": {
                    "id": str(app.id),
                    "application_number": getattr(app, "application_number", None),
                    "tracking_id": getattr(app, "tracking_id", None),
                    "service_id": getattr(app, "service_id", None),
                    "status": app.status,
                    "created_at": str(getattr(app, "created_at", "")),
                },
            }

    return {"found": False, "application": None}
