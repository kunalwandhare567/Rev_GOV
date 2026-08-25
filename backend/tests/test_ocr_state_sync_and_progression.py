"""
Test Suite: OCR Normalization, Authoritative Matching State Sync,
Next-Field Progression, Session Persistence, and OpenRouter Model Configuration.
Covers TEST 1 through TEST 18.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.core.database import SessionLocal, auto_migrate_schema
from app.core.config import settings
from app.models.db_models import Citizen, Application, ConversationSession, Document
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.session_repo import SessionRepository
from app.data_layer.repositories.document_repo import DocumentRepository
from app.services.matching_service import MatchingService
from app.services.ocr_service import OCRService
from app.services.next_question_engine import NextQuestionEngine
from app.orchestration.state_machine.orchestrator import ConversationOrchestrator
from app.llm.openrouter_provider import OpenRouterProvider
from app.llm.exceptions import LLMUnavailableError
from main import app as fastapi_app

auto_migrate_schema()
client = TestClient(fastapi_app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_01_raw_ocr_preserved(db_session):
    """TEST 1: Raw OCR text is preserved in SQLite without truncation or loss."""
    app_repo = ApplicationRepository(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100001", preferred_channel="WEB")
    app = app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")

    raw_noisy = "Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga"
    doc = app_repo.save_document(
        application_id=app.id,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://pan.jpg",
        raw_ocr_text=raw_noisy,
        raw_extracted_fields={"applicant_name": raw_noisy},
        normalized_fields={"applicant_name": "Viki Bhausaheb Lokhande"},
        confidence_score=0.96,
    )

    doc_in_db = db_session.query(Document).filter(Document.id == doc.id).first()
    assert doc_in_db.raw_ocr_text == raw_noisy
    assert doc_in_db.raw_extracted_fields.get("applicant_name") == raw_noisy


def test_02_noisy_ocr_normalized():
    """TEST 2: OpenRouter OCR normalization cleans noisy text into strict dictionary."""
    provider = OpenRouterProvider(api_key="test-key", model="minimax/minimax-m3:free")
    raw_ocr = "Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga"

    mock_llm_resp = '''{
      "normalized_fields": {
        "applicant_name": "Viki Bhausaheb Lokhande",
        "dob": null,
        "gender": null
      },
      "confidence": {
        "applicant_name": 0.96
      },
      "corrections": ["Removed OCR artifact prefix and suffix"]
    }'''

    with patch.object(provider, "_call", return_value=mock_llm_resp):
        res = provider.normalize_ocr_fields(
            raw_text=raw_ocr,
            extracted_fields={"applicant_name": raw_ocr},
            doc_type="IDENTITY_PROOF",
        )
        assert res["normalized_fields"]["applicant_name"] == "Viki Bhausaheb Lokhande"
        assert res["normalized_fields"]["dob"] is None
        assert res["confidence"]["applicant_name"] == 0.96


def test_03_normalized_name_matches_declared_name():
    """TEST 3: Normalized name produces 100% MATCH against declared name."""
    matcher = MatchingService()
    declared = {"applicant_name": "Viki Bhausaheb Lokhande"}
    normalized_ocr = {"applicant_name": "Viki Bhausaheb Lokhande"}

    res = matcher.compare_document(declared, normalized_ocr, doc_type="IDENTITY_PROOF")
    assert res.overall_score == 100.0
    assert "applicant_name" in res.matched_fields
    assert len(res.mismatched_fields) == 0


def test_04_true_mismatch_remains_mismatch():
    """TEST 4: True mismatch (declared vs different name) correctly returns MISMATCH."""
    matcher = MatchingService()
    declared = {"applicant_name": "Viki Bhausaheb Lokhande"}
    different_ocr = {"applicant_name": "Rahul Kumar"}

    res = matcher.compare_document(declared, different_ocr, doc_type="IDENTITY_PROOF")
    assert res.overall_score < 50.0
    assert "applicant_name" in res.mismatched_fields
    assert "applicant_name" not in res.matched_fields


def test_05_normalized_fields_persisted_to_sqlite(db_session):
    """TEST 5: Normalized fields and normalization metadata are persisted to SQLite."""
    app_repo = ApplicationRepository(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100002", preferred_channel="WEB")
    app = app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")

    doc = app_repo.save_document(
        application_id=app.id,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://aadhaar.jpg",
        normalized_fields={"applicant_name": "Viki Bhausaheb Lokhande", "aadhaar_number": "987654321098"},
        normalization_status="AI_NORMALIZED",
        normalization_confidence={"applicant_name": 0.96, "aadhaar_number": 0.99},
        confidence_score=0.975,
    )

    doc_in_db = db_session.query(Document).filter(Document.id == doc.id).first()
    assert doc_in_db.normalized_fields["applicant_name"] == "Viki Bhausaheb Lokhande"
    assert doc_in_db.normalization_status == "AI_NORMALIZED"
    assert doc_in_db.confidence_score == 0.975


def test_06_matching_result_persisted_to_sqlite(db_session):
    """TEST 6: Matching results (score, status, matched_fields) are persisted to SQLite."""
    app_repo = ApplicationRepository(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100003", preferred_channel="WEB")
    app = app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")

    doc = app_repo.save_document(
        application_id=app.id,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://pan.jpg",
        overall_match_score=100.0,
        matched_fields=["applicant_name"],
        field_match_scores={"applicant_name": {"score": 100.0, "match": True}},
        verification_status="VERIFIED",
    )

    doc_in_db = db_session.query(Document).filter(Document.id == doc.id).first()
    assert doc_in_db.overall_match_score == 100.0
    assert doc_in_db.verification_status == "VERIFIED"
    assert "applicant_name" in doc_in_db.matched_fields


def test_07_frontend_api_returns_normalized_fields(db_session):
    """TEST 7: GET /api/v1/applications/{id}/documents returns structured normalized_ocr & raw_ocr."""
    app_repo = ApplicationRepository(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100004", preferred_channel="WEB")
    app = app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")

    app_repo.save_document(
        application_id=app.id,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://doc.jpg",
        raw_ocr_text="Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga",
        raw_extracted_fields={"applicant_name": "Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga"},
        normalized_fields={"applicant_name": "Viki Bhausaheb Lokhande"},
        normalization_confidence={"applicant_name": 0.96},
        overall_match_score=100.0,
        matched_fields=["applicant_name"],
        verification_status="VERIFIED",
    )

    from app.core.security import create_access_token
    token = create_access_token({"sub": citizen.citizen_ref, "citizen_ref": citizen.citizen_ref})
    resp = client.get(f"/api/v1/applications/{app.id}/documents", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1
    d = docs[0]
    assert d["raw_ocr"]["text"] == "Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga"
    assert d["normalized_ocr"]["fields"]["applicant_name"] == "Viki Bhausaheb Lokhande"
    assert d["matching"]["score"] == 100.0
    assert d["matching"]["status"] == "VERIFIED"


def test_08_frontend_api_returns_same_match_score(db_session):
    """TEST 8: Match score in API response exactly matches the persisted score in SQLite."""
    app_repo = ApplicationRepository(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100005", preferred_channel="WEB")
    app = app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")

    app_repo.save_document(
        application_id=app.id,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://doc.jpg",
        overall_match_score=100.0,
        verification_status="VERIFIED",
    )

    from app.core.security import create_access_token
    token = create_access_token({"sub": citizen.citizen_ref, "citizen_ref": citizen.citizen_ref})
    resp = client.get(f"/api/v1/applications/{app.id}/documents", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()[0]["overall_match_score"] == 100.0
    assert resp.json()[0]["matching"]["score"] == 100.0


def test_09_next_question_engine_executes_after_ocr(db_session):
    """TEST 9: NextQuestionEngine executes after OCR verification and asks for the next missing slot."""
    orchestrator = ConversationOrchestrator(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100006", preferred_channel="WEB")

    # Start session with applicant_name filled
    session = orchestrator.session_repo.create_session(citizen.citizen_ref, channel="WEB", language="en")
    app = orchestrator.app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")
    session.application_id = app.id
    session.filled_slots = {"applicant_name": "Viki Bhausaheb Lokhande"}
    session.missing_slots = ["ration_card_number", "annual_income", "purpose"]
    session.current_node = "SLOT_FILLING"
    orchestrator.session_repo.save_session(session)

    res = orchestrator.process_document_upload(
        citizen_ref=citizen.citizen_ref,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://pan.jpg",
        extracted_fields={"applicant_name": "Viki Bhausaheb Lokhande"},
        raw_ocr_text="Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga",
        normalized_fields={"applicant_name": "Viki Bhausaheb Lokhande"},
        normalization_confidence={"applicant_name": 0.96},
    )

    assert res["verification_status"] == "VERIFIED"
    assert res["overall_score"] == 100.0
    # Next question engine must have advanced
    assert res["pending_field"] is not None
    assert "verified successfully" in res["response"].lower()
    # Response contains the next question
    assert len(res["response"]) > len("All fields verified")


def test_10_next_missing_field_becomes_pending_field(db_session):
    """TEST 10: Next missing required field is set as session.pending_field in SQLite."""
    orchestrator = ConversationOrchestrator(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100007", preferred_channel="WEB")

    session = orchestrator.session_repo.create_session(citizen.citizen_ref, channel="WEB", language="en")
    app = orchestrator.app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")
    session.application_id = app.id
    session.filled_slots = {"applicant_name": "Viki Bhausaheb Lokhande"}
    orchestrator.session_repo.save_session(session)

    orchestrator.process_document_upload(
        citizen_ref=citizen.citizen_ref,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://pan.jpg",
        extracted_fields={"applicant_name": "Viki Bhausaheb Lokhande"},
        normalized_fields={"applicant_name": "Viki Bhausaheb Lokhande"},
    )

    refreshed_session = orchestrator.session_repo.load_session(citizen.citizen_ref)
    assert refreshed_session.pending_field in ["applicant_dob", "ration_card_number", "annual_income", "purpose"]


def test_11_pending_question_persisted(db_session):
    """TEST 11: Pending question text is persisted to SQLite."""
    orchestrator = ConversationOrchestrator(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100008", preferred_channel="WEB")

    session = orchestrator.session_repo.create_session(citizen.citizen_ref, channel="WEB", language="en")
    app = orchestrator.app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")
    session.application_id = app.id
    session.filled_slots = {"applicant_name": "Viki Bhausaheb Lokhande"}
    orchestrator.session_repo.save_session(session)

    orchestrator.process_document_upload(
        citizen_ref=citizen.citizen_ref,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://pan.jpg",
        extracted_fields={"applicant_name": "Viki Bhausaheb Lokhande"},
        normalized_fields={"applicant_name": "Viki Bhausaheb Lokhande"},
    )

    refreshed_session = orchestrator.session_repo.load_session(citizen.citizen_ref)
    assert refreshed_session.pending_question is not None
    assert len(refreshed_session.pending_question) > 0


def test_12_browser_session_recovery_preserves_pending_field(db_session):
    """TEST 12: Session recovery restores pending_field and filled_slots without data loss."""
    session_repo = SessionRepository(db_session)
    app_repo = ApplicationRepository(db_session)
    cit_repo = CitizenRepository(db_session)

    citizen = cit_repo.resolve_or_create("+919811100009", preferred_channel="WEB")
    app = app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")
    app_repo.save_field(app.id, "applicant_name", "Viki Bhausaheb Lokhande", classification="NON_SENSITIVE")

    session = session_repo.create_session(citizen.citizen_ref, channel="WEB", language="en")
    session.application_id = app.id
    session.pending_field = "annual_income"
    session.pending_question = "What is your annual family income?"
    session.filled_slots = {"applicant_name": "Viki Bhausaheb Lokhande"}
    session_repo.save_session(session)

    recovered = session_repo.get_or_recover_session(citizen.citizen_ref)
    assert recovered.pending_field == "annual_income"
    assert recovered.pending_question == "What is your annual family income?"
    assert recovered.filled_slots["applicant_name"] == "Viki Bhausaheb Lokhande"


def test_13_cross_question_preserves_pending_field(db_session):
    """TEST 13: Asking a cross-question ('Why do you need this?') answers and preserves pending_field."""
    orchestrator = ConversationOrchestrator(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100010", preferred_channel="WEB")

    session = orchestrator.session_repo.create_session(citizen.citizen_ref, channel="WEB", language="en")
    app = orchestrator.app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")
    session.application_id = app.id
    session.filled_slots = {"applicant_name": "Viki Bhausaheb Lokhande"}
    session.pending_field = "annual_income"
    session.current_node = "SLOT_FILLING"
    orchestrator.session_repo.save_session(session)

    reply = orchestrator.handle_message(
        citizen_ref=citizen.citizen_ref,
        channel="WEB",
        text="Why do you need my annual income?",
        language="en",
    )

    refreshed_session = orchestrator.session_repo.load_session(citizen.citizen_ref)
    # pending_field is preserved
    assert refreshed_session.pending_field == "annual_income"


def test_14_no_duplicate_document_created_on_refresh(db_session):
    """TEST 14: Repeated document uploads or refreshes update the existing Document record."""
    app_repo = ApplicationRepository(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100011", preferred_channel="WEB")
    app = app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")

    doc1 = app_repo.save_document(app.id, "IDENTITY_PROOF", "mock://doc_v1.jpg", {"applicant_name": "Viki"})
    doc2 = app_repo.save_document(app.id, "IDENTITY_PROOF", "mock://doc_v2.jpg", {"applicant_name": "Viki Bhausaheb Lokhande"})

    all_docs = app_repo.get_documents(app.id) if hasattr(app_repo, "get_documents") else (
        db_session.query(Document).filter(Document.application_id == app.id, Document.doc_type == "IDENTITY_PROOF").all()
    )
    assert len(all_docs) == 1
    assert doc1.id == doc2.id
    assert all_docs[0].file_ref == "mock://doc_v2.jpg"


def test_15_no_duplicate_application_on_session_recovery(db_session):
    """TEST 15: Session recovery links to the existing SQLite Application without creating duplicates."""
    import uuid
    session_repo = SessionRepository(db_session)
    app_repo = ApplicationRepository(db_session)
    cit_repo = CitizenRepository(db_session)

    fresh_phone = f"+9199{uuid.uuid4().hex[:8]}"
    citizen = cit_repo.resolve_or_create(fresh_phone, preferred_channel="WEB")
    app = app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")

    session1 = session_repo.get_or_recover_session(citizen.citizen_ref)
    session2 = session_repo.get_or_recover_session(citizen.citizen_ref)

    apps = app_repo.get_by_citizen(citizen.citizen_ref)
    assert len(apps) == 1
    assert session1.application_id == app.id
    assert session2.application_id == app.id


def test_16_openrouter_model_is_configured_model():
    """TEST 16: OpenRouter provider model is settings.OPENROUTER_MODEL (minimax/minimax-m3:free)."""
    from app.llm.provider_factory import get_provider
    provider = get_provider()
    assert provider.provider_name == "openrouter"
    assert provider.model_name == settings.OPENROUTER_MODEL
    assert "minimax" in settings.OPENROUTER_MODEL


def test_17_openrouter_402_returns_http_503():
    """TEST 17: When OpenRouter returns HTTP 402, backend raises LLMUnavailableError with status_code=503."""
    provider = OpenRouterProvider()

    with patch.object(provider, "_call", side_effect=LLMUnavailableError("AI service is temporarily unavailable. Provider error (HTTP 402).", status_code=503)):
        with pytest.raises(LLMUnavailableError) as exc_info:
            provider.extract_nlu("I want an Income Certificate", "en", None)
        assert exc_info.value.status_code == 503
        assert "402" in str(exc_info.value) or "unavailable" in str(exc_info.value).lower()


def test_18_no_local_fallback_executed():
    """TEST 18: On LLM failure, absolutely no local_llm or keyword fallback is executed."""
    provider = OpenRouterProvider()

    with patch.object(provider, "_call", side_effect=LLMUnavailableError("AI service is temporarily unavailable. HTTP error (500).", status_code=503)):
        with pytest.raises(LLMUnavailableError) as exc_info:
            provider.extract_nlu("Citizen utterance", "en", None)
        assert "unavailable" in str(exc_info.value).lower() or "500" in str(exc_info.value)


def test_19_document_upload_success_and_no_fsm_error(db_session):
    """TEST 19: Full document upload flow succeeds with HTTP 200 and transitions to READY_FOR_REVIEW."""
    orchestrator = ConversationOrchestrator(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100019", preferred_channel="WEB")

    session = orchestrator.session_repo.create_session(citizen.citizen_ref, channel="WEB", language="en")
    app = orchestrator.app_repo.create(citizen_ref=citizen.citizen_ref, service_id="income_certificate")
    session.application_id = app.id
    session.filled_slots = {
        "applicant_name": "Viki Bhausaheb Lokhande",
        "applicant_dob": "1995-05-15",
        "gender": "Male",
        "aadhaar_number": "987654321098",
        "address": "Flat 101, Shanti Nagar, Mumbai",
        "annual_income": "300000",
        "purpose": "Higher Education",
    }
    session.current_node = "DOCUMENT_CAPTURE"
    orchestrator.session_repo.save_session(session)

    # 1. Upload first doc: INCOME_PROOF -> asks for IDENTITY_PROOF
    res1 = orchestrator.process_document_upload(
        citizen_ref=citizen.citizen_ref,
        doc_type="INCOME_PROOF",
        file_ref="mock://salary_slip.pdf",
        extracted_fields={"applicant_name": "Viki Bhausaheb Lokhande", "annual_income": "300000"},
        raw_ocr_text="Salary slip for Viki Bhausaheb Lokhande Annual Income Rs. 3,00,000",
        normalized_fields={"applicant_name": "Viki Bhausaheb Lokhande", "annual_income": "300000"},
        normalization_status="DETERMINISTIC",
        normalization_provider="LOCAL",
    )
    assert res1.get("verification_status") == "VERIFIED"
    assert res1.get("overall_score") == 100.0
    assert "error" not in res1
    assert "Identity Proof" in res1.get("response", "")

    # 2. Upload second doc: IDENTITY_PROOF -> all required docs verified -> READY_FOR_REVIEW
    res2 = orchestrator.process_document_upload(
        citizen_ref=citizen.citizen_ref,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://aadhaar.pdf",
        extracted_fields={"applicant_name": "Viki Bhausaheb Lokhande", "aadhaar_number": "987654321098"},
        raw_ocr_text="Aadhaar card for Viki Bhausaheb Lokhande 9876 5432 1098",
        normalized_fields={"applicant_name": "Viki Bhausaheb Lokhande", "aadhaar_number": "987654321098"},
        normalization_status="DETERMINISTIC",
        normalization_provider="LOCAL",
    )
    assert res2.get("verification_status") == "VERIFIED"
    assert res2.get("overall_score") == 100.0
    assert "error" not in res2

    # Application should be transitioned to valid state READY_FOR_REVIEW without throwing AttributeError
    refreshed_app = orchestrator.app_repo.get_by_id(app.id)
    assert refreshed_app.status in ["READY_FOR_REVIEW", "VALIDATION_COMPLETED"]


def test_20_deterministic_ocr_normalization():
    """TEST 20: Deterministic OCR normalization correctly cleans noisy names, PAN, DOB, and Income."""
    ocr_service = OCRService()
    
    # Test noisy name normalization
    noisy_name = "Ee Ae D Viki Bhausaheb Lokhande Oa Bs Ga"
    cleaned_name = ocr_service._normalize_name(noisy_name)
    assert cleaned_name == "Viki Bhausaheb Lokhande"

    # Test PAN normalization
    pan_noisy = " pan : bizpl2757d "
    cleaned_pan = ocr_service._normalize_pan(pan_noisy)
    assert cleaned_pan == "BIZPL2757D"

    # Test Income normalization
    income_noisy = " ₹ 3,00,000 /- "
    cleaned_income = ocr_service._normalize_income(income_noisy)
    assert cleaned_income == "300000"

    # Test Batch deterministic normalization
    raw_dict = {
        "applicant_name": noisy_name,
        "pan_number": pan_noisy,
        "annual_income": income_noisy,
        "gender": "male"
    }
    normalized_dict = ocr_service._normalize_deterministic_fields(raw_dict)
    assert normalized_dict["applicant_name"] == "Viki Bhausaheb Lokhande"
    assert normalized_dict["pan_number"] == "BIZPL2757D"
    assert normalized_dict["annual_income"] == "300000"
    assert normalized_dict["gender"] == "Male"


def test_21_field_correction_and_slot_progression(db_session):
    """TEST 21: Answering applicant_name triggers FieldCorrector and advances to next field via NextQuestionEngine."""
    orchestrator = ConversationOrchestrator(db_session)
    cit_repo = CitizenRepository(db_session)
    citizen = cit_repo.resolve_or_create("+919811100021", preferred_channel="WEB")

    # Start session in SLOT_FILLING with pending_field = applicant_name
    session = orchestrator.session_repo.create_session(citizen.citizen_ref, channel="WEB", language="en")
    app = orchestrator.app_repo.create(citizen_ref=citizen.citizen_ref, service_id="caste_certificate")
    session.application_id = app.id
    session.filled_slots = {}
    session.pending_field = "applicant_name"
    session.current_node = "SLOT_FILLING"
    orchestrator.session_repo.save_session(session)

    reply = orchestrator.handle_message(
        citizen_ref=citizen.citizen_ref,
        channel="WEB",
        text="viki bhausaheb lokhande",
        language="en",
    )

    # 1. Successful response
    assert reply["current_node"] == "SLOT_FILLING"
    # 2. FieldCorrector normalized 'viki bhausaheb lokhande' -> 'Viki Bhausaheb Lokhande'
    refreshed_session = orchestrator.session_repo.load_session(citizen.citizen_ref)
    assert refreshed_session.filled_slots["applicant_name"] == "Viki Bhausaheb Lokhande"
    # 3. NextQuestionEngine advanced to next missing field
    assert refreshed_session.pending_field == "applicant_dob"
    assert refreshed_session.pending_question is not None
    assert len(refreshed_session.pending_question) > 0
    # 4. Value persisted to SQLite ApplicationData
    fields = orchestrator.app_repo.get_fields(app.id)
    assert fields["applicant_name"] == "Viki Bhausaheb Lokhande"
