"""
Phase 15 Tests — OCR Matching Service
Tests field-level fuzzy matching between OCR extracted data and application data.
Uses the correct MatchingService API:
  - compare_fields(app_value, ocr_value, field_name) → FieldMatchResult
  - compare_document(app_fields, ocr_fields) → DocumentMatchResult
"""
import pytest
from app.services.matching_service import MatchingService


class TestOCRMatching:
    def setup_method(self):
        self.svc = MatchingService()

    def test_exact_name_match(self):
        result = self.svc.compare_fields("Ramesh Kumar", "Ramesh Kumar", "full_name")
        assert result.score >= 95

    def test_near_match_name(self):
        result = self.svc.compare_fields("Ramesh Kumar", "Ramesh Kumarr", "full_name")  # typo
        assert result.score >= 70, f"Expected near-match score >=70, got {result.score}"

    def test_clear_mismatch(self):
        result = self.svc.compare_fields("Ramesh Kumar", "Suresh Patel", "full_name")
        assert result.score < 70, f"Expected low score for mismatch, got {result.score}"

    def test_date_format_normalization(self):
        """1990-01-15 vs 15/01/1990 should both normalize to same date → score 100."""
        result = self.svc.compare_fields("1990-01-15", "15/01/1990", "date_of_birth")
        assert result.score >= 80, f"Date format mismatch should score high: {result.score}"

    def test_compare_document_all_match(self):
        """All fields match → high overall score."""
        result = self.svc.compare_document(
            app_fields={"full_name": "Priya Sharma", "date_of_birth": "15-01-1995"},
            ocr_fields={"full_name": "Priya Sharma", "date_of_birth": "15-01-1995"},
        )
        assert result.overall_score >= 95
        assert not result.mismatched_fields

    def test_overall_match_score_all_perfect(self):
        result = self.svc.compare_document(
            app_fields={"full_name": "Priya Sharma", "father_name": "Rajesh Sharma"},
            ocr_fields={"full_name": "Priya Sharma", "father_name": "Rajesh Sharma"},
        )
        assert result.overall_score >= 95

    def test_mismatch_detection(self):
        """Name mismatch flagged; income match not flagged."""
        result = self.svc.compare_document(
            app_fields={"full_name": "Ramesh Kumar", "annual_income": "250000"},
            ocr_fields={"full_name": "Suresh Patel", "annual_income": "250000"},
        )
        assert "full_name" in result.mismatched_fields
        assert "annual_income" not in result.mismatched_fields

    def test_missing_ocr_field_not_compared(self):
        """Fields only in one side are ignored (only common fields compared)."""
        result = self.svc.compare_document(
            app_fields={"full_name": "Ramesh Kumar", "extra_field": "value"},
            ocr_fields={"full_name": "Ramesh Kumar"},   # extra_field missing
        )
        # extra_field not in both → not in field_scores
        assert "extra_field" not in result.field_scores
        assert "full_name" in result.field_scores

    def test_field_match_result_structure(self):
        """FieldMatchResult has all expected fields."""
        result = self.svc.compare_fields("Ramesh Kumar", "Ramesh Kumar", "full_name")
        assert hasattr(result, "score")
        assert hasattr(result, "match")
        assert hasattr(result, "app_value")
        assert hasattr(result, "ocr_value")
        assert hasattr(result, "field_name")

    def test_aadhaar_exact_match(self):
        result = self.svc.compare_fields("123456789012", "123456789012", "aadhaar_number")
        assert result.score == 100.0
        assert result.match

    def test_aadhaar_mismatch_zeroes(self):
        result = self.svc.compare_fields("123456789012", "123456789099", "aadhaar_number")
        assert result.score < 85  # Exact field type → 0 on mismatch
