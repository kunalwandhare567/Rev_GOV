"""
Citizen Repository
Manages tokenized citizen records. Never stores raw PII in the citizens table.
"""
import hashlib
import hmac
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.models.db_models import Citizen
from app.core.config import settings

logger = logging.getLogger(__name__)


def _derive_citizen_ref(raw_identifier: str) -> str:
    """
    Derive stable, anonymized citizen_ref from raw identifier (phone, Aadhaar token, etc.).
    One-way HMAC-SHA256: same input always produces same token, but cannot be reversed.
    """
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, raw_identifier.encode(), hashlib.sha256).hexdigest()[:32]


class CitizenRepository:

    def __init__(self, db: Session):
        self.db = db

    def resolve_or_create(
        self,
        raw_identifier: str,
        preferred_language: str = "en",
        preferred_channel: str = "WEB",
    ) -> Citizen:
        """
        Resolve citizen_ref from raw identifier (channel-specific ID like phone number).
        Creates a new citizen record if not found.
        """
        citizen_ref = _derive_citizen_ref(raw_identifier)
        citizen = self.db.query(Citizen).filter(
            Citizen.citizen_ref == citizen_ref
        ).first()

        if not citizen:
            citizen = Citizen(
                citizen_ref=citizen_ref,
                preferred_language=preferred_language,
                preferred_channel=preferred_channel,
            )
            self.db.add(citizen)
            self.db.commit()
            self.db.refresh(citizen)
            logger.info(f"Created new citizen: {citizen_ref}")

        return citizen

    def get_by_ref(self, citizen_ref: str) -> Optional[Citizen]:
        return self.db.query(Citizen).filter(
            Citizen.citizen_ref == citizen_ref
        ).first()

    def update_preferences(
        self,
        citizen_ref: str,
        language: Optional[str] = None,
        literacy_level: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Optional[Citizen]:
        citizen = self.get_by_ref(citizen_ref)
        if not citizen:
            return None
        if language:
            citizen.preferred_language = language
        if literacy_level:
            citizen.literacy_level = literacy_level
        if channel:
            citizen.preferred_channel = channel
        self.db.commit()
        self.db.refresh(citizen)
        return citizen
