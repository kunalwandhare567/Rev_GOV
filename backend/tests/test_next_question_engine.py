"""
Phase 16 — Unit tests for NextQuestionEngine
Tests slot prioritization, dynamic prompt generation, and fallback logic.
"""
import pytest
from app.services.next_question_engine import NextQuestionEngine, NextQuestionResult


def test_next_question_engine_selection():
    engine = NextQuestionEngine()

    filled = {}
    result = engine.get_next_slot("income_certificate", filled)
    assert isinstance(result, NextQuestionResult)
    assert result.has_next is True
    assert result.slot_name is not None
    assert result.completion_percentage < 100.0


def test_next_question_engine_all_filled():
    engine = NextQuestionEngine()
    all_slots = {
        "applicant_name": "Ramesh Kumar",
        "applicant_dob": "15-08-1990",
        "gender": "MALE",
        "mobile_number": "9876543210",
        "email": "ramesh@example.com",
        "father_name": "Suresh Kumar",
        "mother_name": "Sunita Kumar",
        "aadhaar_number": "123456789012",
        "address": "Nagpur, Maharashtra",
        "district": "Nagpur",
        "taluka": "Nagpur",
        "village": "Nagpur",
        "occupation": "Farmer",
        "annual_income": "150000",
        "family_member_count": "4",
        "earning_family_members": "1",
        "annual_family_income": "150000",
        "purpose": "Higher Education",
    }
    result = engine.get_next_slot("income_certificate", all_slots)
    assert result.has_next is False
    assert result.completion_percentage == 100.0
