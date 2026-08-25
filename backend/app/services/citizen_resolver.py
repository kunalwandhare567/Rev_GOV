"""
CitizenResolver — resolves any channel identifier to a single citizen_ref.

Rules:
- Phone number and WhatsApp number may differ for same person
- Do NOT merge citizens by name alone
- Use SHA-256 hash of identifiers for storage/lookup (never plaintext)
- OTP verification required before linking phone/email
- WhatsApp numbers are auto-verified (Meta verifies ownership)
"""
import hashlib
from sqlalchemy.orm import Session
from app.models.db_models import Citizen, Application
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.data_layer.repositories.channel_identity_repo import ChannelIdentityRepository
from app.data_layer.repositories.application_repo import ApplicationRepository


class CitizenResolver:
    def __init__(self, db: Session):
        self.db = db
        self.citizen_repo = CitizenRepository(db)
        self.channel_id_repo = ChannelIdentityRepository(db)
        self.app_repo = ApplicationRepository(db)

    def resolve(self, *, whatsapp_number: str = None, phone: str = None,
                email: str = None) -> Citizen | None:
        """
        Find citizen by any identifier across Web, WhatsApp, IVR, Email.
        Returns None if not found.
        """
        target_phone = whatsapp_number or phone
        if target_phone:
            # 1. Try ChannelIdentity lookup for WHATSAPP and IVR
            citizen = (
                self.channel_id_repo.find_citizen_by_identifier("WHATSAPP", target_phone)
                or self.channel_id_repo.find_citizen_by_identifier("IVR", target_phone)
                or self.citizen_repo.get_by_identifier(target_phone)
            )
            if citizen:
                return citizen

        if email:
            citizen = (
                self.channel_id_repo.find_citizen_by_identifier("EMAIL", email)
                or self.citizen_repo.get_by_identifier(email)
            )
            if citizen:
                return citizen

        return None

    def create_or_resolve_whatsapp(self, whatsapp_number: str, language: str = "en") -> Citizen:
        """
        For WhatsApp channel: get or create citizen from WhatsApp number.
        No OTP required — Meta verifies phone ownership.
        """
        citizen = self.resolve(whatsapp_number=whatsapp_number)
        if citizen:
            # Update preferred language if different
            if citizen.preferred_language != language:
                self.citizen_repo.update_language(citizen.citizen_ref, language)
            return citizen

        # Create new citizen
        citizen = self.citizen_repo.create(
            preferred_language=language,
            preferred_channel="WHATSAPP",
        )

        # Link WhatsApp identity (auto-verified)
        self.channel_id_repo.create(
            citizen_ref=citizen.citizen_ref,
            channel="WHATSAPP",
            identifier=whatsapp_number,
            identifier_type="WHATSAPP_NUMBER",
            verified=True,
        )

        return citizen

    def create_or_resolve_web(self, session_citizen_ref: str) -> Citizen | None:
        """For authenticated web sessions — citizen_ref from JWT."""
        return self.citizen_repo.get_by_ref(session_citizen_ref)

    def create_or_resolve_ivr(self, phone_number: str) -> Citizen | None:
        """For IVR — look up by registered phone hash. Don't auto-create."""
        return self.resolve(phone=phone_number)

    def get_active_application(self, citizen_ref: str) -> Application | None:
        """
        Get citizen's most recent non-completed application.
        Used for channel continuity: WhatsApp → Web → Mobile → IVR.
        """
        terminal_statuses = {"COMPLETED", "REJECTED"}
        apps = self.app_repo.get_by_citizen(citizen_ref)
        active = [a for a in apps if a.status not in terminal_statuses]
        if not active:
            return None
        # Most recently updated
        return sorted(active, key=lambda a: a.updated_at, reverse=True)[0]

    def link_phone_to_citizen(self, citizen_ref: str, phone: str) -> bool:
        """Link a phone number to existing citizen (for IVR access)."""
        self.channel_id_repo.create(
            citizen_ref=citizen_ref,
            channel="IVR",
            identifier=phone,
            identifier_type="PHONE",
            verified=True,
        )
        return True

    @staticmethod
    def resolve_citizen_ref(identifier: str, db: Session) -> str:
        """Resolve any channel identifier string to authoritative citizen_ref."""
        resolver = CitizenResolver(db)
        if not identifier:
            c = resolver.citizen_repo.resolve_or_create("default_user")
            return c.citizen_ref
        c = resolver.citizen_repo.get_by_ref(identifier)
        if c:
            return c.citizen_ref
        c = resolver.resolve(phone=identifier, email=identifier if "@" in identifier else None)
        if c:
            return c.citizen_ref
        c = resolver.citizen_repo.resolve_or_create(identifier)
        return c.citizen_ref
