"""
Tests for OCR Normalization, Robust Matching, Session Recovery, and OpenRouter Error Handling.
Specification Reference: Rev_GOV Phase 24 Tests.
"""
import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from app.core.database import get_db, SessionLocal
from app.services.matching_service import MatchingService
from app.services.ocr_service import OCRService, OCRResult
from app.llm.openrouter_provider import OpenRouterProvider
from app.llm.exceptions import LLMUnavailableError
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.session_repo import SessionRepository
from app.models.db_models import Citizen, Application, ConversationSession, Document


client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# 1. OCR Noise & Robust Matching Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_01_noisy_ocr_name_matching():
    """Declared 'Viki Bhausaheb Lokhande' matching noisy OCR 'Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga' must be >= 90%."""
    matcher = MatchingService()
    declared = "Viki Bhausaheb Lokhande"
    noisy_ocr = "Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga"

    result = matcher.compare_fields(declared, noisy_ocr, "applicant_name")
    assert result.match is True, f"Expected match=True, got {result.match} (score={result.score})"
    assert result.score >= 90.0, f"Expected score >= 90.0, got {result.score}"


def test_02_true_name_mismatch():
    """Declared 'Viki Bhausaheb Lokhande' vs OCR 'Rahul Kumar' must be MISMATCH (< 50%)."""
    matcher = MatchingService()
    declared = "Viki Bhausaheb Lokhande"
    wrong_ocr = "Rahul Kumar"

    result = matcher.compare_fields(declared, wrong_ocr, "applicant_name")
    assert result.match is False
    assert result.score < 50.0, f"Expected low score for different name, got {result.score}"


def test_03_field_specific_matching():
    """Field-specific matching for DOB, Aadhaar, PAN, Income, Address."""
    matcher = MatchingService()

    # DOB: 15/06/2000 vs 2000-06-15
    dob_res = matcher.compare_fields("15/06/2000", "2000-06-15", "dob")
    assert dob_res.match is True
    assert dob_res.score == 100.0

    # Aadhaar: formatted vs unformatted
    aadhaar_res = matcher.compare_fields("1234 5678 9012", "123456789012", "aadhaar_number")
    assert aadhaar_res.match is True
    assert aadhaar_res.score == 100.0

    # PAN: exact uppercase alphanumeric
    pan_res = matcher.compare_fields("abcde1234f", "ABCDE1234F", "pan_number")
    assert pan_res.match is True
    assert pan_res.score == 100.0

    # Income: numeric comparison (₹ 2,50,000 vs 250000)
    income_res = matcher.compare_fields("₹ 2,50,000", "250000", "annual_income")
    assert income_res.match is True
    assert income_res.score == 100.0


def test_04_missing_ocr_values_remain_null():
    """OpenRouter normalization must return null for missing fields without inventing data."""
    provider = OpenRouterProvider()

    with patch.object(provider, "_call", return_value='''```json
    {
      "normalized_fields": {
        "applicant_name": "Viki Bhausaheb Lokhande",
        "dob": null,
        "gender": null,
        "aadhaar_number": null,
        "pan_number": null,
        "annual_income": null,
        "address": null
      },
      "confidence": {"applicant_name": 0.95},
      "corrections": []
    }
    ```'''):
        norm = provider.normalize_ocr_fields("Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga", {}, "AADHAAR_CARD")
        fields = norm.get("normalized_fields", {})
        assert fields.get("applicant_name") == "Viki Bhausaheb Lokhande"
        assert fields.get("dob") is None
        assert fields.get("aadhaar_number") is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Session Recovery & Authority Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_05_active_session_reuse():
    """If an active session exists for a citizen, it must be reused."""
    db = SessionLocal()
    try:
        citizen_repo = CitizenRepository(db)
        session_repo = SessionRepository(db)

        citizen = citizen_repo.create(preferred_language="en", preferred_channel="WEB")
        
        session1 = session_repo.create_session(citizen.citizen_ref, channel="WEB", language="en")
        session1.filled_slots = {"applicant_name": "Test User"}
        session_repo.save_session(session1)

        recovered = session_repo.get_or_recover_session(citizen.citizen_ref)
        assert recovered is not None
        assert recovered.id == session1.id
        assert recovered.filled_slots.get("applicant_name") == "Test User"
    finally:
        db.close()


