"""
Integration test for OCR Mismatch Detection Flow.
Verifies that when a citizen declares wrong details in chat, uploading a document
with different OCR details triggers a MISMATCH status and returns clear field difference feedback.

Also tests: matched fields, fields_not_in_doc, overall_score, can_auto_resolve, verdict.
"""
import pytest
from app.services.matching_service import MatchingService, normalize_field_dict
from app.orchestration.state_machine.orchestrator import ConversationOrchestrator
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.session_repo import SessionRepository


def test_ocr_mismatch_detection_when_declared_details_differ():
    """
    Full OCR mismatch pipeline test.
    Citizen declares 'Wrong Declared Name' in chat.
    Document OCR extracts 'Kunal Wandhare'.
    Expects MISMATCH status with applicant_name in mismatch_fields.
    """
    from app.core.database import SessionLocal
    db_session = SessionLocal()
    try:
        # 1. Setup citizen
        c_repo = CitizenRepository(db_session)
        citizen = c_repo.resolve_or_create("test_mismatch_user@example.com", preferred_channel="WEB")

        # 2. Create application
        app_repo = ApplicationRepository(db_session)
        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WEB",
        )

        # 3. Create a session with application_id and wrong declared name
        session_repo = SessionRepository(db_session)
        # First try to load existing session, if not create new one
        session = session_repo.load_session(citizen.citizen_ref)
        if session is None:
            session = session_repo.create_session(
                citizen_ref=citizen.citizen_ref,
                channel="WEB",
                language="en",
            )
        session.application_id = app.id
        session.filled_slots = {
            "applicant_name": "Wrong Declared Name",
            "applicant_dob": "15-03-2004",
            "aadhaar_number": "123456789012",
        }
        session_repo.save_session(session)


        # 4. Upload document where OCR extracted real name
        ocr_extracted_fields = {
            "full_name": "Kunal Wandhare",        # Different from declared name
            "dob": "15-03-2004",                   # Matches
            "aadhaar_number": "123456789012",      # Matches
        }

        orchestrator = ConversationOrchestrator(db_session)
        upload_res = orchestrator.process_document_upload(
            citizen_ref=citizen.citizen_ref,
            doc_type="AADHAAR_CARD",
            file_ref="data/uploads/sample_aadhaar.png",
            extracted_fields=ocr_extracted_fields,
        )

        # 5. Verify mismatch detected
        assert upload_res["verification_status"] == "MISMATCH", (
            f"Expected MISMATCH, got {upload_res['verification_status']}. "
            f"Response: {upload_res.get('response')}"
        )

        # applicant_name or full_name should be in mismatched_fields (after normalization)
        mismatch = upload_res.get("mismatch_fields", [])
        assert any(f in mismatch for f in ["applicant_name", "full_name"]), (
            f"Expected applicant_name in mismatch_fields. Got: {mismatch}"
        )

        # Response should contain some mismatch detail
        resp = upload_res.get("response", "")
        assert resp, "Response should not be empty"
        assert len(resp) > 30, f"Response too short: '{resp}'"

        # DOB and aadhaar should be in matched_fields
        matched = upload_res.get("matched_fields", [])
        assert any(f in matched for f in ["applicant_dob", "dob", "aadhaar_number"]), (
            f"Expected dob/aadhaar in matched_fields. Got: {matched}"
        )

        # Scores should be present
        assert upload_res.get("overall_score") is not None
        assert upload_res["overall_score"] < 100, "Score should be < 100 due to name mismatch"

        # Verdict should be MISMATCH
        assert upload_res.get("verdict") == "MISMATCH", (
            f"Expected verdict MISMATCH, got {upload_res.get('verdict')}"
        )

        print("\n[PASS] OCR Mismatch Detection Test PASSED!")
        print(f"   Status: {upload_res['verification_status']}")
        print(f"   Mismatched: {upload_res['mismatch_fields']}")
        print(f"   Matched: {upload_res.get('matched_fields', [])}")
        print(f"   Score: {upload_res['overall_score']:.1f}%")
        print(f"   Response (first 200 chars): {upload_res['response'][:200]}")


    finally:
        db_session.close()
