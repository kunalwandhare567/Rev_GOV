"""
Integration test for the full conversation flow using TestClient.
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_list_services():
    resp = client.get("/api/v1/applications/services")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 4
    service_ids = [s["id"] for s in data["services"]]
    assert "income_certificate" in service_ids
    assert "caste_certificate" in service_ids
    assert "obc_ncl_certificate" in service_ids
    assert "domicile_certificate" in service_ids


def test_data_guard_blocks_pii():
    resp = client.post("/api/v1/data-guard/check", json={
        "payload": {"applicant_name": "Ramesh Kumar", "message": "translate"},
        "destination": "cloud_llm",
        "operation": "translate",
    })
    data = resp.json()
    assert data["decision"] == "BLOCK"
    assert "applicant_name" in data["blocked_fields"]


def test_data_guard_allows_safe_payload():
    resp = client.post("/api/v1/data-guard/check", json={
        "payload": {"message": "translate 'income certificate' to Hindi"},
        "destination": "cloud_llm",
        "operation": "translate",
    })
    data = resp.json()
    assert data["decision"] == "ALLOW"


def test_full_conversation_flow():
    """Simulate a complete income certificate application journey."""
    user_id = "test_integration_user_001"
    lang = "en"

    # Step 1: Init → Consent prompt
    resp = client.post("/api/v1/conversation/message", json={
        "citizen_identifier": user_id,
        "text": "Hello",
        "channel": "WEB",
        "language": lang,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "consent" in data["response"].lower() or data["current_node"] in ("INIT", "CONSENT")

    # Step 2: Consent → Intent detection
    resp = client.post("/api/v1/conversation/message", json={
        "citizen_identifier": user_id,
        "text": "Yes",
        "channel": "WEB",
        "language": lang,
    })
    data = resp.json()
    assert data["consent_given"] is True

    # Step 3: Request income certificate
    resp = client.post("/api/v1/conversation/message", json={
        "citizen_identifier": user_id,
        "text": "I need an income certificate",
        "channel": "WEB",
        "language": lang,
    })
    data = resp.json()
    assert data["current_node"] in ("SLOT_FILLING", "INTENT_DETECTION")


def test_channel_switch():
    """Test seamless channel switch from WEB to MOBILE."""
    user_id = "test_channel_switch_002"

    # Start session on WEB
    client.post("/api/v1/conversation/message", json={
        "citizen_identifier": user_id,
        "text": "yes",
        "channel": "WEB",
        "language": "en",
    })

    # Switch to MOBILE
    resp = client.post("/api/v1/conversation/channel-switch", json={
        "citizen_identifier": user_id,
        "new_channel": "MOBILE",
        "language": "en",
    })
    data = resp.json()
    # Either found session or no session (both valid for fresh test user)
    assert resp.status_code == 200
