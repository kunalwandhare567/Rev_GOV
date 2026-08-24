"""
Phase 15 Tests — Cross-Channel Continuity
Tests that a citizen can start on one channel and continue on another
sharing the same application state in the shared SQLite DB.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Base
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.session_repo import SessionRepository


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


class TestCrossChannel:
    def test_citizen_identity_shared_across_channels(self, db):
        """Same phone number resolves to same citizen on both WhatsApp and Web."""
        repo = CitizenRepository(db)
        c_wa = repo.resolve_or_create("whatsapp:9876543210")
        c_web = repo.resolve_or_create("9876543210")
        # Both should resolve to the same citizen_ref
        assert c_wa.citizen_ref == c_web.citizen_ref

    def test_application_visible_across_channels(self, db):
        """Application created on WhatsApp is accessible from Web portal."""
        citizen_repo = CitizenRepository(db)
        app_repo = ApplicationRepository(db)

        citizen = citizen_repo.resolve_or_create("9876543210")

        # Create application via WhatsApp channel
        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WHATSAPP",
            language="hi",
        )
        assert app.id is not None
        assert app.channel_origin == "WHATSAPP"

        # Fetch from Web channel using same citizen ref
        web_apps = app_repo.get_by_citizen(citizen.citizen_ref, limit=10)
        found = next((a for a in web_apps if a.id == app.id), None)
        assert found is not None, "App created on WhatsApp must be visible on Web"

    def test_last_channel_updated_on_switch(self, db):
        """Switching channels updates last_channel on the application."""
        citizen_repo = CitizenRepository(db)
        app_repo = ApplicationRepository(db)
        citizen = citizen_repo.resolve_or_create("9876543210")

        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WHATSAPP",
            language="en",
        )

        # Citizen continues on Web
        app_repo.update_last_channel(app.id, "WEB")
        db.expire_all()
        refreshed = app_repo.get_by_id(app.id)
        assert refreshed.last_channel == "WEB"
        assert refreshed.channel_origin == "WHATSAPP"  # Origin unchanged

    def test_field_saved_from_whatsapp_visible_on_web(self, db):
        """Fields filled on WhatsApp are accessible from Web review page."""
        citizen_repo = CitizenRepository(db)
        app_repo = ApplicationRepository(db)
        citizen = citizen_repo.resolve_or_create("9876543210")

        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WHATSAPP",
            language="en",
        )

        # Save fields from WhatsApp
        app_repo.save_field(app.id, "applicant_name", "Ramesh Kumar", source="WHATSAPP")
        app_repo.save_field(app.id, "annual_income", "150000", source="WHATSAPP")

        # Read from Web portal
        fields = app_repo.get_fields(app.id, decrypt=True)
        assert fields.get("applicant_name") == "Ramesh Kumar"
        assert fields.get("annual_income") == "150000"

    def test_field_provenance_tracked(self, db):
        """Source channel is recorded per field for officer review."""
        citizen_repo = CitizenRepository(db)
        app_repo = ApplicationRepository(db)
        citizen = citizen_repo.resolve_or_create("9876543210")

        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WHATSAPP",
            language="en",
        )

        app_repo.save_field(app.id, "applicant_name", "Ramesh Kumar", source="WHATSAPP")
        app_repo.save_field(app.id, "annual_income", "150000", source="IVR")

        prov = app_repo.get_fields_with_provenance(app.id)
        prov_map = {f["field_name"]: f for f in prov}

        assert prov_map["applicant_name"]["source"] == "WHATSAPP"
        assert prov_map["annual_income"]["source"] == "IVR"

    def test_tracking_id_generated_on_create(self, db):
        """Every application gets a public tracking ID on creation."""
        citizen_repo = CitizenRepository(db)
        app_repo = ApplicationRepository(db)
        citizen = citizen_repo.resolve_or_create("9876543210")

        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WEB",
            language="en",
        )
        assert app.tracking_id is not None
        assert len(app.tracking_id) > 0

    def test_lookup_by_tracking_id(self, db):
        """Public tracking ID resolves to application (without PII)."""
        citizen_repo = CitizenRepository(db)
        app_repo = ApplicationRepository(db)
        citizen = citizen_repo.resolve_or_create("9876543210")

        app = app_repo.create(
            citizen_ref=citizen.citizen_ref,
            service_id="income_certificate",
            channel_origin="WEB",
            language="en",
        )

        found = app_repo.get_by_tracking_id(app.tracking_id)
        assert found is not None
        assert found.id == app.id
