"""
Phase 7 — ReadinessEngine

Computes a 0-100 application readiness score based on 5 deterministic components.
This score determines whether a citizen can submit their application.

IMPORTANT: This is NOT the same as Document Match Score.
- Document Match Score: how well a document matches declared fields (per-document metric)
- Readiness Score: overall application completeness across all dimensions

Components and weights (as per impl3.md §16):
  1. Field Completeness   — 30 pts  (all required slots filled)
  2. Document Coverage    — 25 pts  (all required documents uploaded)
  3. OCR Validation       — 20 pts  (OCR extracted and verified)
  4. Eligibility          — 15 pts  (rules engine passes)
  5. Cross-field Consistency — 10 pts (income format, DOB valid, mobile format)

Threshold:
  ≥ 90 → READY
  ≥ 75 → MINOR_ISSUES (can submit)
  ≥ 60 → MODERATE_ISSUES (cannot submit yet)
  < 60  → MAJOR_ISSUES (cannot submit)

can_submit = score ≥ 75 AND no blocking_issues
"""
import logging
import re
import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────

@dataclass
class ReadinessComponent:
    """Score for one readiness component."""
    name: str
    weight: int           # Maximum points this component contributes
    score: float          # 0.0 to 1.0 (fraction achieved)
    weighted_score: float # weight * score
    issues: List[str] = field(default_factory=list)  # List of issue descriptions

    @property
    def pct(self) -> float:
        return round(self.score * 100, 1)


@dataclass
class ReadinessResult:
    """Full readiness assessment result."""
    overall_score: float              # 0–100
    status: str                       # READY | MINOR_ISSUES | MODERATE_ISSUES | MAJOR_ISSUES
    can_submit: bool                  # overall_score ≥ 75 and no blocking issues
    components: List[ReadinessComponent]
    blocking_issues: List[str]        # Issues that prevent submission
    warnings: List[str]               # Non-blocking issues
    service_id: str = ""
    computed_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "overall_score": self.overall_score,
            "status": self.status,
            "can_submit": self.can_submit,
            "blocking_issues": self.blocking_issues,
            "warnings": self.warnings,
            "service_id": self.service_id,
            "computed_at": self.computed_at,
            "components": [
                {
                    "name": c.name,
                    "weight": c.weight,
                    "score_pct": c.pct,
                    "weighted_score": round(c.weighted_score, 1),
                    "issues": c.issues,
                }
                for c in self.components
            ],
        }


# ─────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────

