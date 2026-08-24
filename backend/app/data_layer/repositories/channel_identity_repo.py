"""
ChannelIdentity Repository — maps channel identifiers → citizen_ref
"""
import hashlib
from sqlalchemy.orm import Session
from app.models.db_models import ChannelIdentity, Citizen
import datetime


def _hash(identifier: str) -> str:
    return hashlib.sha256(identifier.strip().lower().encode()).hexdigest()


class ChannelIdentityRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_citizen_by_hash(self, channel: str, identifier_hash: str) -> Citizen | None:
        ci = (
            self.db.query(ChannelIdentity)
            .filter(
                ChannelIdentity.channel == channel,
                ChannelIdentity.identifier_hash == identifier_hash,
            )
            .first()
        )
        if ci:
            return self.db.query(Citizen).filter(Citizen.citizen_ref == ci.citizen_ref).first()
        return None

    def find_citizen_by_identifier(self, channel: str, identifier: str) -> Citizen | None:
        return self.find_citizen_by_hash(channel, _hash(identifier))

    def create(self, citizen_ref: str, channel: str, identifier: str,
               identifier_type: str, verified: bool = True) -> ChannelIdentity:
        h = _hash(identifier)
        ci = ChannelIdentity(
            citizen_ref=citizen_ref,
            channel=channel,
            identifier_hash=h,
            identifier_type=identifier_type,
            verified=verified,
            verified_at=datetime.datetime.utcnow() if verified else None,
        )
        self.db.add(ci)
        self.db.commit()
        self.db.refresh(ci)
        return ci

    def get_by_citizen(self, citizen_ref: str) -> list[ChannelIdentity]:
        return (
            self.db.query(ChannelIdentity)
            .filter(ChannelIdentity.citizen_ref == citizen_ref)
            .all()
        )

    def hash(self, identifier: str) -> str:
        return _hash(identifier)
