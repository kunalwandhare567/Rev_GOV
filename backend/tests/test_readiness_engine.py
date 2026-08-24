"""
Phase 16 — Unit tests for ReadinessEngine
"""
import pytest
from app.services.readiness_engine import ReadinessEngine, ReadinessResult


def test_readiness_score_empty():
    engine = ReadinessEngine()
    result = engine.compute(
        service_id="income_certificate",
        filled_slots={},
        required_slots=["applicant_name", "annual_income"],
        required_docs=["IDENTITY_PROOF", "INCOME_PROOF"],
        uploaded_docs=[],
    )
    assert isinstance(result, ReadinessResult)
    assert result.overall_score < 75.0
    assert result.can_submit is False


def test_readiness_score_full():
    engine = ReadinessEngine()
    required_slots = [
        "applicant_name", "applicant_dob", "gender", "mobile_number",
        "aadhaar_number", "address", "annual_income"
    ]
    filled_slots = {
        "applicant_name": "Ramesh Kumar",
        "applicant_dob": "15-08-1990",
        "gender": "MALE",
        "mobile_number": "9876543210",
        "aadhaar_number": "123456789012",
        "address": "Nagpur, Maharashtra",
        "annual_income": "150000",
    }
    required_docs = ["IDENTITY_PROOF", "INCOME_PROOF"]
    uploaded_docs = ["IDENTITY_PROOF", "INCOME_PROOF"]
    ocr_results = [
        {"doc_type": "IDENTITY_PROOF", "status": "VALIDATED", "overall_match_score": 95},
        {"doc_type": "INCOME_PROOF", "status": "VALIDATED", "overall_match_score": 90},
    ]
    eligibility_result = {"eligible": True, "reason": "Eligible"}

    result = engine.compute(
        service_id="income_certificate",
        filled_slots=filled_slots,
        required_slots=required_slots,
        required_docs=required_docs,
        uploaded_docs=uploaded_docs,
        ocr_results=ocr_results,
        eligibility_result=eligibility_result,
    )
    assert result.overall_score >= 75.0
    assert result.can_submit is True
