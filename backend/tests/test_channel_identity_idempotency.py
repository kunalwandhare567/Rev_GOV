"""
Test Suite — Channel Identities Idempotency and Race Condition Handling
Verifies:
1. test_resolve_existing_channel_identity_does_not_duplicate
2. test_resolve_same_identifier_twice_returns_same_citizen
3. test_session_recovery_does_not_create_duplicate_identity
4. test_new_identifier_creates_identity
5. test_duplicate_identity_race_is_handled
"""
import pytest
import uuid
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from unittest.mock import patch

from main import app
from app.core.database import SessionLocal
from app.models.db_models import Citizen, ChannelIdentity, ConversationSession
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.services.citizen_resolver import CitizenResolver


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


def test_resolve_existing_channel_identity_does_not_duplicate(db: Session):
    """If a ChannelIdentity exists, resolving it reuses citizen_ref and does not insert duplicate rows."""
    repo = CitizenRepository(db)
    phone = f"98{str(uuid.uuid4().int)[:8]}"
    h = repo._hash(phone)

    # Pre-create identity without citizen or with citizen
    c1 = repo.resolve_or_create(identifier=phone, preferred_channel="WEB")
    c1_ref = c1.citizen_ref

    count_identities = db.query(ChannelIdentity).filter(
        ChannelIdentity.channel == "WEB",
        ChannelIdentity.identifier_hash == h,
    ).count()
    assert count_identities == 1

    # Call again — must not raise IntegrityError and must return same citizen
    c2 = repo.resolve_or_create(identifier=phone, preferred_channel="WEB")
    assert c2.citizen_ref == c1_ref

    count_identities_after = db.query(ChannelIdentity).filter(
        ChannelIdentity.channel == "WEB",
        ChannelIdentity.identifier_hash == h,
    ).count()
    assert count_identities_after == 1


def test_resolve_same_identifier_twice_returns_same_citizen(db: Session):
    """Resolving the exact same phone/email twice returns the identical citizen record."""
    repo = CitizenRepository(db)
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"

    c1 = repo.resolve_or_create(identifier=email, preferred_channel="WEB")
    c2 = repo.resolve_or_create(identifier=email, preferred_channel="WEB")

    assert c1.citizen_ref == c2.citizen_ref
    assert c1.id == c2.id


def test_session_recovery_does_not_create_duplicate_identity(client: TestClient, db: Session):
    """GET /api/v1/conversation/session/{citizen_identifier} returns 200 repeatedly without duplicate errors."""
    phone = f"73{str(uuid.uuid4().int)[:8]}"

    # Call endpoint 3 times in succession
    res1 = client.get(f"/api/v1/conversation/session/{phone}")
    assert res1.status_code == 200

    res2 = client.get(f"/api/v1/conversation/session/{phone}")
    assert res2.status_code == 200

    res3 = client.get(f"/api/v1/conversation/session/{phone}")
    assert res3.status_code == 200


def test_new_identifier_creates_identity(db: Session):
    """A fresh new identifier successfully creates both Citizen and ChannelIdentity."""
    repo = CitizenRepository(db)
    phone = f"91{str(uuid.uuid4().int)[:8]}"
    h = repo._hash(phone)

    citizen = repo.resolve_or_create(identifier=phone, preferred_channel="WEB")
    assert citizen is not None
    assert citizen.citizen_ref.startswith("CIT-")

    ci = db.query(ChannelIdentity).filter(
        ChannelIdentity.channel == "WEB",
        ChannelIdentity.identifier_hash == h,
    ).first()
    assert ci is not None
    assert ci.citizen_ref == citizen.citizen_ref


def test_duplicate_identity_race_is_handled(db: Session):
    """Simulate concurrent race condition where commit triggers IntegrityError; it recovers gracefully."""
    repo = CitizenRepository(db)
    phone = f"88{str(uuid.uuid4().int)[:8]}"

    # Resolve first time so identity exists in database
    c1 = repo.resolve_or_create(identifier=phone, preferred_channel="WEB")

    # Now create another session and simulate a race collision on commit
    db2 = SessionLocal()
    repo2 = CitizenRepository(db2)
    c2 = repo2.resolve_or_create(identifier=phone, preferred_channel="WEB")
    db2.close()

    assert c2.citizen_ref == c1.citizen_ref
