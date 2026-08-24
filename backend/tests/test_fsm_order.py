"""
Phase 16 — Unit tests for FSM state sequence ordering
Ensures state transitions strictly follow:
INITIATED → CONSENT_GIVEN → SERVICE_SELECTED → INFORMATION_COLLECTION →
DOCUMENT_COLLECTION → OCR_PROCESSING → VALIDATION_COMPLETED →
READINESS_CHECK → READY_FOR_REVIEW → FINAL_REVIEW → CONSENT_CONFIRMED →
SUBMITTED_FOR_VERIFICATION → UNDER_REVIEW → APPROVED → PAYMENT_REQUIRED →
PAYMENT_COMPLETED → CERTIFICATE_GENERATION → CERTIFICATE_READY → COMPLETED
"""
import pytest
from app.orchestration.state_machine.application_fsm import ApplicationFSM, AppState


def test_payment_only_after_approved():
    """Verify PAYMENT_REQUIRED is ONLY reachable from APPROVED."""
    fsm = ApplicationFSM(AppState.UNDER_REVIEW)
    ok, _ = fsm.transition(AppState.PAYMENT_REQUIRED)
    assert ok is False, "PAYMENT_REQUIRED should not be directly reachable from UNDER_REVIEW without APPROVED"

    fsm = ApplicationFSM(AppState.UNDER_REVIEW)
    ok, _ = fsm.transition(AppState.APPROVED)
    assert ok is True
    ok2, _ = fsm.transition(AppState.PAYMENT_REQUIRED)
    assert ok2 is True, "PAYMENT_REQUIRED should be reachable from APPROVED"


def test_certificate_only_after_payment():
    """Verify CERTIFICATE_GENERATION is ONLY reachable from PAYMENT_COMPLETED."""
    fsm = ApplicationFSM(AppState.PAYMENT_REQUIRED)
    ok, _ = fsm.transition(AppState.CERTIFICATE_GENERATION)
    assert ok is False

    fsm = ApplicationFSM(AppState.PAYMENT_COMPLETED)
    ok, _ = fsm.transition(AppState.CERTIFICATE_GENERATION)
    assert ok is True
