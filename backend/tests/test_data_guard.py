"""
Backend Test Suite: Data Guard Adversarial Tests
Verifies that PII is blocked and safe payloads are allowed.
"""
import pytest
from app.data_guard.guard import DataGuard, DataClassifier, DataGuardBlockedError


@pytest.fixture
def guard():
    return DataGuard(audit_logger=None)


class TestDataClassifier:

    def test_restricted_fields_detected(self):
        payload = {"applicant_name": "Ramesh Kumar", "service": "income_certificate"}
        restricted, quasi = DataClassifier.scan_payload(payload)
        assert "applicant_name" in restricted

    def test_aadhaar_detected_as_restricted(self):
        payload = {"aadhaar_number": "123456789012", "amount": 50}
        restricted, quasi = DataClassifier.scan_payload(payload)
        assert "aadhaar_number" in restricted
        assert len(quasi) == 0  # amount is non-sensitive

    def test_nested_restricted_detected(self):
        payload = {
            "message": "process this",
            "data": {"applicant_name": "Ramesh", "dob": "1990-01-01"}
        }
        restricted, quasi = DataClassifier.scan_payload(payload)
        assert len(restricted) > 0

    def test_quasi_identifier_detected(self):
        payload = {"district": "Pune", "annual_income": 150000}
        restricted, quasi = DataClassifier.scan_payload(payload)
        assert len(restricted) == 0
        assert len(quasi) > 0

    def test_safe_payload_clean(self):
        payload = {"message": "translate 'income certificate' to Tamil", "service": "income_certificate"}
        restricted, quasi = DataClassifier.scan_payload(payload)
        assert len(restricted) == 0
        assert len(quasi) == 0


class TestDataGuard:

    def test_blocks_pii_payload(self, guard):
        with pytest.raises(DataGuardBlockedError) as exc_info:
            guard.check(
                payload={"message": "translate this", "applicant_name": "Ramesh Kumar"},
                destination="cloud_llm",
                caller="test",
                operation="translate",
            )
        assert "applicant_name" in exc_info.value.blocked_fields

    def test_allows_safe_payload(self, guard):
        result = guard.check(
            payload={"message": "translate 'income certificate' to Tamil"},
            destination="cloud_llm",
            caller="test",
            operation="translate",
        )
        assert result.allowed is True
        assert result.action == "ALLOW"

    def test_blocks_aadhaar_in_payload(self, guard):
        with pytest.raises(DataGuardBlockedError):
            guard.check(
                payload={"aadhaar_number": "123456789012", "query": "lookup"},
                destination="cloud_api",
                caller="test",
                operation="lookup",
            )

    def test_allows_quasi_with_synthetic_flag(self, guard):
        """Quasi-identifiers allowed when explicitly marked SYNTHETIC with k<3."""
        result = guard.check(
            payload={"district": "Pune"},
            destination="cloud_llm",
            caller="test",
            operation="analytics",
            data_classification="SYNTHETIC",
        )
        assert result.allowed is True

    def test_blocks_quasi_without_synthetic_flag(self, guard):
        """Quasi-identifiers blocked without SYNTHETIC classification."""
        with pytest.raises(DataGuardBlockedError):
            guard.check(
                payload={"district": "Pune", "annual_income": 150000},
                destination="cloud_llm",
                caller="test",
                operation="analytics",
            )

    def test_disabled_guard_allows_everything(self):
        """When DATA_GUARD_ENABLED=False, all calls pass through."""
        guard = DataGuard()
        guard.enabled = False
        result = guard.check(
            payload={"applicant_name": "Ramesh Kumar", "aadhaar_number": "123456789012"},
            destination="cloud_llm",
            caller="test",
            operation="test",
        )
        assert result.allowed is True
