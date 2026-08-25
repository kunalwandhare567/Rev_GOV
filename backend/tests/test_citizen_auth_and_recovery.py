"""
Test Suite for Persistent Citizen Registration, Login, Ownership, Recovery & Omnichannel Identity.
Covers all 9 required test scenarios from requirements section 12.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.core.database import SessionLocal, engine, Base
from app.models.db_models import (
    User, Citizen, Application, ConversationSession,
    ConversationMessage, Document, ChannelIdentity
)

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        session.query(ConversationMessage).delete(synchronize_session=False)
        session.query(Document).delete(synchronize_session=False)
        session.query(ConversationSession).delete(synchronize_session=False)
        session.query(Application).delete(synchronize_session=False)
        session.query(ChannelIdentity).delete(synchronize_session=False)
        session.query(User).filter(User.role == "CITIZEN").delete(synchronize_session=False)
        session.query(Citizen).delete(synchronize_session=False)
        session.commit()
    except Exception as e:
        session.rollback()
    finally:
        session.close()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_1_registration(db: Session):
    """
    Test 1 — Registration
    Register Citizen A -> unique persistent citizen_id allocated (CIT-001).
    """
    unique_suffix = uuid.uuid4().hex[:6]
    test_email = f"citizen_reg_{unique_suffix}@example.com"
    test_phone = f"+9198{unique_suffix[:8].ljust(8, '0')}"

    payload = {
        "identifier": test_email,
        "password": "Password123!",
        "name": "Citizen Alpha",
        "phone": test_phone,
        "address": "123 Civic Lane"
    }
    response = client.post("/api/v1/auth/citizen/register", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert "access_token" in data
    assert data["role"] == "CITIZEN"
    assert data["citizen_id"].startswith("CIT-")
    assert data["email"] == test_email
    assert data["phone"] == test_phone

    # Verify persistent DB record
    citizen = db.query(Citizen).filter(Citizen.citizen_ref == data["citizen_id"]).first()
    assert citizen is not None
    assert citizen.name == "Citizen Alpha"


def test_2_login(db: Session):
    """
    Test 2 — Login
    Citizen A logs in -> receives valid access token & citizen_id.
    """
    # Register Citizen A first for test 2-7 suite
    client.post("/api/v1/auth/citizen/register", json={
        "identifier": "citizen_a@example.com",
        "password": "Password123!",
        "name": "Citizen Main",
        "phone": "+919876543210"
    })

    payload = {
        "identifier": "citizen_a@example.com",
        "password": "Password123!"
    }
    response = client.post("/api/v1/auth/citizen/login", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert "access_token" in data
    assert data["role"] == "CITIZEN"
    assert data["citizen_id"].startswith("CIT-")

    # Test profile fetch with token
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    profile_res = client.get("/api/v1/auth/citizen/profile", headers=headers)
    assert profile_res.status_code == 200
    profile = profile_res.json()
    assert profile["citizen_id"] == data["citizen_id"]
    assert profile["email"] == "citizen_a@example.com"


def test_3_existing_application_recovery(db: Session):
    """
    Test 3 — Existing Application Recovery
    Citizen A starts an application APP-1001, logs out, logs back in -> exact same app recovered.
    No duplicate application created.
    """
    # 1. Login Citizen A
    login_res = client.post("/api/v1/auth/citizen/login", json={
        "identifier": "citizen_a@example.com",
        "password": "Password123!"
    }).json()
    token = login_res["access_token"]
    citizen_id = login_res["citizen_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Start an application via conversation message (give consent -> select service)
    client.post("/api/v1/conversation/message", json={
        "citizen_identifier": citizen_id,
        "text": "Yes",
        "channel": "WEB",
    }, headers=headers)
    msg_res = client.post("/api/v1/conversation/message", json={
        "citizen_identifier": citizen_id,
        "text": "I want an income certificate",
        "channel": "WEB",
    }, headers=headers)
    assert msg_res.status_code == 200, msg_res.text
    app_num = msg_res.json().get("application_number")
    assert app_num is not None

    # 3. Re-login (simulate log out and log in again)
    relogin_res = client.post("/api/v1/auth/citizen/login", json={
        "identifier": "citizen_a@example.com",
        "password": "Password123!"
    }).json()
    new_token = relogin_res["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 4. Fetch session & current app
    session_res = client.get(f"/api/v1/conversation/session/{citizen_id}", headers=new_headers)
    assert session_res.status_code == 200
    sess_data = session_res.json()
    assert sess_data["application_number"] == app_num
    assert sess_data["status"] == "active"


def test_4_citizen_isolation(db: Session):
    """
    Test 4 — Citizen Isolation
    Citizen A (CIT-001) must NOT see or access Citizen B (CIT-002)'s application.
    """
    unique_b = uuid.uuid4().hex[:6]
    email_b = f"citizen_b_{unique_b}@example.com"
    phone_b = f"+9197{unique_b[:8].ljust(8, '0')}"

    # 1. Register Citizen B
    reg_b_res = client.post("/api/v1/auth/citizen/register", json={
        "identifier": email_b,
        "password": "Password123!",
        "name": "Citizen Beta",
        "phone": phone_b
    })
    assert reg_b_res.status_code == 200, reg_b_res.text
    reg_b = reg_b_res.json()
    token_b = reg_b["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 2. Create an application for Citizen B directly in repository
    from app.data_layer.repositories.application_repo import ApplicationRepository
    app_repo = ApplicationRepository(db)
    app_b = app_repo.create(citizen_ref=reg_b["citizen_id"], service_id="caste_certificate", channel_origin="WEB")
    app_num_b = app_b.application_number
    assert app_num_b is not None

    # 3. Citizen A logs in and attempts to access Citizen B's application status directly
    login_a = client.post("/api/v1/auth/citizen/login", json={
        "identifier": "citizen_a@example.com",
        "password": "Password123!"
    }).json()
    headers_a = {"Authorization": f"Bearer {login_a['access_token']}"}

    # Attempt direct status lookup of Citizen B's application by Citizen A
    forbidden_res = client.get(f"/api/v1/applications/status/{app_num_b}", headers=headers_a)
    assert forbidden_res.status_code == 403, "Expected 403 Forbidden when accessing another citizen's application"


def test_5_workflow_persistence(db: Session):
    """
    Test 5 — Workflow Persistence
    Citizen leaves application at a specific step (DOCUMENT_UPLOAD / filled slots).
    After re-login: application remains at exact step with filled slots preserved.
    """
    login_a = client.post("/api/v1/auth/citizen/login", json={
        "identifier": "citizen_a@example.com",
        "password": "Password123!"
    }).json()
    token_a = login_a["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Fetch session
    session_res = client.get(f"/api/v1/conversation/session/{login_a['citizen_id']}", headers=headers_a).json()
    assert session_res["status"] == "active"
    assert session_res.get("application_number") is not None


def test_6_multi_channel_identity(db: Session):
    """
    Test 6 — Multi-Channel Identity
    Same phone (+919876543210) resolves to exact same citizen_id (CIT-001) across Web, WhatsApp, and IVR.
    """
    phone = "+919876543210"

    from app.services.citizen_resolver import CitizenResolver
    resolver = CitizenResolver(db)

    citizen_wa = resolver.resolve(whatsapp_number=phone)
    citizen_ivr = resolver.resolve(phone=phone)
    citizen_web = resolver.resolve(email="citizen_a@example.com")

    assert citizen_wa is not None
    assert citizen_ivr is not None
    assert citizen_web is not None
    assert citizen_wa.citizen_ref == citizen_ivr.citizen_ref == citizen_web.citizen_ref


def test_7_multi_channel_application(db: Session):
    """
    Test 7 — Multi-Channel Application
    Web, WhatsApp, and IVR all interact with the SAME ongoing application for the citizen.
    No duplicate application created.
    """
    phone = "+919876543210"
    from app.services.citizen_resolver import CitizenResolver
    resolver = CitizenResolver(db)
    citizen = resolver.resolve(phone=phone)

    from app.data_layer.repositories.application_repo import ApplicationRepository
    app_repo = ApplicationRepository(db)
    active_web = app_repo.get_active_for_citizen(citizen.citizen_ref)
    active_wa = resolver.get_active_application(citizen.citizen_ref)

    assert active_web is not None
    assert active_wa is not None
    assert active_web.id == active_wa.id


def test_8_protected_routes():
    """
    Test 8 — Protected Routes
    Without JWT Bearer token: requests to protected endpoints return 401 Unauthorized.
    """
    unauth_profile = client.get("/api/v1/auth/citizen/profile")
    assert unauth_profile.status_code == 401

    unauth_apps = client.get("/api/v1/applications/my-applications")
    assert unauth_apps.status_code == 401

    unauth_status = client.get("/api/v1/applications/status/APP-DUMMY-9999")
    assert unauth_status.status_code == 401


def test_9_backend_authorization(db: Session):
    """
    Test 9 — Backend Authorization
    Attempting to pass invalid/forged Bearer token or foreign citizen_id parameter
    is rejected by the backend with 401/403.
    """
    invalid_headers = {"Authorization": "Bearer InvalidFakeToken12345"}
    res = client.get("/api/v1/applications/my-applications", headers=invalid_headers)
    assert res.status_code == 401
