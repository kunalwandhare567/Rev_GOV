"""
Data Guard Demo API
Live-demoable endpoint to show the trust boundary enforcement in action.
Architecture ref: Section 5.5.3 Live Demo Scenario for Data Guard
"""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.data_guard.guard import DataGuard, DataClassifier, DataGuardBlockedError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data-guard", tags=["data-guard"])


class DataGuardTestRequest(BaseModel):
    payload: Any
    destination: str = "cloud_llm"
    caller: str = "demo_client"
    operation: str = "translate"
    data_classification: Optional[str] = None  # "SYNTHETIC" to allow quasi-identifiers


@router.post("/check")
def test_data_guard(req: DataGuardTestRequest, db: Session = Depends(get_db)):
    """
    Live demo endpoint: Test a payload against the Data Guard policy.
    Shows ALLOW or BLOCK decision in real time with audit trail.

    Example BLOCKED payload (copy-paste into Swagger UI):
    {
      "payload": {"message": "translate this", "applicant_name": "Ramesh Kumar"},
      "destination": "cloud_llm",
      "operation": "translate"
    }

    Example ALLOWED payload:
    {
      "payload": {"message": "translate 'income certificate' to Tamil"},
      "destination": "cloud_llm",
      "operation": "translate"
    }
    """
    from app.data_layer.repositories.audit_repo import AuditRepository
    audit_repo = AuditRepository(db)
    guard = DataGuard(audit_logger=audit_repo)

    try:
        result = guard.check(
            payload=req.payload,
            destination=req.destination,
            caller=req.caller,
            operation=req.operation,
            data_classification=req.data_classification,
        )
        return {
            "decision": "ALLOW",
            "message": "✅ Payload is safe to send. No restricted PII detected.",
            "payload_hash": result.payload_hash,
            "timestamp": result.timestamp.isoformat(),
        }
    except DataGuardBlockedError as e:
        return {
            "decision": "BLOCK",
            "message": f"🛑 {e.reason}",
            "blocked_fields": e.blocked_fields,
            "audit_logged": True,
        }


@router.post("/classify")
def classify_payload(payload: Any, db: Session = Depends(get_db)):
    """Classify all fields in a payload by data sensitivity level."""
    restricted, quasi = DataClassifier.scan_payload(payload)
    all_fields = list(set(restricted + quasi))
    non_sensitive = []

    if isinstance(payload, dict):
        for key in payload.keys():
            if key.lower() not in [f.lower() for f in all_fields]:
                non_sensitive.append(key)

    return {
        "restricted_fields": restricted,
        "quasi_identifier_fields": quasi,
        "non_sensitive_fields": non_sensitive,
        "summary": {
            "can_send_to_cloud": len(restricted) == 0 and len(quasi) == 0,
            "requires_anonymization": len(quasi) > 0,
            "must_stay_on_premise": len(restricted) > 0,
        },
    }


@router.get("/policy")
def get_data_guard_policy():
    """Return the current data classification policy (for transparency)."""
    from app.data_guard.guard import RESTRICTED_FIELDS, QUASI_IDENTIFIER_FIELDS
    return {
        "policy_version": "1.0",
        "enforcement_mode": "STRICT",
        "trust_zones": {
            "zone_0": "On-Premise Core — all RESTRICTED data stays here",
            "zone_1": "Sanitized Proxy — QUASI_IDENTIFIER with SYNTHETIC flag allowed",
            "zone_2": "Cloud Services — NON_SENSITIVE only",
        },
        "restricted_fields": sorted(list(RESTRICTED_FIELDS)),
        "quasi_identifier_fields": sorted(list(QUASI_IDENTIFIER_FIELDS)),
        "rules": [
            "RESTRICTED fields → ALWAYS BLOCK from cloud, regardless of context",
            "QUASI_IDENTIFIER fields → BLOCK unless data_classification=SYNTHETIC and k<3",
            "NON_SENSITIVE fields → ALLOW",
        ],
    }
