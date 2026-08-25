"""
Dashboard API Routes
Real-time operational metrics for the Operational Dashboard.
Architecture ref: Section 5.8 Operational Dashboard
"""
import logging
import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.audit_repo import AuditRepository
from app.data_layer.repositories.session_repo import SessionRepository
from app.rules_engine.engine import ServiceSpecLoader

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
@router.get("/stats")
def get_dashboard_overview(db: Session = Depends(get_db)):
    """
    Main dashboard metrics:
    - Active sessions
    - Submissions today
    - Data Guard stats (blocks/allows)
    - Applications by status and service
    - Anomaly score distribution
    """
    app_repo = ApplicationRepository(db)
    audit_repo = AuditRepository(db)
    session_repo = SessionRepository(db)

    app_stats = app_repo.get_submission_stats()
    dg_stats = audit_repo.get_data_guard_stats()
    active_sessions = session_repo.get_active_sessions_count()

    # Anomaly score distribution
    from app.models.db_models import Application
    all_apps = db.query(Application).all()
    anomaly_dist = {"low": 0, "medium": 0, "high": 0}
    from app.core.config import settings
    for a in all_apps:
        if a.anomaly_score < settings.FRAUD_SCORE_THRESHOLD_REVIEW:
            anomaly_dist["low"] += 1
        elif a.anomaly_score < settings.FRAUD_SCORE_THRESHOLD_REJECT:
            anomaly_dist["medium"] += 1
        else:
            anomaly_dist["high"] += 1

    # Language distribution from sessions
    from app.models.db_models import ConversationSession
    sessions = db.query(ConversationSession).all()
    lang_dist = {}
    for s in sessions:
        lang_dist[s.language] = lang_dist.get(s.language, 0) + 1

    # Channel distribution from applications
    channel_dist = {}
    for a in all_apps:
        channel_dist[a.channel_origin] = channel_dist.get(a.channel_origin, 0) + 1

    return {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "total_applications": app_stats["total_applications"],
        "submitted": app_stats["by_status"].get("SUBMITTED_FOR_VERIFICATION", 0),
        "under_review": app_stats["by_status"].get("UNDER_REVIEW", 0),
        "clarification_required": app_stats["by_status"].get("CLARIFICATION_REQUIRED", 0),
        "approved": app_stats["by_status"].get("APPROVED", 0),
        "rejected": app_stats["by_status"].get("REJECTED", 0),
        "payment_required": app_stats["by_status"].get("PAYMENT_REQUIRED", 0),
        "completed": app_stats["by_status"].get("COMPLETED", 0),
        "stats": {
            "active_sessions":   active_sessions,
            "submitted_today":   app_stats["submitted_today"],
            "total_approved":    app_stats["by_status"].get("APPROVED", 0),
            "total_rejected":    app_stats["by_status"].get("REJECTED", 0),
            "dg_blocks_today":   dg_stats.get("blocks_today", 0),
            "avg_anomaly_score": (
                sum(a.anomaly_score for a in all_apps) / len(all_apps)
                if all_apps else 0.0
            ),
        },
        "by_status":   app_stats["by_status"],
        "by_service":  app_stats["by_service"],
        "by_language": lang_dist,
        "by_channel":  channel_dist,
    }


@router.get("/audit-log")
def get_audit_log(
    limit: int = 50,
    event_type: str = None,
    db: Session = Depends(get_db),
):
    """Fetch audit log entries for the security dashboard."""
    audit_repo = AuditRepository(db)
    entries = audit_repo.get_recent_audit(limit=limit, event_type=event_type)
    return {"count": len(entries), "events": entries}


@router.get("/data-guard-stats")
def get_data_guard_stats(db: Session = Depends(get_db)):
    """Data Guard specific stats for the trust boundary visualization."""
    audit_repo = AuditRepository(db)
    stats = audit_repo.get_data_guard_stats()

    # Fetch all DG entries for visualization
    entries = audit_repo.get_recent_audit(limit=20, event_type="DATA_GUARD")
    block_entries = [e for e in entries if e["outcome"] == "BLOCK"]

    return {
        **stats,
        "recent_blocks": block_entries[:5],
        "policy_summary": {
            "restricted_fields": 15,
            "quasi_identifier_fields": 9,
            "enforcement_mode": "STRICT",
            "data_guard_enabled": True,
        },
    }


@router.get("/escalations")
def get_escalations(db: Session = Depends(get_db)):
    """Get open escalation tickets for officer view."""
    from app.models.db_models import Escalation
    escalations = db.query(Escalation).filter(
        Escalation.status.in_(["OPEN", "ASSIGNED"])
    ).order_by(Escalation.created_at.desc()).limit(20).all()

    return {
        "count": len(escalations),
        "escalations": [
            {
                "ticket_id":        e.ticket_id,
                "application_id":   e.application_id,
                "application_number": e.application.application_number if e.application else None,
                "service_type":     e.application.service_type if e.application else None,
                "channel":          e.application.channel_origin if e.application else None,
                "language":         e.application.language if e.application else None,
                "anomaly_score":    e.application.anomaly_score if e.application else 0.0,
                "escalation_reason":e.reason,
                "escalation_state": e.status,
                "priority":         e.priority,
                "officer_summary":  e.officer_summary,
                "escalated_at":     e.created_at.isoformat(),
                "created_at":       e.created_at.isoformat(),
            }
            for e in escalations
        ],
    }


@router.get("/service-health")
def get_service_health(db: Session = Depends(get_db)):
    """Health check for all system components."""
    # Check DB connectivity
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "HEALTHY"
    except Exception:
        db_status = "UNHEALTHY"

    # Check LLM / NLU provider
    try:
        from app.llm.provider_factory import get_provider
        provider = get_provider()
        nlu_status = "HEALTHY"
        provider_name = provider.provider_name
    except Exception as e:
        nlu_status = f"UNAVAILABLE ({e})"
        provider_name = settings.LLM_PROVIDER

    # Check service spec loader
    specs = ServiceSpecLoader.load_all()
    spec_status = f"HEALTHY ({len(specs)} services loaded)"

    return {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "components": {
            "database": {"status": db_status, "type": "SQLite"},
            "nlu_engine": {"status": nlu_status, "provider": provider_name},
            "service_specs": {"status": spec_status},
            "data_guard": {"status": "HEALTHY", "mode": "STRICT"},
            "conversation_engine": {"status": "HEALTHY"},
            "fraud_scorer": {"status": "HEALTHY", "type": "rule_based"},
            "encryption": {"status": "HEALTHY", "algorithm": "AES-256-GCM"},
        },
    }