def test_06_inactive_session_recovery():
    """If a session expired, get_or_recover_session reactivates it with new TTL."""
    db = SessionLocal()
    try:
        import datetime
        citizen_repo = CitizenRepository(db)
        session_repo = SessionRepository(db)
        app_repo = ApplicationRepository(db)

        citizen = citizen_repo.create(preferred_language="en", preferred_channel="WEB")
        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WEB",
            language="en"
        )
        app_repo.save_field(app.id, "applicant_name", "Ananya Sharma", "NON_SENSITIVE")

        # Create expired session
        session = session_repo.create_session(citizen.citizen_ref, channel="WEB", language="en")
        session.expires_at = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        db.commit()

        # Recover session
        recovered = session_repo.get_or_recover_session(citizen.citizen_ref)
        assert recovered is not None
        assert recovered.expires_at > datetime.datetime.utcnow()
        assert recovered.application_id == app.id
        assert recovered.filled_slots.get("applicant_name") == "Ananya Sharma"
    finally:
        db.close()


def test_07_missing_session_recovered_from_application():
    """If no session exists but Application exists, create session without creating duplicate Application."""
    db = SessionLocal()
    try:
        citizen_repo = CitizenRepository(db)
        session_repo = SessionRepository(db)
        app_repo = ApplicationRepository(db)

        citizen = citizen_repo.create(preferred_language="en", preferred_channel="WEB")
        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WEB",
            language="en"
        )
        app_repo.save_field(app.id, "annual_income", "120000", "NON_SENSITIVE")

        # Verify no session in DB initially
        assert session_repo.load_session(citizen.citizen_ref) is None

        # Recover
        recovered = session_repo.get_or_recover_session(citizen.citizen_ref)
        assert recovered is not None
        assert recovered.application_id == app.id
        assert recovered.filled_slots.get("annual_income") == "120000"

        # Check total applications for citizen remains exactly 1
        apps = app_repo.get_by_citizen(citizen.citizen_ref)
        assert len(apps) == 1, f"Expected exactly 1 application, found {len(apps)}"
    finally:
        db.close()


