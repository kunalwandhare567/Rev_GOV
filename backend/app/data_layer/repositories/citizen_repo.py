"""
Citizen Repository — extended for omnichannel identity
"""
import uuid
import random
import hashlib
import datetime
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.db_models import Citizen

logger = logging.getLogger(__name__)


class CitizenRepository:
    def __init__(self, db: Session):
        self.db = db

    def _next_citizen_id(self) -> str:
        """Generate formatted sequential citizen ID: CIT-001, CIT-002, etc. Ensures uniqueness."""
        all_refs = [r[0] for r in self.db.query(Citizen.citizen_ref).all() if r[0] and r[0].startswith("CIT-")]
        max_num = 0
        for r in all_refs:
            try:
                num = int(r.split("-")[1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
        seq = max_num + 1
        return f"CIT-{seq:03d}"

    def create(self, name: str = None, phone: str = None, email: str = None, address: str = None,
               preferred_language: str = "en", preferred_channel: str = "WEB") -> Citizen:
        citizen_ref = self._next_citizen_id()
        citizen = Citizen(
            citizen_ref=citizen_ref,
            name=name,
            phone=phone,
            email=email,
            address=address,
            preferred_language=preferred_language,
            preferred_channel=preferred_channel,
        )
        self.db.add(citizen)
        self.db.commit()
        self.db.refresh(citizen)
        return citizen

    def update_profile(self, citizen_ref: str, name: str = None, phone: str = None,
                       email: str = None, address: str = None) -> Citizen | None:
        c = self.get_by_ref(citizen_ref)
        if c:
            if name is not None: c.name = name
            if phone is not None: c.phone = phone
            if email is not None: c.email = email
            if address is not None: c.address = address
            c.updated_at = datetime.datetime.utcnow()
            self.db.commit()
            self.db.refresh(c)
        return c

    def get_by_ref(self, citizen_ref: str) -> Citizen | None:
        return self.db.query(Citizen).filter(Citizen.citizen_ref == citizen_ref).first()

    get = get_by_ref

    def get_by_identifier(self, identifier: str) -> Citizen | None:
        """Look up citizen by normalized identifier hash via ChannelIdentity or direct email/phone."""
        if not identifier:
            return None
        normalized = self._normalize(identifier)
        # Try direct match first if phone, email, or citizen_ref
        direct = self.db.query(Citizen).filter(
            (Citizen.phone == identifier) | (Citizen.email == identifier) | (Citizen.citizen_ref == identifier) |
            (Citizen.phone == normalized) | (Citizen.email == normalized)
        ).first()
        if direct:
            return direct

        from app.models.db_models import ChannelIdentity
        h = self._hash(normalized)
        ci = self.db.query(ChannelIdentity).filter(ChannelIdentity.identifier_hash == h).first()
        if ci:
            return self.get_by_ref(ci.citizen_ref)
        return None

    def resolve_or_create(self, identifier: str = None, language: str = "en",
                          raw_identifier: str = None, preferred_language: str = None,
                          preferred_channel: str = None, name: str = None) -> Citizen:
        """
        Get-or-create citizen by any channel identifier idempotently.
        Normalizes 'whatsapp:XXXX' → 'XXXX' before hashing.
        Reuses existing channel identity and citizen_ref without violating unique constraints.
        Handles race conditions gracefully.
        """
        from app.models.db_models import ChannelIdentity
        ident = identifier or raw_identifier or "default_user"
        lang = preferred_language or language or "en"
        normalized = self._normalize(ident)
        h = self._hash(normalized)
        channel = preferred_channel or ("WHATSAPP" if ident.lower().startswith("whatsapp:") else "WEB")

        # 1. Look up by direct phone/email or existing ChannelIdentity
        citizen = self.get_by_identifier(ident)
        if citizen:
            if preferred_channel and citizen.preferred_channel != preferred_channel:
                self.update_channel(citizen.citizen_ref, preferred_channel)
            return citizen

        # 2. Check if a ChannelIdentity already exists for this (channel, identifier_hash) or hash
        existing_ci = (
            self.db.query(ChannelIdentity)
            .filter(
                ChannelIdentity.channel == channel,
                ChannelIdentity.identifier_hash == h,
            )
            .first()
        )
        if not existing_ci:
            existing_ci = (
                self.db.query(ChannelIdentity)
                .filter(ChannelIdentity.identifier_hash == h)
                .first()
            )

        if existing_ci:
            # Reuse existing citizen_ref; do NOT insert a duplicate ChannelIdentity
            existing_citizen = self.get_by_ref(existing_ci.citizen_ref)
            if existing_citizen:
                if preferred_channel and existing_citizen.preferred_channel != preferred_channel:
                    self.update_channel(existing_citizen.citizen_ref, preferred_channel)
                return existing_citizen

            # Citizen record was missing for existing identity — recreate Citizen with same citizen_ref
            citizen = Citizen(
                citizen_ref=existing_ci.citizen_ref,
                name=name,
                phone=normalized if "@" not in normalized and normalized.replace("+", "").isdigit() else None,
                email=normalized if "@" in normalized else None,
                preferred_language=lang,
                preferred_channel=channel,
            )
            self.db.add(citizen)
            try:
                self.db.commit()
                self.db.refresh(citizen)
                return citizen
            except Exception as e:
                logger.warning(f"Error persisting citizen for existing identity: {e}")
                self.db.rollback()
                c = self.get_by_ref(existing_ci.citizen_ref)
                if c:
                    return c

        # 3. Create new citizen and link new ChannelIdentity with race-condition safety
        citizen = Citizen(
            citizen_ref=self._next_citizen_id(),
            name=name,
            phone=normalized if "@" not in normalized and normalized.replace("+", "").isdigit() else None,
            email=normalized if "@" in normalized else None,
            preferred_language=lang,
            preferred_channel=channel,
        )
        self.db.add(citizen)
        self.db.flush()  # obtain citizen_ref

        identity = ChannelIdentity(
            citizen_ref=citizen.citizen_ref,
            channel=channel,
            identifier_type="PHONE" if channel != "WHATSAPP" else "WHATSAPP_NUMBER",
            identifier_hash=h,
            verified=True,
        )
        self.db.add(identity)

        try:
            self.db.commit()
            self.db.refresh(citizen)
            return citizen
        except (IntegrityError, Exception) as e:
            # Handle concurrent creation race condition
            logger.info(f"Handled concurrent citizen creation collision for hash {h[:8]}: {e}")
            self.db.rollback()

            # Re-query existing ChannelIdentity created concurrently
            ci_race = (
                self.db.query(ChannelIdentity)
                .filter(
                    ChannelIdentity.channel == channel,
                    ChannelIdentity.identifier_hash == h,
                )
                .first()
            )
            if not ci_race:
                ci_race = (
                    self.db.query(ChannelIdentity)
                    .filter(ChannelIdentity.identifier_hash == h)
                    .first()
                )

            if ci_race:
                c = self.get_by_ref(ci_race.citizen_ref)
                if c:
                    return c
                c = Citizen(
                    citizen_ref=ci_race.citizen_ref,
                    name=name,
                    phone=normalized if "@" not in normalized and normalized.replace("+", "").isdigit() else None,
                    email=normalized if "@" in normalized else None,
                    preferred_language=lang,
                    preferred_channel=channel,
                )
                self.db.add(c)
                self.db.commit()
                self.db.refresh(c)
                return c

            fallback = self.get_by_identifier(ident)
            if fallback:
                return fallback
            raise



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

