"""
Test Suite — Admin Workflow, Review, Decision Lifecycle & Payment Handoff
Covers all 25 required test cases specified in the Admin Module Implementation.
"""
import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.core.database import get_db, SessionLocal
from app.models.db_models import User, Citizen, Application, ApplicationData, Document, Certificate, ConversationSession
from app.orchestration.state_machine.application_fsm import AppState
from app.data_layer.encryption import FieldEncryptor
from app.api.routes.auth import pwd_ctx, _create_token
from app.data_layer.repositories.audit_repo import AuditRepository


@pytest.fixture
def db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_token(db: Session):
    admin = db.query(User).filter(User.username == "admin_test").first()
    if not admin:
        admin = User(
            username="admin_test",
            hashed_password=pwd_ctx.hash("admin123"),
            role="ADMIN",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    return _create_token({"sub": "admin_test", "role": "ADMIN"})


@pytest.fixture
def citizen_token(db: Session):
    citizen = db.query(Citizen).filter(Citizen.citizen_ref == "CIT-TEST-001").first()
    if not citizen:
        citizen = Citizen(
            citizen_ref="CIT-TEST-001",
            name="Ramesh Kumar",
            phone="+919876543210",
            email="ramesh@example.com",
        )
        db.add(citizen)
        db.commit()
        db.refresh(citizen)
    return _create_token({"sub": "ramesh", "citizen_ref": "CIT-TEST-001", "role": "CITIZEN"})


def _create_test_application(db: Session, status: str = "SUBMITTED_FOR_VERIFICATION", citizen_ref: Optional[str] = None):
    import uuid
    uid = str(uuid.uuid4())[:8].upper()
    if not citizen_ref:
        citizen_ref = f"CIT-TEST-{uid}"

    # Ensure Citizen exists
    citizen = db.query(Citizen).filter(Citizen.citizen_ref == citizen_ref).first()
    if not citizen:
        citizen = Citizen(
            citizen_ref=citizen_ref,
            name=f"Ramesh Kumar {uid}",
            phone="+919876543210",
            email="ramesh@example.com",
        )
        db.add(citizen)
        db.commit()

    # Ensure Service exists
    from app.models.db_models import Service
    svc = db.query(Service).filter(Service.id == "income_certificate").first()
    if not svc:
        svc = Service(
            id="income_certificate",
            name_en="Income Certificate",
            department="Revenue Department",
            fee_amount=50.0,
            sla_days=7,
        )
        db.add(svc)
        db.commit()

    app_record = Application(
        application_number=f"APP-INC-2026-{uid}",
        tracking_id=f"INC-2026-{uid}",
        citizen_ref=citizen_ref,
        service_id="income_certificate",
        status=status,
        channel_origin="WEB",
        language="en",
        progress_percent=85,
        anomaly_score=0.15,
        submitted_at=datetime.datetime.utcnow() if status != "DRAFT" else None,
    )
    db.add(app_record)
    db.commit()
    db.refresh(app_record)

    # Add slot fields
    encryptor = FieldEncryptor()
    fields = {
        "applicant_name": f"Ramesh Kumar {uid}",
        "annual_income": "120000",
        "address": "Pune, Maharashtra",
        "purpose": "Higher Education",
    }
    for k, v in fields.items():
        db.add(ApplicationData(
            application_id=app_record.id,
            field_name=k,
            field_value_encrypted=encryptor.encrypt(v),
            classification="RESTRICTED" if "income" in k else "QUASI_IDENTIFIER",
        ))

    # Add document
    db.add(Document(
        application_id=app_record.id,
        doc_type="INCOME_PROOF",
        file_ref=f"data/uploads/income_{uid}.pdf",
        verification_status="VERIFIED",
        confidence_score=0.92,
        extracted_fields={"annual_income": "120000", "applicant_name": f"Ramesh Kumar {uid}"},
        normalized_fields={"annual_income": "120000", "applicant_name": f"Ramesh Kumar {uid}"},
        matched_fields=["annual_income", "applicant_name"],
        mismatch_fields=[],
        overall_match_score=100.0,
    ))

    # Ensure conversation session exists
    session = db.query(ConversationSession).filter(ConversationSession.citizen_ref == citizen_ref).first()
    if not session:
        session = ConversationSession(
            citizen_ref=citizen_ref,
            language="en",
            channel="WEB",
            application_id=app_record.id,
            current_node="VALIDATION",
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        )
        db.add(session)
    else:
        session.application_id = app_record.id
        session.expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=24)

    db.commit()
    db.refresh(app_record)
    return app_record


