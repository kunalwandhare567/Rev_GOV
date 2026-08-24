"""
Phase 16 — Unit tests for Cross-Question Digression Handling in Orchestrator
"""
import pytest
from unittest.mock import MagicMock
from app.orchestration.state_machine.orchestrator import ConversationOrchestrator


def test_cross_question_detection():
    # Pass dummy DB mock
    orchestrator = ConversationOrchestrator(db=MagicMock())

    # Question/FAQ style inputs
    assert orchestrator._is_cross_question("why do you need father's name?") is True
    assert orchestrator._is_cross_question("what documents are required?") is True
    assert orchestrator._is_cross_question("how long does it take?") is True
    assert orchestrator._is_cross_question("what is the fee?") is True

    # Normal slot responses
    assert orchestrator._is_cross_question("Ramesh Kumar") is False
    assert orchestrator._is_cross_question("150000") is False
    assert orchestrator._is_cross_question("9876543210") is False
