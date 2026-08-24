"""
Phase 16 — Unit tests for Mock Government Adapter & Decision logic
"""
import pytest
from unittest.mock import MagicMock
from app.api.routes.mock_government import (
    SimulateDecisionRequest,
    SubmitApplicationRequest,
)


def test_simulate_decision_request_model():
    req = SimulateDecisionRequest(
        tracking_id="INC-2026-000001",
        decision="APPROVE",
        reason="All documents valid",
    )
    assert req.tracking_id == "INC-2026-000001"
    assert req.decision == "APPROVE"
    assert req.reason == "All documents valid"


def test_submit_application_request_model():
    req = SubmitApplicationRequest(
        tracking_id="INC-2026-000001",
        citizen_ref="cit_12345",
    )
    assert req.tracking_id == "INC-2026-000001"
    assert req.citizen_ref == "cit_12345"