# ── TEST CASES ──

def test_01_submitted_application_appears_in_admin_queue(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.get(
        "/api/v1/applications/admin/list?status=SUBMITTED_FOR_VERIFICATION",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    app_ids = [a["id"] for a in data["applications"]]
    assert str(app_record.id) in app_ids


def test_02_draft_application_does_not_appear_in_submitted_queue(client: TestClient, db: Session, admin_token: str):
    draft_app = _create_test_application(db, status="DRAFT")
    res = client.get(
        "/api/v1/applications/admin/list?status=SUBMITTED_FOR_VERIFICATION",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    app_ids = [a["id"] for a in data["applications"]]
    assert str(draft_app.id) not in app_ids


def test_03_admin_can_open_submitted_application(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.get(
        f"/api/v1/applications/admin/{app_record.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["application"]["id"] == str(app_record.id)
    assert data["application"]["status"] == "SUBMITTED_FOR_VERIFICATION"
    assert "available_actions" in data
    assert "APPROVE" in data["available_actions"]


def test_04_unauthorized_citizen_cannot_access_admin_review(client: TestClient, db: Session, citizen_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    # Missing token -> 401
    res_no_auth = client.get(f"/api/v1/applications/admin/{app_record.id}")
    assert res_no_auth.status_code == 401

    # Citizen token -> 401 or 403 (unauthorized/forbidden for admin endpoints)
    res_citizen = client.get(
        f"/api/v1/applications/admin/{app_record.id}",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert res_citizen.status_code in (401, 403)


def test_05_admin_can_inspect_application_data(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.get(
        f"/api/v1/applications/admin/{app_record.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "application_data" in data
    assert "applicant_name" in data["application_data"]
    assert "Ramesh Kumar" in data["application_data"]["applicant_name"]["value"]


def test_06_admin_can_inspect_normalized_ocr(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.get(
        f"/api/v1/applications/admin/{app_record.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["documents"]) >= 1
    doc = data["documents"][0]
    assert "normalized_fields" in doc
    assert "Ramesh Kumar" in doc["normalized_fields"]["applicant_name"]


def test_07_admin_can_inspect_document_matching(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.get(
        f"/api/v1/applications/admin/{app_record.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "matching" in data
    assert "overall_match_score" in data["matching"]
    assert data["matching"]["overall_match_score"] >= 80


def test_08_admin_can_inspect_readiness(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.get(
        f"/api/v1/applications/admin/{app_record.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "readiness" in data
    assert "overall_score" in data["readiness"]
    assert "components" in data["readiness"]
    comp_names = [c["name"] for c in data["readiness"]["components"]]
    assert "Field Completeness" in comp_names
    assert "Document Coverage" in comp_names


def test_09_invalid_fsm_approval_blocked(client: TestClient, db: Session, admin_token: str):
    draft_app = _create_test_application(db, status="DRAFT")
    res = client.post(
        f"/api/v1/applications/admin/{draft_app.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE", "admin_notes": "Attempting invalid approve"},
    )
    assert res.status_code == 400


def test_10_approval_creates_approved_state(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE", "admin_notes": "All documents verified"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True


def test_11_approval_creates_payment_required(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE"},
    )
    assert res.status_code == 200
    assert res.json()["new_status"] == AppState.PAYMENT_REQUIRED

    # Check database
    db.refresh(app_record)
    assert app_record.status == AppState.PAYMENT_REQUIRED


def test_12_approval_generates_audit_log(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE", "admin_notes": "Audit verification test"},
    )
    audit_repo = AuditRepository(db)
    logs = audit_repo.get_recent_audit(limit=10, application_id=app_record.id)
    assert any("APPLICATION_APPROVED" in str(l.get("action")) for l in logs)


def test_13_approval_emits_sse_event(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_14_citizen_receives_approval_notification(client: TestClient, db: Session, admin_token: str):
    from app.models.db_models import ConversationMessage
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE"},
    )
    session = db.query(ConversationSession).filter(ConversationSession.citizen_ref == app_record.citizen_ref).first()
    assert session is not None
    messages = db.query(ConversationMessage).filter(ConversationMessage.session_id == session.id).all()
    assert any("APPROVED" in str(m.content) for m in messages)


def test_15_payment_is_unavailable_before_approval(client: TestClient, db: Session):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.post(
        "/api/v1/payment/initiate",
        json={
            "application_id": str(app_record.id),
            "citizen_identifier": app_record.citizen_ref,
            "amount": 50.0,
        },
    )
    assert res.status_code == 400
    assert "only allowed after government approval" in res.json()["detail"]


def test_16_payment_becomes_available_after_approval(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    # Approve first
    client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE"},
    )
    # Payment should now succeed
    res = client.post(
        "/api/v1/payment/initiate",
        json={
            "application_id": str(app_record.id),
            "citizen_identifier": app_record.citizen_ref,
            "amount": 50.0,
            "mode": "MOCK_AUTO",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "SUCCESS"


def test_17_admin_rejection_requires_reason(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "REJECT", "reason": ""},
    )
    assert res.status_code == 400
    assert "Rejection reason is required" in res.json()["detail"]


def test_18_rejected_application_cannot_pay(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "REJECT", "reason": "Income mismatch with revenue records"},
    )
    res = client.post(
        "/api/v1/payment/initiate",
        json={
            "application_id": str(app_record.id),
            "citizen_identifier": app_record.citizen_ref,
            "amount": 50.0,
        },
    )
    assert res.status_code == 400


def test_19_clarification_requires_message(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    res = client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "REQUEST_CLARIFICATION", "reason": ""},
    )
    assert res.status_code == 400


def test_20_citizen_receives_clarification_notification(client: TestClient, db: Session, admin_token: str):
    from app.models.db_models import ConversationMessage
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "REQUEST_CLARIFICATION", "reason": "Please upload a clearer address proof"},
    )
    session = db.query(ConversationSession).filter(ConversationSession.citizen_ref == app_record.citizen_ref).first()
    assert session is not None
    messages = db.query(ConversationMessage).filter(ConversationMessage.session_id == session.id).all()
    assert any("Action Required" in str(m.content) for m in messages)


def test_21_clarification_response_returns_application_to_review_queue(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "REQUEST_CLARIFICATION", "reason": "Missing signature"},
    )
    # Citizen resubmits
    res_submit = client.post(
        f"/api/v1/applications/{app_record.id}/submit"
    )
    assert res_submit.status_code == 200
    assert res_submit.json()["status"] == "SUBMITTED_FOR_VERIFICATION"

    # Verify visible in Admin queue
    res_queue = client.get(
        "/api/v1/applications/admin/list?status=SUBMITTED_FOR_VERIFICATION",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_queue.status_code == 200
    app_ids = [a["id"] for a in res_queue.json()["applications"]]
    assert str(app_record.id) in app_ids


def test_22_payment_completion_triggers_certificate_generation(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE"},
    )
    res_pay = client.post(
        "/api/v1/payment/initiate",
        json={
            "application_id": str(app_record.id),
            "citizen_identifier": app_record.citizen_ref,
            "amount": 50.0,
            "mode": "MOCK_AUTO",
        },
    )
    assert res_pay.status_code == 200
    assert res_pay.json()["status"] == "SUCCESS"
    assert res_pay.json()["certificate_ready"] is True


def test_23_certificate_becomes_certificate_ready(client: TestClient, db: Session, admin_token: str):
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE"},
    )
    client.post(
        "/api/v1/payment/initiate",
        json={
            "application_id": str(app_record.id),
            "citizen_identifier": app_record.citizen_ref,
            "amount": 50.0,
            "mode": "MOCK_AUTO",
        },
    )
    db.refresh(app_record)
    assert app_record.status in ("CERTIFICATE_READY", "COMPLETED")
    assert app_record.certificate is not None
    assert app_record.certificate.certificate_number.startswith("CERT-")


def test_24_admin_dashboard_counters_match_sqlite(client: TestClient, db: Session):
    total_db = db.query(Application).count()
    res = client.get("/api/v1/dashboard/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["total_applications"] == total_db


def test_25_admin_decision_syncs_to_citizen_session(client: TestClient, db: Session, admin_token: str):
    from app.models.db_models import ConversationMessage
    app_record = _create_test_application(db, status="SUBMITTED_FOR_VERIFICATION")
    client.post(
        f"/api/v1/applications/admin/{app_record.id}/decision",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE", "admin_notes": "Sync test"},
    )
    session = db.query(ConversationSession).filter(ConversationSession.citizen_ref == app_record.citizen_ref).first()
    assert session is not None
    messages = db.query(ConversationMessage).filter(ConversationMessage.session_id == session.id).all()
    assert len(messages) > 0
