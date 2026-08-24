"""
Citizen Repository — extended for omnichannel identity
"""
import uuid
import random
import hashlib
import datetime
from sqlalchemy.orm import Session
from app.models.db_models import Citizen


class CitizenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, preferred_language: str = "en",
               preferred_channel: str = "WEB") -> Citizen:
        citizen = Citizen(
            citizen_ref=f"CIT-{str(uuid.uuid4())[:12].upper()}",
            preferred_language=preferred_language,
            preferred_channel=preferred_channel,
        )
        self.db.add(citizen)
        self.db.commit()
        self.db.refresh(citizen)
        return citizen

    def get_by_ref(self, citizen_ref: str) -> Citizen | None:
        return self.db.query(Citizen).filter(Citizen.citizen_ref == citizen_ref).first()

    def get_by_identifier(self, identifier: str) -> Citizen | None:
        """Look up citizen by normalized identifier hash via ChannelIdentity."""
        from app.models.db_models import ChannelIdentity
        h = self._hash(self._normalize(identifier))
        ci = self.db.query(ChannelIdentity).filter(ChannelIdentity.identifier_hash == h).first()
        if ci:
            return self.get_by_ref(ci.citizen_ref)
        return None

    def resolve_or_create(self, identifier: str = None, language: str = "en",
                          raw_identifier: str = None, preferred_language: str = None,
                          preferred_channel: str = None) -> Citizen:
        """
        Get-or-create citizen by any channel identifier.
        Normalizes 'whatsapp:XXXX' → 'XXXX' before hashing.
        Uses ChannelIdentity table for lookup.
        """
        from app.models.db_models import ChannelIdentity
        ident = identifier or raw_identifier or "default_user"
        lang = preferred_language or language or "en"
        normalized = self._normalize(ident)
        h = self._hash(normalized)
        channel = preferred_channel or ("WHATSAPP" if ident.lower().startswith("whatsapp:") else "WEB")

        # Look up by identity hash
        ci = self.db.query(ChannelIdentity).filter(ChannelIdentity.identifier_hash == h).first()
        if ci:
            citizen = self.get_by_ref(ci.citizen_ref)
            if citizen and preferred_channel and citizen.preferred_channel != preferred_channel:
                self.update_channel(citizen.citizen_ref, preferred_channel)
            return citizen

        # Create new citizen
        citizen = Citizen(
            citizen_ref=f"CIT-{str(uuid.uuid4())[:12].upper()}",
            preferred_language=lang,
            preferred_channel=channel,
        )
        self.db.add(citizen)
        self.db.flush()  # get citizen_ref without commit

        # Link identity
        identity = ChannelIdentity(
            citizen_ref=citizen.citizen_ref,
            channel=channel,
            identifier_type="PHONE" if channel != "WHATSAPP" else "WHATSAPP_NUMBER",
            identifier_hash=h,
            verified=True,
        )
        self.db.add(identity)
        self.db.commit()
        self.db.refresh(citizen)
        return citizen



    def update_language(self, citizen_ref: str, language: str) -> Citizen | None:
        c = self.get_by_ref(citizen_ref)
        if c:
            c.preferred_language = language
            c.updated_at = datetime.datetime.utcnow()
            self.db.commit()
        return c

    def update_channel(self, citizen_ref: str, channel: str) -> Citizen | None:
        c = self.get_by_ref(citizen_ref)
        if c:
            c.preferred_channel = channel
            c.updated_at = datetime.datetime.utcnow()
            self.db.commit()
        return c

    def generate_otp(self, citizen_ref: str, ttl_seconds: int = 300) -> str:
        """Generate a 6-digit OTP, store hashed. Returns plaintext OTP for delivery."""
        otp = f"{random.randint(0, 999999):06d}"
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl_seconds)
        self.set_otp(citizen_ref, otp_hash, expires_at)
        return otp

    def set_otp(self, citizen_ref: str, otp_hash: str, expires_at: datetime.datetime) -> None:
        c = self.get_by_ref(citizen_ref)
        if c:
            c.otp_hash = otp_hash
            c.otp_expires_at = expires_at
            self.db.commit()

    def verify_otp(self, citizen_ref: str, otp_or_hash: str) -> bool:
        """Accepts plaintext OTP (auto-hashes) or pre-hashed value."""
        c = self.get_by_ref(citizen_ref)
        if not c:
            return False
        if not c.otp_hash or not c.otp_expires_at:
            return False
        if datetime.datetime.utcnow() > c.otp_expires_at:
            return False
        # Accept both plaintext (auto-hash) and pre-hashed
        plain_hash = hashlib.sha256(otp_or_hash.encode()).hexdigest()
        return c.otp_hash in (otp_or_hash, plain_hash)

    def get_all(self) -> list[Citizen]:
        return self.db.query(Citizen).all()

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(identifier: str) -> str:
        """Strip channel prefix, lowercase, remove spaces."""
        for prefix in ("whatsapp:", "email:", "phone:", "ivr:"):
            if identifier.lower().startswith(prefix):
                identifier = identifier[len(prefix):]
        return identifier.strip().lower().replace(" ", "")

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