class ReadinessEngine:
    """
    Deterministic 5-component readiness scoring engine.
    No LLM involvement. No randomness.
    """

    COMPONENT_WEIGHTS = {
        "Field Completeness":      30,
        "Document Coverage":       25,
        "OCR Validation":          20,
        "Eligibility":             15,
        "Cross-field Consistency": 10,
    }

    STATUS_THRESHOLDS = [
        (90, "READY"),
        (75, "MINOR_ISSUES"),
        (60, "MODERATE_ISSUES"),
        (0,  "MAJOR_ISSUES"),
    ]

    def compute(
        self,
        service_id: str,
        filled_slots: Dict[str, Any],
        required_slots: List[str],
        required_docs: List[str],
        uploaded_docs: List[str],
        ocr_results: Optional[List[Dict]] = None,
        eligibility_result: Optional[Dict] = None,
    ) -> ReadinessResult:
        """
        Compute readiness score.

        Args:
            service_id: e.g., 'income_certificate'
            filled_slots: {field_name: value} — currently filled
            required_slots: list of required field names for this service
            required_docs: list of required document type IDs
            uploaded_docs: list of document type IDs actually uploaded
            ocr_results: list of OCR result dicts (from matching_service)
            eligibility_result: dict from rules engine {eligible, reason, score}

        Returns:
            ReadinessResult with full breakdown
        """
        components = []
        blocking_issues = []
        warnings = []

        # ── Component 1: Field Completeness (30 pts) ──
        fc = self._score_field_completeness(filled_slots, required_slots)
        components.append(fc)
        if fc.score < 1.0:
            missing = [s for s in required_slots if not filled_slots.get(s)]
            blocking_issues.append(
                f"Missing required fields: {', '.join(missing[:5])}"
                + (" and more" if len(missing) > 5 else "")
            )

        # ── Component 2: Document Coverage (25 pts) ──
        dc = self._score_document_coverage(required_docs, uploaded_docs)
        components.append(dc)
        if dc.score < 1.0:
            missing_docs = [d for d in required_docs if d not in uploaded_docs]
            blocking_issues.append(f"Missing documents: {', '.join(missing_docs)}")

        # ── Component 3: OCR Validation (20 pts) ──
        ocr_c = self._score_ocr_validation(ocr_results or [])
        components.append(ocr_c)
        if ocr_c.score < 0.5:
            warnings.append("Document OCR validation shows low confidence. Please re-upload clearer documents.")

        # ── Component 4: Eligibility (15 pts) ──
        elig_c = self._score_eligibility(eligibility_result)
        components.append(elig_c)
        if elig_c.score == 0.0:
            reason = (eligibility_result or {}).get("reason", "Eligibility check failed")
            blocking_issues.append(f"Eligibility check: {reason}")

        # ── Component 5: Cross-field Consistency (10 pts) ──
        cons_c = self._score_consistency(filled_slots)
        components.append(cons_c)
        if cons_c.score < 0.7:
            warnings.extend(cons_c.issues)

        # ── Overall Score ──
        overall = sum(c.weighted_score for c in components)
        overall = round(min(100.0, max(0.0, overall)), 1)

        # Determine status
        status = "MAJOR_ISSUES"
        for threshold, label in self.STATUS_THRESHOLDS:
            if overall >= threshold:
                status = label
                break

        # can_submit: score ≥ 75 AND no blocking issues
        can_submit = overall >= 75.0 and len(blocking_issues) == 0

        return ReadinessResult(
            overall_score=overall,
            status=status,
            can_submit=can_submit,
            components=components,
            blocking_issues=blocking_issues,
            warnings=warnings,
            service_id=service_id,
            computed_at=datetime.datetime.utcnow().isoformat(),
        )

    # ─────────────────────────────────────────────
    # Component Scorers
    # ─────────────────────────────────────────────

    def _score_field_completeness(
        self,
        filled_slots: Dict,
        required_slots: List[str]
    ) -> ReadinessComponent:
        """Score how many required fields are filled."""
        weight = self.COMPONENT_WEIGHTS["Field Completeness"]

        if not required_slots:
            return ReadinessComponent("Field Completeness", weight, 1.0, float(weight))

        filled_required = [s for s in required_slots if filled_slots.get(s) is not None]
        score = len(filled_required) / len(required_slots)

        issues = []
        if score < 1.0:
            missing = [s for s in required_slots if not filled_slots.get(s)]
            issues = [f"Missing: {s.replace('_', ' ')}" for s in missing[:5]]

        return ReadinessComponent(
            name="Field Completeness",
            weight=weight,
            score=score,
            weighted_score=weight * score,
            issues=issues,
        )

    def _score_document_coverage(
        self,
        required_docs: List[str],
        uploaded_docs: List[str]
    ) -> ReadinessComponent:
        """Score how many required documents are uploaded."""
        weight = self.COMPONENT_WEIGHTS["Document Coverage"]

        if not required_docs:
            return ReadinessComponent("Document Coverage", weight, 1.0, float(weight))

        uploaded_set = set(uploaded_docs)
        covered = [d for d in required_docs if d in uploaded_set]
        score = len(covered) / len(required_docs)

        issues = []
        if score < 1.0:
            missing = [d for d in required_docs if d not in uploaded_set]
            issues = [f"Not uploaded: {d.replace('_', ' ')}" for d in missing]

        return ReadinessComponent(
            name="Document Coverage",
            weight=weight,
            score=score,
            weighted_score=weight * score,
            issues=issues,
        )

    def _score_ocr_validation(self, ocr_results: List[Dict]) -> ReadinessComponent:
        """
        Score OCR completion and match quality.
        - All docs have OCR results: +50%
        - Average match score is high: +50%
        """
        weight = self.COMPONENT_WEIGHTS["OCR Validation"]

        if not ocr_results:
            # No docs uploaded yet — this component is N/A, give partial credit
            return ReadinessComponent(
                name="OCR Validation",
                weight=weight,
                score=0.5,
                weighted_score=weight * 0.5,
                issues=["No documents uploaded yet"],
            )

        # Check each document's OCR status
        ocr_done = 0
        total_match = 0.0
        issues = []

        for ocr in ocr_results:
            status = ocr.get("status", "")
            match_score = ocr.get("overall_match_score", 0)
            doc_type = ocr.get("doc_type", "document")

            if status in ("COMPLETED", "VALIDATED", "MISMATCH_RESOLVED"):
                ocr_done += 1
                total_match += match_score
            elif status in ("PENDING", "PROCESSING"):
                issues.append(f"OCR pending for: {doc_type}")
            elif status in ("FAILED", "ERROR"):
                issues.append(f"OCR failed for: {doc_type} — please re-upload")
            elif status == "MISMATCH":
                ocr_done += 1
                total_match += match_score
                issues.append(f"Mismatch in: {doc_type} — please resolve")

        ocr_coverage = ocr_done / len(ocr_results) if ocr_results else 0
        avg_match = (total_match / ocr_done) if ocr_done > 0 else 0

        # Combined score
        score = (0.5 * ocr_coverage) + (0.5 * (avg_match / 100.0))

        return ReadinessComponent(
            name="OCR Validation",
            weight=weight,
            score=score,
            weighted_score=weight * score,
            issues=issues,
        )

    def _score_eligibility(self, eligibility_result: Optional[Dict]) -> ReadinessComponent:
        """Score eligibility check result from rules engine."""
        weight = self.COMPONENT_WEIGHTS["Eligibility"]

        if eligibility_result is None:
            # Not yet checked — give neutral credit
            return ReadinessComponent(
                name="Eligibility",
                weight=weight,
                score=0.7,
                weighted_score=weight * 0.7,
                issues=["Eligibility check not yet run"],
            )

        eligible = eligibility_result.get("eligible", False)
        if eligible:
            return ReadinessComponent(
                name="Eligibility",
                weight=weight,
                score=1.0,
                weighted_score=float(weight),
            )
        else:
            reason = eligibility_result.get("reason", "Not eligible")
            return ReadinessComponent(
                name="Eligibility",
                weight=weight,
                score=0.0,
                weighted_score=0.0,
                issues=[reason],
            )

    def _score_consistency(self, filled_slots: Dict) -> ReadinessComponent:
        """
        Score cross-field consistency:
        - Mobile number format (10 digits)
        - DOB is a valid past date
        - Annual income is a positive number
        - Income ≤ family income (family_income >= individual_income)
        - Aadhaar is 12 digits
        """
        weight = self.COMPONENT_WEIGHTS["Cross-field Consistency"]
        issues = []
        checks = 0
        passed = 0

        # Mobile format
        if mobile := filled_slots.get("mobile_number"):
            checks += 1
            if re.match(r"^[6-9]\d{9}$", str(mobile).replace(" ", "").replace("-", "")):
                passed += 1
            else:
                issues.append("Mobile number must be 10 digits starting with 6-9")

        # DOB validity
        if dob := filled_slots.get("applicant_dob"):
            checks += 1
            try:
                # Support DD-MM-YYYY and YYYY-MM-DD
                dob_str = str(dob)
                for fmt in ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]:
                    try:
                        dob_date = datetime.datetime.strptime(dob_str, fmt).date()
                        if dob_date < datetime.date.today():
                            passed += 1
                        else:
                            issues.append("Date of birth cannot be in the future")
                        break
                    except ValueError:
                        continue
                else:
                    issues.append("Date of birth format should be DD-MM-YYYY")
            except Exception:
                issues.append("Invalid date of birth")

        # Annual income positive
        if income := filled_slots.get("annual_income"):
            checks += 1
            try:
                income_val = float(str(income).replace(",", ""))
                if income_val > 0:
                    passed += 1
                else:
                    issues.append("Annual income must be greater than 0")
            except (ValueError, TypeError):
                issues.append("Annual income must be a number")

        # Family income >= individual income
        if annual_income := filled_slots.get("annual_income"):
            if family_income := filled_slots.get("annual_family_income"):
                checks += 1
                try:
                    ind = float(str(annual_income).replace(",", ""))
                    fam = float(str(family_income).replace(",", ""))
                    if fam >= ind:
                        passed += 1
                    else:
                        issues.append("Annual family income cannot be less than individual income")
                except Exception:
                    pass  # Already caught above

        # Aadhaar format
        if aadhaar := filled_slots.get("aadhaar_number"):
            checks += 1
            clean = str(aadhaar).replace(" ", "").replace("-", "")
            if re.match(r"^\d{12}$", clean):
                passed += 1
            else:
                issues.append("Aadhaar number must be exactly 12 digits")

        if checks == 0:
            return ReadinessComponent(
                name="Cross-field Consistency",
                weight=weight,
                score=0.8,
                weighted_score=weight * 0.8,
            )

        score = passed / checks

        return ReadinessComponent(
            name="Cross-field Consistency",
            weight=weight,
            score=score,
            weighted_score=weight * score,
            issues=issues,
        )