def test_08_resolve_mismatch_recovers_session_without_error():
    """Calling POST /resolve-mismatch when session was not cached in memory recovers session from DB."""
    db = SessionLocal()
    try:
        citizen_repo = CitizenRepository(db)
        app_repo = ApplicationRepository(db)

        test_phone = f"+9198{uuid.uuid4().hex[:8]}"
        citizen = citizen_repo.resolve_or_create(test_phone)
        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WEB"
        )
        doc = Document(
            application_id=app.id,
            doc_type="AADHAAR_CARD",
            file_ref="mock://doc/aadhaar.pdf",
            extracted_fields={"applicant_name": "Viki B Lokhande"},
            verification_status="MISMATCH",
            mismatch_fields=["applicant_name"]
        )
        db.add(doc)
        db.commit()

        # Call /resolve-mismatch directly
        resp = client.post("/api/v1/conversation/resolve-mismatch", json={
            "citizen_identifier": test_phone,
            "field_name": "applicant_name",
            "resolution": "use_document"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "ok"
    finally:
        db.close()


def test_09_unauthorized_application_access_blocked():
    """Citizen A must receive HTTP 403 when trying to access Citizen B's application."""
    db = SessionLocal()
    try:
        from app.core.security import create_access_token
        citizen_repo = CitizenRepository(db)
        app_repo = ApplicationRepository(db)

        citizen_a = citizen_repo.create(preferred_language="en", preferred_channel="WEB")
        citizen_b = citizen_repo.create(preferred_language="en", preferred_channel="WEB")

        app_b = app_repo.create(
            citizen_ref=citizen_b.citizen_ref,
            service_id="income_certificate",
            channel_origin="WEB"
        )

        token_a = create_access_token(data={"sub": citizen_a.citizen_ref, "citizen_ref": citizen_a.citizen_ref, "role": "citizen"})
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Citizen A attempts to get Citizen B's application
        resp = client.get(f"/api/v1/applications/{app_b.id}", headers=headers_a)
        assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}"

        # Citizen A attempts to get Citizen B's documents
        doc_resp = client.get(f"/api/v1/applications/{app_b.id}/documents", headers=headers_a)
        assert doc_resp.status_code == 403
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# 3. OpenRouter Error Handling & Zero-Fallback Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_10_openrouter_402_returns_controlled_503():
    """When OpenRouter returns HTTP 402, backend must raise LLMUnavailableError and return HTTP 503 with NO local fallback."""
    import httpx
    provider = OpenRouterProvider()

    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp_402 = httpx.Response(
        status_code=402,
        request=req,
        text='{"error":{"message":"This request requires more credits, or fewer max_tokens. You requested up to 100 tokens, but can only afford 0."}}'
    )

    with patch("httpx.post", side_effect=httpx.HTTPStatusError("Payment Required", request=req, response=resp_402)):
        with pytest.raises(LLMUnavailableError) as exc_info:
            provider.extract_nlu("I want an income certificate", "en", None)
        assert "402" in str(exc_info.value) or "unavailable" in str(exc_info.value).lower()


def test_11_openrouter_success_nlu():
    """Mock valid OpenRouter NLU output and verify structured extraction."""
    provider = OpenRouterProvider()
    valid_json = '''```json
    {
      "intent": "CERTIFICATE_REQUEST",
      "service_type": "income_certificate",
      "entities": {"applicant_name": "Ananya Sharma"},
      "pii_detected": ["applicant_name"],
      "literacy_level": "HIGH",
      "language": "en",
      "is_cross_question": false,
      "cross_question_target": null
    }
    ```'''

    with patch.object(provider, "_call", return_value=valid_json):
        result = provider.extract_nlu("I want an income certificate, my name is Ananya Sharma", "en", None)
        assert result["intent"] == "CERTIFICATE_REQUEST"
        assert result["service_type"] == "income_certificate"
        assert result["entities"]["applicant_name"] == "Ananya Sharma"


def test_12_direct_document_and_review_loading_without_chat():
    """Opening Documents or Review endpoint directly without prior chat loads application state from SQLite."""
    db = SessionLocal()
    try:
        citizen_repo = CitizenRepository(db)
        app_repo = ApplicationRepository(db)

        citizen = citizen_repo.create(preferred_language="en", preferred_channel="WEB")
        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WEB"
        )
        app_repo.save_field(app.id, "applicant_name", "Kunal Wandhare", "NON_SENSITIVE")

        doc = Document(
            application_id=app.id,
            doc_type="INCOME_PROOF",
            file_ref="mock://doc/income.pdf",
            extracted_fields={"applicant_name": "Kunal Wandhare", "annual_income": "300000"},
            verification_status="VERIFIED",
            overall_match_score=98.0
        )
        db.add(doc)
        db.commit()

        # Direct GET /applications/{id}
        app_res = client.get(f"/api/v1/applications/{app.id}")
        assert app_res.status_code == 200
        app_data = app_res.json()
        assert app_data.get("application_number") == app.application_number

        # Direct GET /applications/{id}/documents
        docs_res = client.get(f"/api/v1/applications/{app.id}/documents")
        assert docs_res.status_code == 200
        docs_data = docs_res.json()
        assert len(docs_data) == 1
        assert docs_data[0]["doc_type"] == "INCOME_PROOF"

        # Direct GET /applications/{id}/fields
        fields_res = client.get(f"/api/v1/applications/{app.id}/fields")
        assert fields_res.status_code == 200
        fields_data = fields_res.json()
        assert fields_data.get("applicant_name", {}).get("value") == "Kunal Wandhare"
    finally:
        db.close()
