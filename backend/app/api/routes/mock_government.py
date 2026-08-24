"""
Phase 8 — Mock Government Adapter API Routes

Simulates the government verification workflow for POC purposes.
In production, this would be replaced by a real government API integration.

Endpoints:
  POST /api/v1/mock-government/simulate-decision
      Admin clicks Approve / Request Clarification / Reject
      → transitions application FSM
      → notifies citizen via chat message + SSE broadcast

  POST /api/v1/mock-government/submit
      Called when citizen submits after CONSENT_CONFIRMED
      → transitions CONSENT_CONFIRMED → SUBMITTED → UNDER_REVIEW

  GET /api/v1/mock-government/status/{tracking_id}
      Returns current status info for admin display

Rules:
  - Approval ONLY allowed from UNDER_REVIEW state
  - PAYMENT_REQUIRED is ONLY reachable from APPROVED (never directly from admin)
  - All decisions are logged to audit trail
"""
import logging
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.session_repo import SessionRepository
from app.data_layer.repositories.audit_repo import AuditRepository
from app.orchestration.state_machine.application_fsm import AppState, ApplicationFSM

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mock-government", tags=["Mock Government"])


# ─────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────

class SimulateDecisionRequest(BaseModel):
    tracking_id: str
    decision: str           # "APPROVE" | "REJECT" | "CLARIFICATION_REQUIRED"
    reason: Optional[str] = None
    admin_notes: Optional[str] = None

class SimulateDecisionResponse(BaseModel):
    success: bool
    tracking_id: str
    old_status: str
    new_status: str
    citizen_notified: bool
    message: str

class SubmitApplicationRequest(BaseModel):
    tracking_id: str
    citizen_ref: str

class SubmitApplicationResponse(BaseModel):
    success: bool
    tracking_id: str
    new_status: str
    message: str


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _notify_citizen(
    session_repo: SessionRepository,
    citizen_ref: str,
    message: str,
    db: Session
) -> bool:
    """Store a system notification in the citizen's chat session."""
    try:
        session = session_repo.load_session(citizen_ref)
        if session:
            session_repo.add_message(
                session_id=session.id,
                role="ASSISTANT",
                content=message,
                language=getattr(session, "language", "en"),
                modality="TEXT",
            )
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to notify citizen {citizen_ref}: {e}")
        return False


