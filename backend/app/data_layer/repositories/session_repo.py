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
        from sqlalchemy import or_
        cutoff = datetime.datetime.utcnow()
        session = (
            self.db.query(ConversationSession)
            .filter(
                ConversationSession.citizen_ref == citizen_ref,
                or_(
                    ConversationSession.expires_at > cutoff,
                    ConversationSession.expires_at.is_(None),
                ),
            )
            .order_by(ConversationSession.updated_at.desc())
            .first()
        )
        return session

    def get_or_recover_session(
        self,
        citizen_ref: str,
        application_id: Optional[str] = None,
        tracking_id: Optional[str] = None,
        channel: str = "WEB",
        language: str = "en",
    ) -> Optional[ConversationSession]:
        """
        Recover conversation session using SQLite Application as recovery anchor:
        1. Active session exists -> Reuse it.
        2. Inactive / expired session exists -> Reactivate it with new TTL.
        3. Application exists in SQLite, but no session exists -> Create new session linked to Application.
           (DO NOT create duplicate Application).
        4. Neither exists -> Return None.
        """
        from app.models.db_models import Application
        from app.data_layer.repositories.application_repo import ApplicationRepository

        now = datetime.datetime.utcnow()
        ttl = datetime.timedelta(minutes=settings.SESSION_TTL_MINUTES)

        # 1. Check for existing active session
        session = self.load_session(citizen_ref)
        if session:
            if application_id and session.application_id != application_id:
                app_check = self.db.query(Application).filter(Application.id == application_id, Application.citizen_ref == citizen_ref).first()
                if app_check:
                    session.application_id = application_id
                    self.save_session(session)
            elif session.application_id:
                app_check = self.db.query(Application).filter(Application.id == session.application_id, Application.citizen_ref == citizen_ref).first()
                if not app_check:
                    session.application_id = None
                    self.save_session(session)
            return session

        # 2. Check for latest inactive/expired session for this citizen
        latest_session = (
            self.db.query(ConversationSession)
            .filter(ConversationSession.citizen_ref == citizen_ref)
            .order_by(ConversationSession.updated_at.desc())
            .first()
        )

        # Look up citizen's active or targeted Application in SQLite
        app_query = self.db.query(Application).filter(Application.citizen_ref == citizen_ref)
        if application_id:
            target_app = app_query.filter(Application.id == application_id).first()
        elif tracking_id:
            target_app = app_query.filter(
                (Application.tracking_id == tracking_id) | (Application.application_number == tracking_id)
            ).first()
        else:
            terminal = ("COMPLETED", "REJECTED")
            target_app = (
                app_query.filter(~Application.status.in_(terminal))
                .order_by(Application.created_at.desc())
                .first()
            )
            if not target_app:
                target_app = app_query.order_by(Application.created_at.desc()).first()

        app_repo = ApplicationRepository(self.db)

        if latest_session:
            # CASE 2: Reactivate existing session
            latest_session.expires_at = now + ttl
            latest_session.updated_at = now
            if target_app and target_app.citizen_ref == citizen_ref:
                latest_session.application_id = target_app.id
                app_fields = app_repo.get_fields(target_app.id)
                if app_fields:
                    latest_session.filled_slots = {**app_fields, **(latest_session.filled_slots or {})}
                if target_app.status in ("APPROVED", "PAYMENT_REQUIRED"):
                    latest_session.current_node = "PAYMENT"
                elif target_app.status in ("OCR_VALIDATION", "DOCUMENT_COLLECTION", "DOCUMENTS_REQUESTED"):
                    latest_session.current_node = "DOCUMENT_UPLOAD"
                elif target_app.status in ("SUBMITTED_FOR_VERIFICATION", "UNDER_REVIEW", "COMPLETED"):
                    latest_session.current_node = "SUBMITTED"
            else:
                latest_session.application_id = None
            self.db.commit()
            self.db.refresh(latest_session)
            return latest_session

        if target_app:
            # CASE 3: Application exists, create linked session without duplicate application
            app_fields = app_repo.get_fields(target_app.id)
            status_node = "SLOT_FILLING"
            if target_app.status in ("APPROVED", "PAYMENT_REQUIRED"):
                status_node = "PAYMENT"
            elif target_app.status in ("OCR_VALIDATION", "DOCUMENT_COLLECTION"):
                status_node = "DOCUMENT_UPLOAD"
            elif target_app.status in ("SUBMITTED_FOR_VERIFICATION", "UNDER_REVIEW", "COMPLETED"):
                status_node = "SUBMITTED"

            new_session = ConversationSession(
                citizen_ref=citizen_ref,
                application_id=target_app.id,
                current_node=status_node,
                channel=target_app.last_channel or target_app.channel_origin or channel,
                language=target_app.language or language,
                filled_slots=app_fields or {},
                missing_slots=[],
                validation_errors=[],
                correction_history=[],
                document_refs=[d.file_ref for d in (target_app.documents or []) if d.file_ref],
                payment_status=target_app.payment_status or "PENDING",
                consent_given=True,
                anomaly_score=target_app.anomaly_score or 0.0,
                channel_history=[target_app.channel_origin or channel],
                expires_at=now + ttl,
            )
            self.db.add(new_session)
            self.db.commit()
            self.db.refresh(new_session)
            return new_session

        return None

    def get_session_by_application_id(self, application_id: str) -> Optional[ConversationSession]:
        """Find the conversation session attached to an application_id."""
        return (
            self.db.query(ConversationSession)
            .filter(ConversationSession.application_id == application_id)
            .order_by(ConversationSession.updated_at.desc())
            .first()
        )

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
        if isinstance(content, str):
            content = content.encode("utf-8", "replace").decode("utf-8")

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
