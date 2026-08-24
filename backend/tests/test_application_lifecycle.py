"""
Phase 15 (final) — Application Lifecycle Tests
Tests the 14-state ApplicationFSM: valid transitions, invalid blocking,
progress tracking, citizen messages, and integration with the DB status field.
"""
import pytest
from app.orchestration.state_machine.application_fsm import (
    ApplicationFSM, AppState, STATE_PROGRESS, VALID_TRANSITIONS,
    get_fsm_for_app, CITIZEN_MESSAGES,
)


class TestApplicationFSM:

    def test_initial_state(self):
        fsm = ApplicationFSM()
        assert fsm.current_state == AppState.INITIATED
        assert fsm.progress == STATE_PROGRESS[AppState.INITIATED]
        assert not fsm.is_terminal
        assert not fsm.is_complete

    def test_valid_linear_path_to_approved(self):
        """Walk through the happy path: INITIATED → CERTIFICATE_READY."""
        happy_path = [
            AppState.CONSENT_GIVEN,
            AppState.SERVICE_SELECTED,
            AppState.COLLECTING_DATA,
            AppState.ELIGIBILITY_CHECK,
            AppState.DOCUMENTS_REQUESTED,
            AppState.DOCUMENTS_UPLOADED,
            AppState.OCR_PROCESSING,
            AppState.PAYMENT_PENDING,
            AppState.PAYMENT_COMPLETED,
            AppState.SUBMITTED_FOR_VERIFICATION,
            AppState.UNDER_REVIEW,
            AppState.APPROVED,
            AppState.CERTIFICATE_READY,
        ]
        fsm = ApplicationFSM()
        for state in happy_path:
            ok, msg = fsm.transition(state)
            assert ok, f"Expected valid transition to {state}, got: {msg}"
        assert fsm.current_state == AppState.CERTIFICATE_READY
        assert fsm.is_complete
        assert fsm.progress == 100

    def test_valid_path_to_rejected(self):
        fsm = ApplicationFSM()
        for s in [AppState.CONSENT_GIVEN, AppState.SERVICE_SELECTED,
                  AppState.COLLECTING_DATA, AppState.ELIGIBILITY_CHECK]:
            fsm.transition(s)
        ok, msg = fsm.transition(AppState.REJECTED)
        assert ok
        assert fsm.is_terminal
        assert not fsm.is_complete

    def test_valid_escalation_path(self):
        fsm = ApplicationFSM()
        for s in [AppState.CONSENT_GIVEN, AppState.SERVICE_SELECTED,
                  AppState.COLLECTING_DATA, AppState.ELIGIBILITY_CHECK,
                  AppState.DOCUMENTS_REQUESTED, AppState.DOCUMENTS_UPLOADED,
                  AppState.OCR_PROCESSING, AppState.PAYMENT_PENDING,
                  AppState.PAYMENT_COMPLETED, AppState.SUBMITTED_FOR_VERIFICATION,
                  AppState.UNDER_REVIEW, AppState.ESCALATED]:
            ok, msg = fsm.transition(s)
            assert ok, f"Failed at {s}: {msg}"
        assert fsm.current_state == AppState.ESCALATED

    def test_invalid_transition_blocked(self):
        """Cannot skip from INITIATED → APPROVED."""
        fsm = ApplicationFSM()
        ok, msg = fsm.transition(AppState.APPROVED)
        assert not ok
        assert "Invalid transition" in msg

    def test_cannot_exit_terminal_state(self):
        """Terminal state CERTIFICATE_READY has no outgoing transitions."""
        fsm = ApplicationFSM(AppState.CERTIFICATE_READY)
        ok, msg = fsm.transition(AppState.INITIATED)
        assert not ok
        assert fsm.current_state == AppState.CERTIFICATE_READY

    def test_cannot_exit_rejected_terminal(self):
        fsm = ApplicationFSM(AppState.REJECTED)
        ok, _ = fsm.transition(AppState.APPROVED)
        assert not ok

    def test_same_state_transition_is_ok(self):
        """Transitioning to the same state is a no-op (already there)."""
        fsm = ApplicationFSM()
        ok, msg = fsm.transition(AppState.INITIATED)
        assert ok
        assert "Already" in msg

    def test_progress_increases_monotonically(self):
        """Progress should generally increase along the happy path."""
        happy_path = [
            AppState.CONSENT_GIVEN, AppState.SERVICE_SELECTED,
            AppState.COLLECTING_DATA, AppState.ELIGIBILITY_CHECK,
            AppState.DOCUMENTS_REQUESTED, AppState.DOCUMENTS_UPLOADED,
            AppState.OCR_PROCESSING, AppState.PAYMENT_PENDING,
            AppState.PAYMENT_COMPLETED, AppState.SUBMITTED_FOR_VERIFICATION,
            AppState.UNDER_REVIEW, AppState.APPROVED, AppState.CERTIFICATE_READY,
        ]
        fsm = ApplicationFSM()
        prev_progress = fsm.progress
        for state in happy_path:
            fsm.transition(state)
            assert fsm.progress >= prev_progress, (
                f"Progress decreased at {state}: {prev_progress} → {fsm.progress}"
            )
            prev_progress = fsm.progress

    def test_all_states_have_progress_defined(self):
        """Every AppState must have a progress percentage defined."""
        for state in AppState:
            assert state in STATE_PROGRESS, f"State {state} missing from STATE_PROGRESS"
            progress = STATE_PROGRESS[state]
            assert 0 <= progress <= 100, f"Progress for {state} out of range: {progress}"

    def test_all_states_have_valid_transitions_defined(self):
        """Every AppState must appear in VALID_TRANSITIONS."""
        for state in AppState:
            assert state in VALID_TRANSITIONS, f"State {state} missing from VALID_TRANSITIONS"

    def test_citizen_messages_have_english_fallback(self):
        """Every state with citizen messages must have English."""
        for state, messages in CITIZEN_MESSAGES.items():
            assert "en" in messages, f"State {state} missing English citizen message"

    def test_citizen_message_in_hindi(self):
        fsm = ApplicationFSM(AppState.APPROVED)
        msg = fsm.get_citizen_message("hi")
        assert msg  # Not empty
        assert "बधाई" in msg or "स्वीकृत" in msg or "APPROVED" not in msg

    def test_citizen_message_in_marathi(self):
        fsm = ApplicationFSM(AppState.DOCUMENTS_REQUESTED)
        msg = fsm.get_citizen_message("mr")
        assert msg
        # Should contain Marathi text
        assert any(ord(c) > 127 for c in msg), "Marathi message should contain non-ASCII chars"

    def test_next_states_correct(self):
        fsm = ApplicationFSM(AppState.UNDER_REVIEW)
        next_states = fsm.get_next_states()
        assert AppState.APPROVED in next_states
        assert AppState.REJECTED in next_states
        assert AppState.ESCALATED in next_states

    def test_get_fsm_for_app_helper(self):
        """get_fsm_for_app() creates FSM from ORM-like object."""
        class FakeApp:
            status = AppState.PAYMENT_PENDING
        fsm = get_fsm_for_app(FakeApp())
        assert fsm.current_state == AppState.PAYMENT_PENDING
        assert fsm.progress == STATE_PROGRESS[AppState.PAYMENT_PENDING]

    def test_to_dict_structure(self):
        fsm = ApplicationFSM(AppState.UNDER_REVIEW)
        d = fsm.to_dict()
        assert d["state"] == AppState.UNDER_REVIEW
        assert d["progress"] == STATE_PROGRESS[AppState.UNDER_REVIEW]
        assert "next_states" in d
        assert "is_terminal" in d

    def test_ocr_failure_can_go_back_to_documents(self):
        """OCR failure path: OCR_PROCESSING → DOCUMENTS_REQUESTED."""
        fsm = ApplicationFSM(AppState.OCR_PROCESSING)
        ok, _ = fsm.transition(AppState.DOCUMENTS_REQUESTED)
        assert ok

    def test_payment_cannot_be_skipped(self):
        """Cannot go from PAYMENT_PENDING to SUBMITTED_FOR_VERIFICATION."""
        fsm = ApplicationFSM(AppState.PAYMENT_PENDING)
        ok, _ = fsm.transition(AppState.SUBMITTED_FOR_VERIFICATION)
        assert not ok

    def test_full_state_coverage(self):
        """Ensure all 16 states (including terminal) are reachable."""
        reachable = {AppState.INITIATED}
        for from_state, to_states in VALID_TRANSITIONS.items():
            for s in to_states:
                reachable.add(s)
        all_states = set(AppState)
        unreachable = all_states - reachable
        # Only INITIATED is "bootstrap" (not a target of any transition)
        # All others must be reachable
        assert not unreachable, f"Unreachable states: {unreachable}"


