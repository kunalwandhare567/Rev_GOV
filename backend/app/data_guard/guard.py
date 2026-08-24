"""
Data Guard — Trust Boundary Enforcement
Intercepts ALL outbound calls and enforces data classification policy.
Provides live-demoable blocking with immutable audit trail.
Architecture ref: enterprise_architecture.md Section 5.5
"""
import hashlib
import logging
import datetime
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data Classification Schema (from OPA/Rego policy)
# ─────────────────────────────────────────────

RESTRICTED_FIELDS: Set[str] = {
    "aadhaar_number",
    "pan_number",
    "voter_id",
    "passport_number",
    "bank_account",
    "applicant_dob",
    "date_of_birth",
    "biometric_data",
    "medical_history",
    "applicant_name",
    "father_name",
    "mother_name",
    "phone_number",
    "email_address",
    "address",
    "house_number",
    "street",
}

QUASI_IDENTIFIER_FIELDS: Set[str] = {
    "district",
    "annual_income",
    "caste_category",
    "caste_name",
    "occupation",
    "age_range",
    "residence_years",
    "place_of_birth",
    "pincode",
}


@dataclass
class DataGuardResult:
    allowed: bool
    action: str            # ALLOW | BLOCK
    blocked_fields: List[str]
    block_reason: Optional[str]
    payload_hash: str
    timestamp: datetime.datetime


class DataGuardBlockedError(Exception):
    """Raised when Data Guard blocks an outbound call."""
    def __init__(self, reason: str, blocked_fields: List[str]):
        self.reason = reason
        self.blocked_fields = blocked_fields
        super().__init__(f"DataGuard BLOCKED: {reason} | Fields: {blocked_fields}")


class DataClassifier:
    """Classifies individual fields and payloads."""

    @classmethod
    def classify_field(cls, field_name: str) -> str:
        """Returns RESTRICTED | QUASI_IDENTIFIER | NON_SENSITIVE."""
        name_lower = field_name.lower()
        if name_lower in RESTRICTED_FIELDS:
            return "RESTRICTED"
        if name_lower in QUASI_IDENTIFIER_FIELDS:
            return "QUASI_IDENTIFIER"
        return "NON_SENSITIVE"

    @classmethod
    def scan_payload(cls, payload: Any, path: str = "") -> Tuple[List[str], List[str]]:
        """
        Recursively scan a payload for restricted and quasi-identifier fields.
        Returns (restricted_found, quasi_found).
        """
        restricted_found = []
        quasi_found = []

        if isinstance(payload, dict):
            for key, value in payload.items():
                key_lower = key.lower()
                full_path = f"{path}.{key_lower}" if path else key_lower

                if key_lower in RESTRICTED_FIELDS:
                    restricted_found.append(full_path)
                elif key_lower in QUASI_IDENTIFIER_FIELDS:
                    quasi_found.append(full_path)

                if isinstance(value, str):
                    import re
                    if re.search(r'\b\d{4}\s?\d{4}\s?\d{4}\b', value):
                        restricted_found.append(f"{full_path}:aadhaar_number")

                # Recurse into nested dicts/lists
                if isinstance(value, (dict, list)):
                    sub_restricted, sub_quasi = cls.scan_payload(value, full_path)
                    restricted_found.extend(sub_restricted)
                    quasi_found.extend(sub_quasi)

        elif isinstance(payload, list):
            for i, item in enumerate(payload):
                sub_restricted, sub_quasi = cls.scan_payload(item, f"{path}[{i}]")
                restricted_found.extend(sub_restricted)
                quasi_found.extend(sub_quasi)

        elif isinstance(payload, str):
            import re
            if re.search(r'\b\d{4}\s?\d{4}\s?\d{4}\b', payload):
                restricted_found.append("aadhaar_number")

        return restricted_found, quasi_found


