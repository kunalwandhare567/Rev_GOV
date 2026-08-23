"""
Conversation Session Repository — Context Vault
Channel-agnostic session store backed by SQLite.
Keyed by citizen_ref, enables seamless channel switching.
Architecture ref: Section 5.2.3 Context Vault Design
"""
import datetime
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.db_models import ConversationSession, ConversationMessage
from app.core.config import settings

logger = logging.getLogger(__name__)


class SessionRepository:
    """
    Context Vault implementation.
    In production: Redis hot cache + SQLite cold store.
    POC: SQLite only (sufficient for demo).
    """

    def __init__(self, db: Session):
        self.db = db

    def load_session(self, citizen_ref: str) -> Optional[ConversationSession]:
        """Load the most recent active session for a citizen."""
        cutoff = datetime.datetime.utcnow()
        session = (
            self.db.query(ConversationSession)
            .filter(
                ConversationSession.citizen_ref == citizen_ref,
                ConversationSession.expires_at > cutoff,
            )
            .order_by(ConversationSession.updated_at.desc())
            .first()
        )
        return session

    def create_session(
        self,
        citizen_ref: str,
        channel: str,
        language: str = "en",
        service_id: Optional[str] = None,
    ) -> ConversationSession:
        """Create a new conversation session."""
        ttl = datetime.timedelta(minutes=settings.SESSION_TTL_MINUTES)
        session = ConversationSession(
            citizen_ref=citizen_ref,
            current_node="INIT",
            channel=channel,
            language=language,
            filled_slots={},
            missing_slots=[],
            validation_errors=[],
            correction_history=[],
            document_refs=[],
            payment_status="PENDING",
            consent_given=False,
            anomaly_score=0.0,
            channel_history=[channel],
            expires_at=datetime.datetime.utcnow() + ttl,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def save_session(self, session: ConversationSession) -> ConversationSession:
        """Persist session state changes."""
        session.updated_at = datetime.datetime.utcnow()
        # Extend TTL on every interaction
        session.expires_at = datetime.datetime.utcnow() + datetime.timedelta(
            minutes=settings.SESSION_TTL_MINUTES
        )
        self.db.commit()
        self.db.refresh(session)
        return session

    def transfer_channel(
        self, citizen_ref: str, new_channel: str
    ) -> Optional[ConversationSession]:
        """
        Handle channel switch: update channel field, preserve all state.
        This is the core of omnichannel continuity.
        """
        session = self.load_session(citizen_ref)
        if session:
            if new_channel not in session.channel_history:
                session.channel_history = session.channel_history + [new_channel]
            session.channel = new_channel
            return self.save_session(session)
        return None

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        language: str = "en",
        modality: str = "TEXT",
    ) -> ConversationMessage:
        """Append a message to the conversation history."""
        msg = ConversationMessage(
            session_id=session_id,
            role=role,
            content=content,
            language=language,
            modality=modality,
        )
        self.db.add(msg)
        self.db.commit()
        return msg

    def get_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get conversation history for escalation summary."""
        messages = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "role": m.role,
                "content": m.content,
                "language": m.language,
                "modality": m.modality,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]

    def get_active_sessions_count(self) -> int:
        """Dashboard metric: count of active sessions."""
        return self.db.query(ConversationSession).filter(
            ConversationSession.expires_at > datetime.datetime.utcnow()
        ).count()
