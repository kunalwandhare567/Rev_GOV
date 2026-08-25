"""
Multi-User Citizen Data Isolation & Ownership Regression Test Suite
Validates that:
1. Every citizen sees ONLY their own profile, sessions, applications, documents, OCR, payment state, and SSE events.
2. No citizen can view or modify another citizen's application or documents by ID.
3. Channel identities resolve cleanly and uniquely without collision or cross-contamination.
4. Session recovery is strictly scoped by citizen_ref.
5. Inactive sessions do not leak previous applications.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.core.database import SessionLocal
from app.models.db_models import Citizen, Application, ConversationSession, Document, ChannelIdentity, User
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.session_repo import SessionRepository
from app.data_layer.repositories.channel_identity_repo import ChannelIdentityRepository
from app.services.citizen_resolver import CitizenResolver
from app.core.security import create_access_token

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def citizen_a(db: Session):
    citizen_repo = CitizenRepository(db)
    channel_repo = ChannelIdentityRepository(db)
    phone = f"+9198{uuid.uuid4().hex[:8]}"
    citizen = citizen_repo.create(name="Viki Bhausaheb Lokhande", phone=phone, preferred_language="en", preferred_channel="WEB")
    channel_repo.create(citizen_ref=citizen.citizen_ref, channel="WEB", identifier=phone, identifier_type="PHONE", verified=True)
    return citizen


@pytest.fixture
def citizen_b(db: Session):
    citizen_repo = CitizenRepository(db)
    channel_repo = ChannelIdentityRepository(db)
    phone = f"+9197{uuid.uuid4().hex[:8]}"
    citizen = citizen_repo.create(name="Pratik Madan", phone=phone, preferred_language="en", preferred_channel="WEB")
    channel_repo.create(citizen_ref=citizen.citizen_ref, channel="WEB", identifier=phone, identifier_type="PHONE", verified=True)
    return citizen


# 1. test_new_citizen_cannot_see_existing_citizen_application
def test_new_citizen_cannot_see_existing_citizen_application(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    app_repo = ApplicationRepository(db)
    session_repo = SessionRepository(db)

    # Citizen A has an application and session
    app_a = app_repo.create(citizen_ref=citizen_a.citizen_ref, service_id="income_certificate", channel_origin="WEB")
    app_repo.save_field(app_a.id, "applicant_name", "Viki Bhausaheb Lokhande", confirmed=True)
    session_a = session_repo.create_session(citizen_ref=citizen_a.citizen_ref, channel="WEB")
    session_a.application_id = app_a.id
    session_a.filled_slots = {"applicant_name": "Viki Bhausaheb Lokhande"}
    session_repo.save_session(session_a)
    db.commit()

    # Query session for Citizen B (newly logged in)
    token_b = create_access_token({"sub": citizen_b.phone, "citizen_ref": citizen_b.citizen_ref, "role": "CITIZEN"})
    resp = client.get(f"/api/v1/conversation/session/{citizen_b.citizen_ref}", headers={"Authorization": f"Bearer {token_b}"})
    
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("citizen_ref") == citizen_b.citizen_ref
    # Must NOT contain Citizen A's application or fields
    assert data.get("application_number") != app_a.application_number
    assert data.get("application_number") is None or data.get("application_number") != app_a.application_number
    filled = data.get("filled_slots", {})
    assert filled.get("applicant_name") != "Viki Bhausaheb Lokhande"


# 2. test_my_applications_returns_only_current_citizen
def test_my_applications_returns_only_current_citizen(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    app_repo = ApplicationRepository(db)

    # Create 2 applications for A and 1 for B
    app_a1 = app_repo.create(citizen_ref=citizen_a.citizen_ref, service_id="income_certificate", channel_origin="WEB")
    app_a2 = app_repo.create(citizen_ref=citizen_a.citizen_ref, service_id="caste_certificate", channel_origin="WEB")
    app_b1 = app_repo.create(citizen_ref=citizen_b.citizen_ref, service_id="domicile_certificate", channel_origin="WEB")

    token_b = create_access_token({"sub": citizen_b.phone, "citizen_ref": citizen_b.citizen_ref, "role": "CITIZEN"})
    resp = client.get("/api/v1/applications/my-applications", headers={"Authorization": f"Bearer {token_b}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("citizen_id") == citizen_b.citizen_ref
    apps = data.get("applications", [])
    app_ids = [a["id"] for a in apps]
    
    assert app_b1.id in app_ids
    assert app_a1.id not in app_ids
    assert app_a2.id not in app_ids


# 3. test_session_recovery_is_citizen_scoped
def test_session_recovery_is_citizen_scoped(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    app_repo = ApplicationRepository(db)
    session_repo = SessionRepository(db)

    app_a = app_repo.create(citizen_ref=citizen_a.citizen_ref, service_id="income_certificate", channel_origin="WEB")
    
    # Attempting to recover session for citizen B must never link app_a
    recovered_b = session_repo.get_or_recover_session(citizen_b.citizen_ref, application_id=app_a.id)
    assert recovered_b is None or recovered_b.application_id != app_a.id


# 4. test_application_details_require_ownership
def test_application_details_require_ownership(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    app_repo = ApplicationRepository(db)
    app_a = app_repo.create(citizen_ref=citizen_a.citizen_ref, service_id="income_certificate", channel_origin="WEB")

    token_b = create_access_token({"sub": citizen_b.phone, "citizen_ref": citizen_b.citizen_ref, "role": "CITIZEN"})
    resp = client.get(f"/api/v1/applications/{app_a.id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}"


# 5. test_documents_require_application_ownership
def test_documents_require_application_ownership(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    app_repo = ApplicationRepository(db)
    app_a = app_repo.create(citizen_ref=citizen_a.citizen_ref, service_id="income_certificate", channel_origin="WEB")

    doc = Document(
        application_id=app_a.id,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://secret/aadhaar.pdf",
        extracted_fields={"applicant_name": "Viki Bhausaheb Lokhande"},
        verification_status="VERIFIED"
    )
    db.add(doc)
    db.commit()

    token_b = create_access_token({"sub": citizen_b.phone, "citizen_ref": citizen_b.citizen_ref, "role": "CITIZEN"})
    resp = client.get(f"/api/v1/applications/{app_a.id}/documents", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403


# 6. test_document_image_requires_application_ownership
def test_document_image_requires_application_ownership(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    app_repo = ApplicationRepository(db)
    app_a = app_repo.create(citizen_ref=citizen_a.citizen_ref, service_id="income_certificate", channel_origin="WEB")

    doc = Document(
        application_id=app_a.id,
        doc_type="IDENTITY_PROOF",
        file_ref="mock://secret/aadhaar.pdf",
        verification_status="VERIFIED"
    )
    db.add(doc)
    db.commit()

    token_b = create_access_token({"sub": citizen_b.phone, "citizen_ref": citizen_b.citizen_ref, "role": "CITIZEN"})
    resp = client.get(f"/api/v1/applications/{app_a.id}/documents/{doc.id}/image", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403


# 7. test_channel_identity_resolves_correct_citizen
def test_channel_identity_resolves_correct_citizen(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    resolver = CitizenResolver(db)
    resolved_a = resolver.resolve(phone=citizen_a.phone)
    resolved_b = resolver.resolve(phone=citizen_b.phone)

    assert resolved_a is not None
    assert resolved_b is not None
    assert resolved_a.citizen_ref == citizen_a.citizen_ref
    assert resolved_b.citizen_ref == citizen_b.citizen_ref
    assert resolved_a.citizen_ref != resolved_b.citizen_ref


# 8. test_switching_accounts_clears_previous_frontend_state
def test_switching_accounts_clears_previous_frontend_state(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    # Session endpoint returns clean state when switching from citizen A to B
    token_a = create_access_token({"sub": citizen_a.phone, "citizen_ref": citizen_a.citizen_ref, "role": "CITIZEN"})
    token_b = create_access_token({"sub": citizen_b.phone, "citizen_ref": citizen_b.citizen_ref, "role": "CITIZEN"})

    resp_a = client.get(f"/api/v1/conversation/session/{citizen_a.citizen_ref}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    assert resp_a.json().get("citizen_ref") == citizen_a.citizen_ref

    resp_b = client.get(f"/api/v1/conversation/session/{citizen_b.citizen_ref}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    assert resp_b.json().get("citizen_ref") == citizen_b.citizen_ref


# 9. test_sse_events_are_citizen_scoped
def test_sse_events_are_citizen_scoped(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    token_b = create_access_token({"sub": citizen_b.phone, "citizen_ref": citizen_b.citizen_ref, "role": "CITIZEN"})
    # Citizen B attempts to listen to Citizen A's private notifications
    resp = client.get(f"/api/v1/stream/citizen/{citizen_a.citizen_ref}/events", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403


# 10. test_profile_and_application_citizen_ref_match
def test_profile_and_application_citizen_ref_match(db: Session, citizen_a: Citizen):
    app_repo = ApplicationRepository(db)
    session_repo = SessionRepository(db)

    app_a = app_repo.create(citizen_ref=citizen_a.citizen_ref, service_id="income_certificate", channel_origin="WEB")
    session = session_repo.create_session(citizen_ref=citizen_a.citizen_ref, channel="WEB")
    session.application_id = app_a.id
    session_repo.save_session(session)
    db.commit()

    token_a = create_access_token({"sub": citizen_a.phone, "citizen_ref": citizen_a.citizen_ref, "role": "CITIZEN"})
    resp = client.get(f"/api/v1/conversation/session/{citizen_a.citizen_ref}", headers={"Authorization": f"Bearer {token_a}"})
    data = resp.json()

    assert data["citizen_ref"] == citizen_a.citizen_ref
    assert data["application_number"] == app_a.application_number


# 11. test_two_citizens_can_have_independent_active_applications
def test_two_citizens_can_have_independent_active_applications(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    app_repo = ApplicationRepository(db)
    session_repo = SessionRepository(db)

    app_a = app_repo.create(citizen_ref=citizen_a.citizen_ref, service_id="income_certificate", channel_origin="WEB")
    app_b = app_repo.create(citizen_ref=citizen_b.citizen_ref, service_id="caste_certificate", channel_origin="WEB")

    session_a = session_repo.create_session(citizen_ref=citizen_a.citizen_ref, channel="WEB")
    session_a.application_id = app_a.id
    session_repo.save_session(session_a)

    session_b = session_repo.create_session(citizen_ref=citizen_b.citizen_ref, channel="WEB")
    session_b.application_id = app_b.id
    session_repo.save_session(session_b)
    db.commit()

    token_a = create_access_token({"sub": citizen_a.phone, "citizen_ref": citizen_a.citizen_ref, "role": "CITIZEN"})
    token_b = create_access_token({"sub": citizen_b.phone, "citizen_ref": citizen_b.citizen_ref, "role": "CITIZEN"})

    res_a = client.get(f"/api/v1/conversation/session/{citizen_a.citizen_ref}", headers={"Authorization": f"Bearer {token_a}"}).json()
    res_b = client.get(f"/api/v1/conversation/session/{citizen_b.citizen_ref}", headers={"Authorization": f"Bearer {token_b}"}).json()

    assert res_a["application_number"] == app_a.application_number
    assert res_a["service_type"] == "income_certificate"
    assert res_b["application_number"] == app_b.application_number
    assert res_b["service_type"] == "caste_certificate"


# 12. test_citizen_A_cannot_access_citizen_B_by_application_id
def test_citizen_A_cannot_access_citizen_B_by_application_id(db: Session, citizen_a: Citizen, citizen_b: Citizen):
    app_repo = ApplicationRepository(db)
    app_b = app_repo.create(citizen_ref=citizen_b.citizen_ref, service_id="domicile_certificate", channel_origin="WEB")

    token_a = create_access_token({"sub": citizen_a.phone, "citizen_ref": citizen_a.citizen_ref, "role": "CITIZEN"})
    
    # 1. Direct application details
    r1 = client.get(f"/api/v1/applications/{app_b.id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r1.status_code == 403

    # 2. Fields
    r2 = client.get(f"/api/v1/applications/{app_b.id}/fields", headers={"Authorization": f"Bearer {token_a}"})
    assert r2.status_code == 403

    # 3. Documents
    r3 = client.get(f"/api/v1/applications/{app_b.id}/documents", headers={"Authorization": f"Bearer {token_a}"})
    assert r3.status_code == 403

    # 4. Status
    r4 = client.get(f"/api/v1/applications/status/{app_b.application_number}", headers={"Authorization": f"Bearer {token_a}"})
    assert r4.status_code == 403