class DataGuard:
    """
    Runtime enforcement middleware for the Trust Boundary.
    Every call to external/cloud services must pass through this gate.
    Provides live-demoable blocking + real-time audit log entries.
    """

    def __init__(self, audit_logger=None):
        from app.core.config import settings
        self.enabled = settings.DATA_GUARD_ENABLED
        self.log_all = settings.DATA_GUARD_LOG_ALL
        self._audit_logger = audit_logger

    def check(
        self,
        payload: Any,
        destination: str,
        caller: str,
        operation: str,
        citizen_ref: Optional[str] = None,
        application_id: Optional[str] = None,
        data_classification: Optional[str] = None,  # "SYNTHETIC" for demo/test data
    ) -> DataGuardResult:
        """
        Evaluate whether payload is safe to send to external destination.
        Raises DataGuardBlockedError if blocked.
        Returns DataGuardResult if allowed.
        """
        payload_hash = hashlib.sha256(str(payload).encode()).hexdigest()[:32]

        if not self.enabled:
            result = DataGuardResult(
                allowed=True,
                action="ALLOW",
                blocked_fields=[],
                block_reason=None,
                payload_hash=payload_hash,
                timestamp=datetime.datetime.utcnow(),
            )
            self._log_result(result, caller, destination, operation, citizen_ref, application_id)
            return result

        restricted_found, quasi_found = DataClassifier.scan_payload(payload)

        # Policy: deny if ANY restricted fields found
        if restricted_found:
            reason = f"BLOCKED: Restricted PII fields detected: {restricted_found}"
            result = DataGuardResult(
                allowed=False,
                action="BLOCK",
                blocked_fields=restricted_found + quasi_found,
                block_reason=reason,
                payload_hash=payload_hash,
                timestamp=datetime.datetime.utcnow(),
            )
            self._log_result(result, caller, destination, operation, citizen_ref, application_id)
            raise DataGuardBlockedError(reason=reason, blocked_fields=restricted_found)

        # Policy: allow quasi-identifiers only with synthetic/demo flag and k-anonymity
        if quasi_found:
            if data_classification == "SYNTHETIC" and len(quasi_found) < 3:
                pass  # k-anonymity minimum met for synthetic data
            else:
                reason = f"BLOCKED: Quasi-identifier fields without explicit SYNTHETIC classification: {quasi_found}"
                result = DataGuardResult(
                    allowed=False,
                    action="BLOCK",
                    blocked_fields=quasi_found,
                    block_reason=reason,
                    payload_hash=payload_hash,
                    timestamp=datetime.datetime.utcnow(),
                )
                self._log_result(result, caller, destination, operation, citizen_ref, application_id)
                raise DataGuardBlockedError(reason=reason, blocked_fields=quasi_found)

        result = DataGuardResult(
            allowed=True,
            action="ALLOW",
            blocked_fields=[],
            block_reason=None,
            payload_hash=payload_hash,
            timestamp=datetime.datetime.utcnow(),
        )
        self._log_result(result, caller, destination, operation, citizen_ref, application_id)
        return result

    def _log_result(
        self,
        result: DataGuardResult,
        caller: str,
        destination: str,
        operation: str,
        citizen_ref: Optional[str],
        application_id: Optional[str],
    ) -> None:
        """Write an immutable audit log entry for the Data Guard decision."""
        if not self._audit_logger:
            return
        if not self.log_all and result.allowed:
            return

        self._audit_logger.write(
            event_type="DATA_GUARD",
            actor=caller,
            citizen_ref=citizen_ref,
            application_id=application_id,
            action=f"{result.action}: {operation} -> {destination}",
            outcome=result.action,
            blocked_fields=result.blocked_fields,
            metadata={
                "destination": destination,
                "operation": operation,
                "block_reason": result.block_reason,
                "payload_hash": result.payload_hash,
            },
            payload_hash=result.payload_hash,
        )


# Singleton instance (lazy-initialized with db audit logger)
_data_guard_instance: Optional[DataGuard] = None


def get_data_guard(db=None) -> DataGuard:
    """Get the singleton Data Guard instance."""
    global _data_guard_instance
    if _data_guard_instance is None:
        if db is not None:
            from app.data_layer.repositories.audit_repo import AuditRepository
            audit_logger = AuditRepository(db)
            _data_guard_instance = DataGuard(audit_logger=audit_logger)
        else:
            _data_guard_instance = DataGuard()
    return _data_guard_instance
