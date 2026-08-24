"""
Phase 15 Tests — Citizen Resolver
Tests unified citizen identity across multiple channels.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Base
from app.data_layer.repositories.citizen_repo import CitizenRepository


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


class TestCitizenResolver:
    def test_create_new_citizen_by_phone(self, db):
        repo = CitizenRepository(db)
        citizen = repo.resolve_or_create("9876543210")
        assert citizen is not None
        assert citizen.citizen_ref is not None
        assert citizen.citizen_ref.startswith("CIT-")

    def test_resolve_same_phone_twice(self, db):
        repo = CitizenRepository(db)
        c1 = repo.resolve_or_create("9876543210")
        c2 = repo.resolve_or_create("9876543210")
        assert c1.citizen_ref == c2.citizen_ref, "Same phone must resolve to same citizen"

    def test_resolve_by_whatsapp_number(self, db):
        repo = CitizenRepository(db)
        c1 = repo.resolve_or_create("whatsapp:9876543210")
        assert c1.citizen_ref is not None

    def test_different_phones_get_different_refs(self, db):
        repo = CitizenRepository(db)
        c1 = repo.resolve_or_create("9876543210")
        c2 = repo.resolve_or_create("9999999999")
        assert c1.citizen_ref != c2.citizen_ref

    def test_update_language_preference(self, db):
        repo = CitizenRepository(db)
        citizen = repo.resolve_or_create("9876543210")
        repo.update_language(citizen.citizen_ref, "hi")
        db.expire_all()
        updated = repo.get_by_ref(citizen.citizen_ref)
        assert updated.preferred_language == "hi"

    def test_generate_and_verify_otp(self, db):
        repo = CitizenRepository(db)
        citizen = repo.resolve_or_create("9876543210")
        otp = repo.generate_otp(citizen.citizen_ref)
        assert otp is not None
        assert len(otp) == 6
        assert otp.isdigit()
        result = repo.verify_otp(citizen.citizen_ref, otp)
        assert result is True

    def test_otp_invalid_value(self, db):
        repo = CitizenRepository(db)
        citizen = repo.resolve_or_create("9876543210")
        repo.generate_otp(citizen.citizen_ref)
        assert repo.verify_otp(citizen.citizen_ref, "000000") is False
