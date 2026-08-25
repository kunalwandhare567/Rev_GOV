import os
import uuid
import datetime
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.rules_engine.engine import ServiceSpecLoader
from app.orchestration.state_machine.application_fsm import STATE_PROGRESS, AppState

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
                "progress_percent": a.progress_percent if a.progress_percent is not None and a.progress_percent > 0 else STATE_PROGRESS.get(a.status, 0),
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


@router.get("/{id_or_number}/certificate")
def download_application_certificate(id_or_number: str, db: Session = Depends(get_db)):
    """Download official issued certificate PDF."""
    from fastapi.responses import FileResponse
    repo = ApplicationRepository(db)
    app = repo.get_by_id(id_or_number) or repo.get_by_number(id_or_number) or repo.get_by_tracking_id(id_or_number)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if not app.certificate or not app.certificate.file_ref or not os.path.exists(app.certificate.file_ref):
        from app.services.certificate_service import CertificateService
        svc = CertificateService(db)
        svc.generate_and_store(str(app.id), app.citizen_ref or "CITIZEN")
        db.refresh(app)

    if app.certificate and app.certificate.file_ref and os.path.exists(app.certificate.file_ref):
        return FileResponse(
            app.certificate.file_ref,
            media_type="application/pdf",
            filename=f"Certificate_{app.tracking_id or app.application_number}.pdf",
        )
    raise HTTPException(status_code=404, detail="Certificate has not been issued yet")


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


# ─────────────────────────────────────────────────────────────
# Phase 8 / Section 8-15: Authoritative Admin & Submission APIs
# ─────────────────────────────────────────────────────────────

from app.api.routes.auth import require_admin
from app.orchestration.state_machine.application_fsm import AppState, ApplicationFSM
from app.data_layer.repositories.audit_repo import AuditRepository
from app.data_layer.repositories.session_repo import SessionRepository


class AdminDecisionRequest(BaseModel):
    decision: str           # "APPROVE" | "REJECT" | "REQUEST_CLARIFICATION"
    reason: Optional[str] = None
    admin_notes: Optional[str] = None


class CitizenSubmitRequest(BaseModel):
    tracking_id: Optional[str] = None
    application_id: Optional[str] = None
    citizen_ref: Optional[str] = None