class TestFieldCorrector:
    """Test FieldCorrector auto-correction logic."""

    def setup_method(self):
        from app.orchestration.nlu.field_corrector import FieldCorrector
        self.fc = FieldCorrector()

    def test_aadhaar_removes_spaces(self):
        v, corrected, note = self.fc.correct("aadhaar_number", "1234 5678 9012")
        assert v == "123456789012"
        assert corrected

    def test_phone_removes_country_code(self):
        v, corrected, note = self.fc.correct("phone_number", "+919876543210")
        assert v == "9876543210"
        assert corrected

    def test_income_lakh_expansion(self):
        v, corrected, note = self.fc.correct("annual_income", "1.5 lakh")
        assert v == "150000"
        assert corrected

    def test_income_k_expansion(self):
        v, corrected, note = self.fc.correct("annual_income", "50k")
        assert v == "50000"
        assert corrected

    def test_income_comma_removal(self):
        v, corrected, note = self.fc.correct("annual_income", "1,50,000")
        assert v == "150000"
        assert corrected

    def test_date_slash_to_dash(self):
        v, corrected, note = self.fc.correct("date_of_birth", "15/01/1990")
        assert v == "15-01-1990"
        assert corrected

    def test_date_iso_to_ddmmyyyy(self):
        v, corrected, note = self.fc.correct("date_of_birth", "1990-01-15")
        assert v == "15-01-1990"
        assert corrected

    def test_date_already_correct(self):
        v, corrected, note = self.fc.correct("date_of_birth", "15-01-1990")
        assert v == "15-01-1990"
        assert not corrected

    def test_gender_normalization(self):
        v, corrected, note = self.fc.correct("gender", "male")
        assert v == "MALE"

    def test_caste_normalization(self):
        v, corrected, note = self.fc.correct("caste_category", "obc")
        assert v == "OBC"

    def test_name_title_case(self):
        v, corrected, note = self.fc.correct("applicant_name", "ramesh kumar")
        assert v == "Ramesh Kumar"

    def test_hindi_digits_converted(self):
        from app.orchestration.nlu.field_corrector import FieldCorrector
        fc = FieldCorrector()
        v, _, _ = fc.correct("phone_number", "९८७६५४३२१०")
        assert v == "9876543210"

    def test_correct_all(self):
        fields = {
            "aadhaar_number": "1234 5678 9012",
            "annual_income": "2 lakh",
            "date_of_birth": "15/06/1995",
        }
        results = self.fc.correct_all(fields)
        assert results["aadhaar_number"]["value"] == "123456789012"
        assert results["annual_income"]["value"] == "200000"
        assert results["date_of_birth"]["value"] == "15-06-1995"