def _broadcast_sse(
    tracking_id: str,
    new_status: str,
    citizen_ref: str = None,
    extra: dict = None,
):
    """
    Phase 13 — Broadcast status change via SSE stream.
    Publishes to BOTH tracking_id AND citizen_ref channels so:
      - Application-level subscriptions get updated
      - CitizenChat's citizen-level subscription gets the push notification
    """
    try:
        from app.api.routes.stream import broadcast_status_change_sync
        broadcast_status_change_sync(
            application_id=tracking_id,  # re-used as key
            tracking_id=tracking_id,
            new_status=new_status,
            actor="ADMIN",
            extra=extra or {},
        )
        # Also broadcast to citizen SSE channel
        if citizen_ref:
            from app.api.routes.stream import bus
            event = {
                "type": "status_change",
                "tracking_id": tracking_id,
                "new_status": new_status,
                "actor": "ADMIN",
                **(extra or {}),
            }
            bus.publish_sync(citizen_ref, event)
    except Exception as e:
        logger.warning(f"SSE broadcast failed: {e}")


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@router.post("/simulate-decision", response_model=SimulateDecisionResponse)
def simulate_government_decision(
    req: SimulateDecisionRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """
    Admin simulates a government decision on an application.
    APPROVAL: UNDER_REVIEW → APPROVED → PAYMENT_REQUIRED
    REJECTION: UNDER_REVIEW → REJECTED
    CLARIFICATION: UNDER_REVIEW → CLARIFICATION_REQUIRED

    Rule: Payment is ONLY triggered by APPROVED state. Never directly by admin.
    """
    app_repo = ApplicationRepository(db)
    session_repo = SessionRepository(db)
    audit_repo = AuditRepository(db)

    # Load application
    app = app_repo.get_by_tracking_id(req.tracking_id)
    if not app:
        raise HTTPException(404, f"Application not found: {req.tracking_id}")

    old_status = app.status

    # Validate: decision can only be made from UNDER_REVIEW
    if old_status != AppState.UNDER_REVIEW:
        raise HTTPException(400, (
            f"Decision can only be made from UNDER_REVIEW state. "
            f"Current state: {old_status}. "
            f"Hint: Submit the application first."
        ))

    decision = req.decision.upper()
    valid_decisions = {"APPROVE", "REJECT", "CLARIFICATION_REQUIRED"}
    if decision not in valid_decisions:
        raise HTTPException(400, f"Decision must be one of: {valid_decisions}")

    # Apply FSM transition
    fsm = ApplicationFSM(current_state=old_status)

    if decision == "APPROVE":
        # UNDER_REVIEW → APPROVED → PAYMENT_REQUIRED
        success, msg = fsm.transition(AppState.APPROVED)
        if not success:
            raise HTTPException(400, f"FSM error: {msg}")

        app_repo.update_status(app.id, AppState.APPROVED)

        # Immediately trigger payment requirement (correct FSM flow)
        success2, msg2 = fsm.transition(AppState.PAYMENT_REQUIRED)
        if success2:
            app_repo.update_status(app.id, AppState.PAYMENT_REQUIRED)

        new_status = AppState.PAYMENT_REQUIRED

        # Notify citizen
        fee_amount = getattr(app, "fee_amount", 50)
        citizen_msg = (
            f"🎉 Great news! Your application **{req.tracking_id}** has been APPROVED by the government!\n\n"
            f"💳 To receive your certificate, please complete the payment of ₹{fee_amount}.\n"
            f"Visit the portal or type 'pay now' to proceed."
        )

    elif decision == "REJECT":
        success, msg = fsm.transition(AppState.REJECTED)
        if not success:
            raise HTTPException(400, f"FSM error: {msg}")

        app_repo.update_status(app.id, AppState.REJECTED)
        new_status = AppState.REJECTED

        reason = req.reason or "Application did not meet the required criteria."
        citizen_msg = (
            f"❌ We regret to inform you that your application **{req.tracking_id}** "
            f"has been rejected by the Revenue Department.\n\n"
            f"**Reason:** {reason}\n\n"
            f"You may reapply after 30 days with corrected information."
        )

    elif decision == "CLARIFICATION_REQUIRED":
        success, msg = fsm.transition(AppState.CLARIFICATION_REQUIRED)
        if not success:
            raise HTTPException(400, f"FSM error: {msg}")

        app_repo.update_status(app.id, AppState.CLARIFICATION_REQUIRED)
        new_status = AppState.CLARIFICATION_REQUIRED

        notes = req.admin_notes or req.reason or "Additional information is needed."
        citizen_msg = (
            f"📝 The Revenue Department has reviewed your application **{req.tracking_id}** "
            f"and requires additional clarification:\n\n"
            f"**What's needed:** {notes}\n\n"
            f"Please provide the requested information to continue."
        )

    else:
        raise HTTPException(400, "Invalid decision")

    # Notify citizen via chat
    citizen_ref = getattr(app, "citizen_ref", None) or getattr(app, "citizen_identifier", None)
    citizen_notified = False
    if citizen_ref:
        citizen_notified = _notify_citizen(session_repo, citizen_ref, citizen_msg, db)

    # Audit log
    try:
        audit_repo.write(
            event_type="GOVERNMENT_DECISION",
            actor="ADMIN",
            citizen_ref=citizen_ref,
            action=f"Simulated government decision: {decision}",
            outcome="SUCCESS",
            metadata={
                "tracking_id": req.tracking_id,
                "decision": decision,
                "reason": req.reason,
                "old_status": old_status,
                "new_status": new_status,
                "admin_notes": req.admin_notes,
                "timestamp": datetime.datetime.utcnow().isoformat(),
            },
        )
    except Exception as e:
        logger.warning(f"Audit write failed: {e}")

    # SSE broadcast (Phase 13: sends to both tracking_id + citizen_ref)
    _broadcast_sse(
        tracking_id=req.tracking_id,
        new_status=new_status,
        citizen_ref=citizen_ref,
        extra={"decision": decision, "reason": req.reason},
    )

    logger.info(
        f"Mock Government Decision: {req.tracking_id} {old_status} → {new_status} "
        f"[{decision}] citizen_notified={citizen_notified}"
    )

    return SimulateDecisionResponse(
        success=True,
        tracking_id=req.tracking_id,
        old_status=old_status,
        new_status=new_status,
        citizen_notified=citizen_notified,
        message=f"Decision '{decision}' applied. Application moved to {new_status}.",
    )


@router.post("/submit", response_model=SubmitApplicationResponse)
def submit_application(
    req: SubmitApplicationRequest,
    db: Session = Depends(get_db),
):
    """
    Citizen submits application after giving consent.
    Transitions: CONSENT_CONFIRMED → SUBMITTED_FOR_VERIFICATION → UNDER_REVIEW
    """
    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_tracking_id(req.tracking_id)

    if not app:
        raise HTTPException(404, f"Application not found: {req.tracking_id}")

    current = app.status
    if current not in (AppState.CONSENT_CONFIRMED, AppState.READY_FOR_REVIEW):
        raise HTTPException(400, (
            f"Application must be in CONSENT_CONFIRMED state to submit. "
            f"Current: {current}"
        ))

    # Transition to SUBMITTED → UNDER_REVIEW
    fsm = ApplicationFSM(current_state=current)

    if current == AppState.READY_FOR_REVIEW:
        fsm.transition(AppState.FINAL_REVIEW)
        app_repo.update_status(app.id, AppState.FINAL_REVIEW)
        fsm.transition(AppState.CONSENT_CONFIRMED)
        app_repo.update_status(app.id, AppState.CONSENT_CONFIRMED)

    fsm.transition(AppState.SUBMITTED_FOR_VERIFICATION)
    app_repo.update_status(app.id, AppState.SUBMITTED_FOR_VERIFICATION)
    fsm.transition(AppState.UNDER_REVIEW)
    app_repo.update_status(app.id, AppState.UNDER_REVIEW)

    logger.info(f"Application submitted: {req.tracking_id} → UNDER_REVIEW")

    return SubmitApplicationResponse(
        success=True,
        tracking_id=req.tracking_id,
        new_status=AppState.UNDER_REVIEW,
        message="Application submitted successfully and is now under government review.",
    )


@router.get("/status/{tracking_id}")
def get_application_status_for_admin(
    tracking_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Get full application status for admin review panel."""
    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_tracking_id(tracking_id)

    if not app:
        raise HTTPException(404, f"Application not found: {tracking_id}")

    return {
        "tracking_id": tracking_id,
        "current_status": app.status,
        "service_id": getattr(app, "service_id", None),
        "citizen_ref": getattr(app, "citizen_ref", None),
        "submitted_at": str(getattr(app, "submitted_at", None) or getattr(app, "updated_at", "")),
        "created_at": str(getattr(app, "created_at", "")),
        "can_decide": app.status == AppState.UNDER_REVIEW,
        "allowed_decisions": ["APPROVE", "REJECT", "CLARIFICATION_REQUIRED"]
            if app.status == AppState.UNDER_REVIEW else [],
        "application_number": getattr(app, "application_number", tracking_id),
        "fee_amount": getattr(app, "fee_amount", 50),
    }