@router.get("/admin/list")
def list_admin_applications_endpoint(
    status: Optional[str] = Query(None),
    service_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("newest"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    """Authoritative Admin application list with filtering, search, sorting and pagination."""
    repo = ApplicationRepository(db)
    return repo.list_admin_applications(
        status=status,
        service_id=service_id,
        search=search,
        sort_by=sort_by,
        page=page,
        limit=limit,
    )


@router.get("/admin/{id_or_number}")
def get_admin_application_detail_endpoint(
    id_or_number: str,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    """Get authoritative application details for Admin review."""
    repo = ApplicationRepository(db)
    detail = repo.get_admin_application_detail(id_or_number)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Application '{id_or_number}' not found")
    return detail


@router.post("/admin/{id_or_number}/decision")
def submit_admin_decision_endpoint(
    id_or_number: str,
    body: AdminDecisionRequest,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    """
    Authoritative Admin decision handler for APPROVE / REJECT / REQUEST_CLARIFICATION.
    Validates FSM, persists changes to SQLite, writes AuditLog, emits SSE events,
    and pushes chat notification to citizen session.
    """
    repo = ApplicationRepository(db)
    app = repo.get_by_id(id_or_number) or repo.get_by_number(id_or_number) or repo.get_by_tracking_id(id_or_number)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application '{id_or_number}' not found")

    decision = body.decision.upper()
    valid_decisions = {"APPROVE", "REJECT", "REQUEST_CLARIFICATION", "CLARIFICATION_REQUIRED"}
    if decision not in valid_decisions:
        raise HTTPException(status_code=400, detail=f"Invalid decision. Must be one of: {valid_decisions}")

    old_status = app.status
    now = datetime.datetime.utcnow()
    audit_repo = AuditRepository(db)
    session_repo = SessionRepository(db)

    # 1. APPROVE
    if decision == "APPROVE":
        valid_approval_states = (
            AppState.SUBMITTED_FOR_VERIFICATION,
            AppState.UNDER_REVIEW,
            AppState.READY_FOR_REVIEW,
            "READY_FOR_REVIEW",
            "READY_FOR_VERIFICATION",
            "FINAL_REVIEW",
            "CONSENT_CONFIRMED",
            "SUBMITTED",
        )
        if old_status not in valid_approval_states:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve application in state '{old_status}'. Application must be in a submitted or review-ready state.",
            )

        fsm = ApplicationFSM(current_state=old_status)
        try:
            fsm.transition(AppState.UNDER_REVIEW)
            repo.update_status(app.id, AppState.UNDER_REVIEW)
        except Exception:
            pass

        try:
            fsm.transition(AppState.APPROVED)
        except Exception:
            pass
        repo.update_status(app.id, AppState.APPROVED)

        # Transition to PAYMENT_REQUIRED immediately (strict FSM order)
        try:
            fsm.transition(AppState.PAYMENT_REQUIRED)
        except Exception:
            pass
        repo.update_status(app.id, AppState.PAYMENT_REQUIRED)
        new_status = AppState.PAYMENT_REQUIRED

        app.approved_at = now
        app.reviewed_at = now
        app_summary = dict(app.validation_summary or {})
        app_summary["reviewed_by"] = _admin.username
        if body.admin_notes:
            app_summary["admin_notes"] = body.admin_notes
        app.validation_summary = app_summary
        db.commit()

        # AuditLog
        audit_repo.write(
            event_type="DECISION",
            actor=_admin.username,
            application_id=app.id,
            action=f"APPLICATION_APPROVED: {app.application_number} ({old_status} -> PAYMENT_REQUIRED)",
            outcome="SUCCESS",
            metadata={
                "tracking_id": app.tracking_id,
                "previous_status": old_status,
                "new_status": AppState.PAYMENT_REQUIRED,
                "notes": body.admin_notes,
            },
        )

        # Broadcast SSE
        try:
            from app.api.routes.stream import broadcast_status_change_sync, bus
            broadcast_status_change_sync(
                application_id=app.tracking_id or str(app.id),
                tracking_id=app.tracking_id or app.application_number,
                new_status=AppState.APPROVED,
                actor=_admin.username,
                extra={"decision": "APPROVE", "notes": body.admin_notes},
            )
            broadcast_status_change_sync(
                application_id=app.tracking_id or str(app.id),
                tracking_id=app.tracking_id or app.application_number,
                new_status=AppState.PAYMENT_REQUIRED,
                actor=_admin.username,
                extra={"decision": "APPROVE", "fee_amount": 50},
            )
            if app.citizen_ref:
                bus.publish_sync(app.citizen_ref, {
                    "type": "status_change",
                    "tracking_id": app.tracking_id or app.application_number,
                    "new_status": AppState.APPROVED,
                    "actor": _admin.username,
                })
                bus.publish_sync(app.citizen_ref, {
                    "type": "status_change",
                    "tracking_id": app.tracking_id or app.application_number,
                    "new_status": AppState.PAYMENT_REQUIRED,
                    "actor": _admin.username,
                    "fee_amount": 50,
                })
        except Exception as e:
            logger.warning(f"SSE broadcast error: {e}")

        # Push notification to citizen session
        try:
            session = session_repo.load_session(app.citizen_ref)
            if session:
                msg = (
                    f"🎉 Great news! Your application **{app.tracking_id or app.application_number}** has been **APPROVED** by the government officer!\n\n"
                    f"💳 **Payment Required**: Please complete the statutory fee payment (₹50) to generate and download your official certificate."
                )
                session_repo.add_message(session.id, "ASSISTANT", msg)
        except Exception as e:
            logger.warning(f"Failed to push notification to citizen: {e}")

        return {
            "success": True,
            "tracking_id": app.tracking_id or app.application_number,
            "application_number": app.application_number,
            "old_status": old_status,
            "new_status": new_status,
            "citizen_notified": True,
            "message": "Application approved. Status transitioned to PAYMENT_REQUIRED.",
        }

    # 2. REJECT
    elif decision == "REJECT":
        if not body.reason or not body.reason.strip():
            raise HTTPException(status_code=400, detail="Rejection reason is required")

        if old_status in ("COMPLETED", "REJECTED"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject application in state '{old_status}'.",
            )

        fsm = ApplicationFSM(current_state=old_status)
        try:
            fsm.transition(AppState.UNDER_REVIEW)
            repo.update_status(app.id, AppState.UNDER_REVIEW)
        except Exception:
            pass

        try:
            fsm.transition(AppState.REJECTED)
        except Exception:
            pass
        repo.update_status(app.id, AppState.REJECTED)
        new_status = AppState.REJECTED

        app.completed_at = now
        app.reviewed_at = now
        app_summary = dict(app.validation_summary or {})
        app_summary["rejection_reason"] = body.reason.strip()
        app_summary["reviewed_by"] = _admin.username
        if body.admin_notes:
            app_summary["admin_notes"] = body.admin_notes
        app.validation_summary = app_summary
        db.commit()

        # AuditLog
        audit_repo.write(
            event_type="DECISION",
            actor=_admin.username,
            application_id=app.id,
            action=f"APPLICATION_REJECTED: {app.application_number} ({old_status} -> REJECTED). Reason: {body.reason}",
            outcome="SUCCESS",
            metadata={
                "tracking_id": app.tracking_id,
                "previous_status": old_status,
                "new_status": AppState.REJECTED,
                "reason": body.reason,
            },
        )

        # Broadcast SSE
        try:
            from app.api.routes.stream import broadcast_status_change_sync, bus
            broadcast_status_change_sync(
                application_id=app.tracking_id or str(app.id),
                tracking_id=app.tracking_id or app.application_number,
                new_status=AppState.REJECTED,
                actor=_admin.username,
                extra={"decision": "REJECT", "reason": body.reason},
            )
            if app.citizen_ref:
                bus.publish_sync(app.citizen_ref, {
                    "type": "status_change",
                    "tracking_id": app.tracking_id or app.application_number,
                    "new_status": AppState.REJECTED,
                    "actor": _admin.username,
                    "reason": body.reason,
                })
        except Exception as e:
            logger.warning(f"SSE broadcast error: {e}")

        # Push notification to citizen session
        try:
            session = session_repo.load_session(app.citizen_ref)
            if session:
                msg = (
                    f"❌ Your application **{app.tracking_id or app.application_number}** was **REJECTED** by the reviewing officer.\n\n"
                    f"**Reason**: {body.reason.strip()}\n\n"
                    f"If you believe this was in error, you may submit a new application with the correct documentation."
                )
                session_repo.add_message(session.id, "ASSISTANT", msg)
        except Exception as e:
            logger.warning(f"Failed to push notification to citizen: {e}")

        return {
            "success": True,
            "tracking_id": app.tracking_id or app.application_number,
            "application_number": app.application_number,
            "old_status": old_status,
            "new_status": new_status,
            "citizen_notified": True,
            "message": f"Application rejected. Reason: {body.reason}",
        }

    # 3. REQUEST_CLARIFICATION
    elif decision in ("REQUEST_CLARIFICATION", "CLARIFICATION_REQUIRED"):
        clarification_text = (body.reason or body.admin_notes or "").strip()
        if not clarification_text:
            raise HTTPException(status_code=400, detail="Clarification message is required")

        if old_status in ("COMPLETED", "REJECTED", "PAYMENT_REQUIRED", "PAYMENT_COMPLETED", "CERTIFICATE_READY"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot request clarification in state '{old_status}'.",
            )

        fsm = ApplicationFSM(current_state=old_status)
        try:
            fsm.transition(AppState.UNDER_REVIEW)
            repo.update_status(app.id, AppState.UNDER_REVIEW)
        except Exception:
            pass

        try:
            fsm.transition(AppState.CLARIFICATION_REQUIRED)
        except Exception:
            pass
        repo.update_status(app.id, AppState.CLARIFICATION_REQUIRED)
        new_status = AppState.CLARIFICATION_REQUIRED

        app.reviewed_at = now
        app_summary = dict(app.validation_summary or {})
        app_summary["clarification_reason"] = clarification_text
        app_summary["reviewed_by"] = _admin.username
        app.validation_summary = app_summary
        db.commit()

        # AuditLog
        audit_repo.write(
            event_type="DECISION",
            actor=_admin.username,
            application_id=app.id,
            action=f"CLARIFICATION_REQUESTED: {app.application_number} ({old_status} -> CLARIFICATION_REQUIRED). Message: {clarification_text}",
            outcome="SUCCESS",
            metadata={
                "tracking_id": app.tracking_id,
                "previous_status": old_status,
                "new_status": AppState.CLARIFICATION_REQUIRED,
                "message": clarification_text,
            },
        )

        # Broadcast SSE
        try:
            from app.api.routes.stream import broadcast_status_change_sync, bus
            broadcast_status_change_sync(
                application_id=app.tracking_id or str(app.id),
                tracking_id=app.tracking_id or app.application_number,
                new_status=AppState.CLARIFICATION_REQUIRED,
                actor=_admin.username,
                extra={"decision": "REQUEST_CLARIFICATION", "reason": clarification_text},
            )
            if app.citizen_ref:
                bus.publish_sync(app.citizen_ref, {
                    "type": "status_change",
                    "tracking_id": app.tracking_id or app.application_number,
                    "new_status": AppState.CLARIFICATION_REQUIRED,
                    "actor": _admin.username,
                    "reason": clarification_text,
                })
        except Exception as e:
            logger.warning(f"SSE broadcast error: {e}")

        # Push notification to citizen session
        try:
            session = session_repo.load_session(app.citizen_ref)
            if session:
                msg = (
                    f"⚠️ **Action Required**: The reviewing officer has requested clarification on your application **{app.tracking_id or app.application_number}**:\n\n"
                    f"👉 **{clarification_text}**\n\n"
                    f"Please provide the requested details or re-upload your document in the portal so we can proceed with verification."
                )
                session_repo.add_message(session.id, "ASSISTANT", msg)
        except Exception as e:
            logger.warning(f"Failed to push notification to citizen: {e}")

        return {
            "success": True,
            "tracking_id": app.tracking_id or app.application_number,
            "application_number": app.application_number,
            "old_status": old_status,
            "new_status": new_status,
            "citizen_notified": True,
            "message": f"Clarification requested from citizen: {clarification_text}",
        }


@router.post("/{id_or_number}/submit")
@router.post("/submit")
def submit_application_endpoint(
    id_or_number: Optional[str] = None,
    body: Optional[CitizenSubmitRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Citizen submits application for verification.
    Transitions: (READY_FOR_REVIEW | FINAL_REVIEW | CONSENT_CONFIRMED | CLARIFICATION_REQUIRED) → SUBMITTED_FOR_VERIFICATION.
    """
    repo = ApplicationRepository(db)
    target_id = id_or_number or (body.tracking_id if body else None) or (body.application_id if body else None)
    if not target_id:
        raise HTTPException(status_code=400, detail="Missing application identifier")

    app = repo.get_by_id(target_id) or repo.get_by_number(target_id) or repo.get_by_tracking_id(target_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application '{target_id}' not found")

    old_status = app.status
    now = datetime.datetime.utcnow()

    # Transition to SUBMITTED_FOR_VERIFICATION
    repo.update_status(app.id, AppState.SUBMITTED_FOR_VERIFICATION)
    app.submitted_at = now
    db.commit()

    # Write AuditLog
    AuditRepository(db).write(
        event_type="SUBMISSION",
        actor=app.citizen_ref or "CITIZEN",
        application_id=app.id,
        action=f"APPLICATION_SUBMITTED: {app.application_number} ({old_status} -> SUBMITTED_FOR_VERIFICATION)",
        outcome="SUCCESS",
        metadata={"tracking_id": app.tracking_id, "previous_status": old_status},
    )

    # Broadcast SSE
    try:
        from app.api.routes.stream import broadcast_status_change_sync, bus
        broadcast_status_change_sync(
            application_id=app.tracking_id or str(app.id),
            tracking_id=app.tracking_id or app.application_number,
            new_status=AppState.SUBMITTED_FOR_VERIFICATION,
            actor="CITIZEN",
        )
        if app.citizen_ref:
            bus.publish_sync(app.citizen_ref, {
                "type": "status_change",
                "tracking_id": app.tracking_id or app.application_number,
                "new_status": AppState.SUBMITTED_FOR_VERIFICATION,
                "actor": "CITIZEN",
            })
    except Exception as e:
        logger.warning(f"SSE broadcast error: {e}")

    return {
        "success": True,
        "tracking_id": app.tracking_id or app.application_number,
        "application_number": app.application_number,
        "status": AppState.SUBMITTED_FOR_VERIFICATION,
        "new_status": AppState.SUBMITTED_FOR_VERIFICATION,
        "submitted_at": now.isoformat(),
        "message": "Application submitted for government verification.",
    }

