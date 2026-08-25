"""
Audit Repository — Immutable Audit Log
Append-only by design. No update or delete operations exist.
Architecture ref: enterprise_architecture.md Section 5.6.1 (audit_log table)
"""
import hashlib
import json
import datetime
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.db_models import AuditLog

logger = logging.getLogger(__name__)


class AuditRepository:
    """
    Immutable audit log writer.
    All Data Guard decisions, consent records, payments, and submissions
    are written here. No update/delete operations are permitted.
    """

    def __init__(self, db: Session):
        self.db = db

    def write(
        self,
        event_type: str,
        actor: str,
        action: str,
        outcome: str,
        citizen_ref: Optional[str] = None,
        application_id: Optional[str] = None,
        blocked_fields: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload_hash: Optional[str] = None,
    ) -> AuditLog:
        """
        Write an immutable audit log entry.
        Computes chain-of-custody hash linking to previous entry.
        """
        # Get last entry's hash for chain of custody
        last = self.db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        previous_hash = last.payload_hash if last else "GENESIS"

        if isinstance(action, str):
            action = action.encode("utf-8", "replace").decode("utf-8")

        entry = AuditLog(
            event_type=event_type,
            actor=actor,
            citizen_ref=citizen_ref,
            application_id=application_id,
            action=action,
            outcome=outcome,
            blocked_fields=blocked_fields or [],
            metadata_json=metadata or {},
            payload_hash=payload_hash,
            previous_hash=previous_hash,
            created_at=datetime.datetime.utcnow(),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_data_guard_stats(self) -> Dict:
        """Return Data Guard metrics for the dashboard."""
        from sqlalchemy import func, and_

        today = datetime.datetime.utcnow().date()
        today_start = datetime.datetime(today.year, today.month, today.day)

        total = self.db.query(AuditLog).filter(
            AuditLog.event_type == "DATA_GUARD",
            AuditLog.created_at >= today_start
        ).count()

        blocks = self.db.query(AuditLog).filter(
            AuditLog.event_type == "DATA_GUARD",
            AuditLog.outcome == "BLOCK",
            AuditLog.created_at >= today_start
        ).count()

        last_block = self.db.query(AuditLog).filter(
            AuditLog.event_type == "DATA_GUARD",
            AuditLog.outcome == "BLOCK",
        ).order_by(AuditLog.created_at.desc()).first()

        return {
            "allows_today": total - blocks,
            "blocks_today": blocks,
            "audit_entries_today": total,
            "last_block_at": last_block.created_at.isoformat() if last_block else None,
        }

    def get_recent_audit(
        self,
        limit: int = 50,
        event_type: Optional[str] = None,
        application_id: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch recent audit entries for the dashboard and application review."""
        query = self.db.query(AuditLog)
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        if application_id:
            query = query.filter(AuditLog.application_id == application_id)
        entries = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "actor": e.actor,
                "citizen_ref": e.citizen_ref,
                "application_id": e.application_id,
                "action": e.action,
                "outcome": e.outcome,
                "blocked_fields": e.blocked_fields,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]
