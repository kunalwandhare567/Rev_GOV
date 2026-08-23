"""
Rules Engine Tests
Verifies field validation, eligibility checks, fee calculation.
"""
import pytest
from app.rules_engine.engine import (
    ServiceSpecLoader, FieldValidator, EligibilityChecker, FeeCalculator, SlotSpec
)


class TestFieldValidator:

    def _slot(self, name, stype, validation, required=True, classification="NON_SENSITIVE"):
        return SlotSpec(
            name=name, type=stype, required=required,
            classification=classification, validation=validation, prompt={}
        )

    def test_valid_aadhaar(self):
        slot = self._slot("aadhaar_number", "string", {"pattern": "^[0-9]{12}$"}, classification="RESTRICTED")
        valid, _ = FieldValidator.validate_slot(slot, "123456789012")
        assert valid is True

    def test_invalid_aadhaar_too_short(self):
        slot = self._slot("aadhaar_number", "string", {"pattern": "^[0-9]{12}$", "error_msg": "Invalid Aadhaar"})
        valid, error = FieldValidator.validate_slot(slot, "12345678")
        assert valid is False
        assert "Invalid Aadhaar" in error

    def test_valid_income_range(self):
        slot = self._slot("annual_income", "number", {"min": 0, "max": 10000000})
        valid, _ = FieldValidator.validate_slot(slot, "150000")
        assert valid is True

    def test_income_exceeds_max(self):
        slot = self._slot("annual_income", "number", {"min": 0, "max": 10000000})
        valid, error = FieldValidator.validate_slot(slot, "15000000")
        assert valid is False
        assert "10000000" in error

    def test_required_field_empty(self):
        slot = self._slot("applicant_name", "string", {"min_length": 3}, required=True)
        valid, error = FieldValidator.validate_slot(slot, "")
        assert valid is False
        assert "required" in error.lower()

    def test_date_format_valid(self):
        slot = self._slot("dob", "date", {"format": "DD-MM-YYYY"})
        valid, _ = FieldValidator.validate_slot(slot, "15-03-1990")
        assert valid is True

    def test_date_format_invalid(self):
        slot = self._slot("dob", "date", {"format": "DD-MM-YYYY"})
        valid, error = FieldValidator.validate_slot(slot, "1990-03-15")
        assert valid is False

    def test_allowed_values_valid(self):
        slot = self._slot("caste_category", "string", {"allowed_values": ["SC", "ST", "OBC"]})
        valid, _ = FieldValidator.validate_slot(slot, "OBC")
        assert valid is True

    def test_allowed_values_invalid(self):
        slot = self._slot("caste_category", "string", {"allowed_values": ["SC", "ST", "OBC"]})
        valid, error = FieldValidator.validate_slot(slot, "GENERAL")
        assert valid is False


class TestFeeCalculator:

    @pytest.fixture
    def income_spec(self):
        return ServiceSpecLoader.get("income_certificate")

    def test_standard_fee_no_waiver(self, income_spec):
        if not income_spec:
            pytest.skip("Service specs not loaded")
        result = FeeCalculator.calculate(income_spec, {"annual_income": 500000})
        assert result.base_fee == 50.0
        assert result.final_fee == 50.0
        assert result.waiver_reason is None

    def test_full_waiver_low_income(self, income_spec):
        if not income_spec:
            pytest.skip("Service specs not loaded")
        result = FeeCalculator.calculate(income_spec, {"annual_income": 15000})
        assert result.discount > 0
        assert result.final_fee == 0.0

    def test_full_waiver_bpl_card(self, income_spec):
        if not income_spec:
            pytest.skip("Service specs not loaded")
        result = FeeCalculator.calculate(income_spec, {"annual_income": 300000, "bpl_card": True})
        assert result.final_fee == 0.0


class TestEligibilityChecker:

    @pytest.fixture
    def domicile_spec(self):
        return ServiceSpecLoader.get("domicile_certificate")

    def test_domicile_passes_15_years(self, domicile_spec):
        if not domicile_spec:
            pytest.skip("Service specs not loaded")
        result = EligibilityChecker.check(domicile_spec, {
            "applicant_dob": "01-01-1990",
            "residence_years": 20,
        })
        assert result.valid is True

    def test_domicile_fails_under_15_years(self, domicile_spec):
        if not domicile_spec:
            pytest.skip("Service specs not loaded")
        result = EligibilityChecker.check(domicile_spec, {
            "applicant_dob": "01-01-1990",
            "residence_years": 10,
        })
        assert result.valid is False
        assert len(result.errors) > 0

    def test_obc_ncl_income_limit(self):
        spec = ServiceSpecLoader.get("obc_ncl_certificate")
        if not spec:
            pytest.skip("Service specs not loaded")
        result = EligibilityChecker.check(spec, {
            "applicant_dob": "01-01-1990",
            "annual_income": 900000,  # Over 8 lakh limit
            "caste_category": "OBC",
        })
        assert result.valid is False
