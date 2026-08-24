"""
Matching Service — Field-level data match scoring
Compares OCR-extracted document fields vs application-declared fields.

IMPORTANT: This is a DATA MATCH SCORE — NOT a document authenticity score.
"""
import difflib
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


@dataclass
class FieldMatchResult:
    field_name: str
    app_value: str
    ocr_value: str
    score: float           # 0-100
    match: bool            # True if score >= threshold
    threshold: float = 85.0


@dataclass
class DocumentMatchResult:
    field_scores: dict          # {field_name: FieldMatchResult-dict}
    overall_score: float        # Weighted average
    mismatched_fields: list
    matched_fields: list
    fields_only_in_app: list    # Declared in chat, NOT found in document at all
    fields_only_in_doc: list    # In document OCR, NOT declared in chat
    data_match_disclaimer: str = (
        "This score compares your declared information with data extracted from your document. "
        "It does not verify document authenticity."
    )


@dataclass
class ValidationReport:
    """
    Full structured validation report.
    Returned by compare_document() and used by UI and orchestrator.
    """
    overall_score: float
    matched_fields: List[str]
    mismatched_fields: List[str]
    fields_only_in_app: List[str]     # Declared but not in OCR
    fields_only_in_doc: List[str]     # In OCR but not declared
    field_scores: Dict[str, dict]     # Per-field comparison details
    verdict: str                      # "VERIFIED" | "MISMATCH" | "INCOMPLETE" | "EMPTY"
    summary: str                      # Human-readable one-line summary
    can_auto_resolve: List[str]       # Fields where score >= 92 (likely just a variant)


# Field type determines matching algorithm
FIELD_TYPES = {
    "full_name": "name",
    "applicant_name": "name",
    "father_name": "name",
    "mother_name": "name",
    "spouse_name": "name",
    "dob": "date",
    "applicant_dob": "date",
    "date_of_birth": "date",
    "gender": "exact",
    "aadhaar_number": "number",
    "pan_number": "number",
    "voter_id": "number",
    "dl_number": "number",
    "passport_number": "number",
    "address": "address",
    "annual_income": "number",
    "amount": "number",
    "transaction_id": "exact",
    "caste_category": "exact",
}

# Weights for overall score — higher = more important field
FIELD_WEIGHTS = {
    "applicant_name": 3.0,
    "dob": 3.0,
    "aadhaar_number": 4.0,
    "pan_number": 4.0,
    "annual_income": 2.0,
    "address": 1.5,
    "gender": 1.0,
    "caste_category": 2.0,
    "father_name": 1.5,
    "mother_name": 1.5,
}

# Alias -> Single Canonical Field Key Mapping
CANONICAL_FIELD_MAP = {
    "applicant_name": "applicant_name",
    "full_name": "applicant_name",
    "name": "applicant_name",
    "full_name_en": "applicant_name",
    "applicant_name_en": "applicant_name",

    "dob": "dob",
    "applicant_dob": "dob",
    "date_of_birth": "dob",
    "birth_date": "dob",

    "aadhaar_number": "aadhaar_number",
    "aadhaar": "aadhaar_number",
    "uid": "aadhaar_number",
    "aadhaar_no": "aadhaar_number",

    "annual_income": "annual_income",
    "income": "annual_income",
    "annual_income_rs": "annual_income",

    "address": "address",
    "residential_address": "address",
    "full_address": "address",

    "caste_category": "caste_category",
    "caste": "caste_category",
    "caste_name": "caste_category",

    "gender": "gender",
    "sex": "gender",
}

# Fields that are only meaningful to compare across certain document types
# Maps doc_type → list of fields to prioritize in that comparison
DOC_TYPE_PRIORITY_FIELDS = {
    "AADHAAR_CARD": ["applicant_name", "dob", "aadhaar_number", "address", "gender"],
    "PAN_CARD": ["applicant_name", "dob", "pan_number", "father_name"],
    "INCOME_PROOF": ["applicant_name", "annual_income"],
    "CASTE_CERTIFICATE": ["applicant_name", "caste_category"],
    "VOTER_ID": ["applicant_name", "dob", "gender", "address", "voter_id"],
    "DRIVING_LICENSE": ["applicant_name", "dob", "dl_number", "address"],
    "PASSPORT": ["applicant_name", "dob", "gender", "passport_number"],
}


def normalize_field_dict(d: dict) -> dict:
    """
    Map all field aliases to a SINGLE canonical field key.
    Eliminates duplicate keys (e.g. dob vs applicant_dob vs date_of_birth)
    so each piece of data is compared exactly once.
    """
    if not isinstance(d, dict):
        return {}
    canonical = {}
    for k, v in d.items():
        if v is None or not str(v).strip() or k == "doc_type":
            continue
        c_key = CANONICAL_FIELD_MAP.get(k, k)
        if c_key not in canonical:
            canonical[c_key] = str(v).strip()
    return canonical


class MatchingService:
    """
    Compares OCR-extracted fields with application-declared fields.
    Uses different algorithms per field type for best accuracy.
    Returns a full ValidationReport with matched, mismatched, and missing fields.
    """

    MATCH_THRESHOLD = 85.0       # Score >= this → matched
    AUTO_RESOLVE_THRESHOLD = 92.0  # Score >= this → likely a variant, can auto-suggest

    def compare_fields(
        self, app_value: str, ocr_value: str, field_name: str
    ) -> FieldMatchResult:
        """Compare a single field and return match score."""
        if not app_value or not ocr_value:
            score = 0.0 if (app_value or ocr_value) else 100.0
            return FieldMatchResult(
                field_name=field_name,
                app_value=str(app_value or ""),
                ocr_value=str(ocr_value or ""),
                score=score,
                match=score >= self.MATCH_THRESHOLD,
            )

        field_type = FIELD_TYPES.get(field_name, "text")
        score = self._compute_score(str(app_value), str(ocr_value), field_type)

        return FieldMatchResult(
            field_name=field_name,
            app_value=str(app_value),
            ocr_value=str(ocr_value),
            score=round(score, 1),
            match=score >= self.MATCH_THRESHOLD,
        )

    def compare_document(
        self,
        app_fields: dict,
        ocr_fields: dict,
        doc_type: str = None,
    ) -> DocumentMatchResult:
        """
        Compare all overlapping fields between application and document.

        Returns DocumentMatchResult with:
          - field_scores: per-field comparison
          - matched_fields: fields that match
          - mismatched_fields: fields that don't match
          - fields_only_in_app: declared but not found in OCR
          - fields_only_in_doc: in OCR but not declared
        """
        norm_app = normalize_field_dict(app_fields or {})
        norm_ocr = normalize_field_dict(ocr_fields or {})

        # Remove null/empty values and doc_type metadata key
        norm_app = {k: v for k, v in norm_app.items() if v and str(v).strip() and k != "doc_type"}
        norm_ocr = {k: v for k, v in norm_ocr.items() if v and str(v).strip() and k != "doc_type"}

        # Determine priority fields for this doc type
        priority_fields = set(DOC_TYPE_PRIORITY_FIELDS.get(doc_type or "UNKNOWN", []))

        # Fields present in both
        app_keys = set(norm_app.keys())
        ocr_keys = set(norm_ocr.keys())
        common_fields = app_keys & ocr_keys

        # Fields only in one side
        fields_only_in_app = sorted(
            f for f in (app_keys - ocr_keys)
            if f in FIELD_TYPES  # Only warn about known/important fields
        )
        fields_only_in_doc = sorted(ocr_keys - app_keys)

        field_scores = {}
        mismatched = []
        matched = []
        can_auto_resolve = []

        for f in common_fields:
            app_val = norm_app.get(f)
            ocr_val = norm_ocr.get(f)

            if app_val is None or ocr_val is None:
                continue

            result = self.compare_fields(str(app_val), str(ocr_val), f)
            field_scores[f] = {
                "app_value": result.app_value,
                "ocr_value": result.ocr_value,
                "score": result.score,
                "match": result.match,
                "field_type": FIELD_TYPES.get(f, "text"),
                "weight": FIELD_WEIGHTS.get(f, 1.0),
                "is_priority": f in priority_fields,
            }

            if result.match:
                matched.append(f)
                if result.score >= self.AUTO_RESOLVE_THRESHOLD and result.score < 100.0:
                    # Very high score but not exact — likely a variant spelling
                    can_auto_resolve.append(f)
            else:
                mismatched.append(f)

        # Compute weighted overall score
        if field_scores:
            total_weight = sum(FIELD_WEIGHTS.get(f, 1.0) for f in field_scores)
            weighted_sum = sum(
                v["score"] * FIELD_WEIGHTS.get(f, 1.0)
                for f, v in field_scores.items()
            )
            overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        else:
            overall = 0.0

        return DocumentMatchResult(
            field_scores=field_scores,
            overall_score=round(overall, 1),
            mismatched_fields=mismatched,
            matched_fields=matched,
            fields_only_in_app=fields_only_in_app,
            fields_only_in_doc=fields_only_in_doc,
        )

    def build_validation_report(
        self,
        match_result: DocumentMatchResult,
    ) -> ValidationReport:
        """
        Build a full ValidationReport from a DocumentMatchResult.
        Used by conversation routes and admin dashboard.
        """
        n_match = len(match_result.matched_fields)
        n_mismatch = len(match_result.mismatched_fields)
        n_missing = len(match_result.fields_only_in_app)
        total_compared = n_match + n_mismatch

        if total_compared == 0:
            verdict = "EMPTY"
            summary = "No comparable fields found between your application and document."
        elif n_mismatch == 0 and n_missing == 0:
            verdict = "VERIFIED"
            summary = f"All {n_match} fields verified — document matches your application perfectly."
        elif n_mismatch == 0 and n_missing > 0:
            verdict = "INCOMPLETE"
            summary = (
                f"{n_match} field(s) verified. "
                f"{n_missing} declared field(s) were not found in this document."
            )
        else:
            verdict = "MISMATCH"
            summary = (
                f"{n_match} field(s) matched, {n_mismatch} field(s) differ "
                f"(Overall: {match_result.overall_score:.1f}%). "
                f"Please review and resolve."
            )

        can_auto_resolve = [
            f for f, v in match_result.field_scores.items()
            if not v["match"] and v["score"] >= self.AUTO_RESOLVE_THRESHOLD
        ]

        return ValidationReport(
            overall_score=match_result.overall_score,
            matched_fields=match_result.matched_fields,
            mismatched_fields=match_result.mismatched_fields,
            fields_only_in_app=match_result.fields_only_in_app,
            fields_only_in_doc=match_result.fields_only_in_doc,
            field_scores=match_result.field_scores,
            verdict=verdict,
            summary=summary,
            can_auto_resolve=can_auto_resolve,
        )

    def generate_mismatch_message(
        self,
        doc_result: DocumentMatchResult,
        language: str = "en",
        use_gemini: bool = True,
    ) -> str:
        """
        Generate human-readable mismatch explanation in citizen's language.
        Tries GeminiDialogueService first; falls back to structured template.
        Returns chat message for WhatsApp/IVR/Web.
        """
        has_mismatches = bool(doc_result.mismatched_fields)
        has_missing = bool(doc_result.fields_only_in_app)

        if not has_mismatches and not has_missing:
            return self._all_match_message(doc_result, language)

        if use_gemini:
            try:
                from app.services.gemini_dialogue import gemini_dialogue
                msg = gemini_dialogue.format_mismatch(
                    matched_fields=doc_result.matched_fields,
                    mismatched_fields=doc_result.mismatched_fields,
                    field_scores=doc_result.field_scores,
                    fields_not_in_doc=doc_result.fields_only_in_app,
                    overall_score=doc_result.overall_score,
                    language=language,
                )
                if msg:
                    return msg
            except Exception as e:
                logger.warning(f"GeminiDialogue format_mismatch failed: {e}")

        # Structured fallback
        from app.services.gemini_dialogue import GeminiDialogueService
        svc = GeminiDialogueService()
        return svc._fallback_mismatch_message(
            matched_fields=doc_result.matched_fields,
            mismatched_fields=doc_result.mismatched_fields,
            field_scores=doc_result.field_scores,
            fields_not_in_doc=doc_result.fields_only_in_app,
            overall_score=doc_result.overall_score,
            language=language,
        )

    def _all_match_message(self, r: DocumentMatchResult, language: str) -> str:
        messages = {
            "en": (
                f"✅ All fields verified successfully!\n"
                f"Overall match score: {r.overall_score:.1f}%\n"
                f"Your application details match your document perfectly."
            ),
            "hi": (
                f"✅ सभी विवरण सफलतापूर्वक सत्यापित!\n"
                f"कुल मिलान स्कोर: {r.overall_score:.1f}%\n"
                f"आपके आवेदन की जानकारी दस्तावेज़ से पूरी तरह मेल खाती है।"
            ),
            "mr": (
                f"✅ सर्व तपशील यशस्वीरित्या सत्यापित!\n"
                f"एकूण जुळणी: {r.overall_score:.1f}%\n"
                f"तुमच्या अर्जाचे तपशील कागदपत्राशी पूर्णपणे जुळतात."
            ),
        }
        return messages.get(language, messages["en"])

    # ── Scoring algorithms ──────────────────────────────────────────────────

    def _compute_score(self, v1: str, v2: str, field_type: str) -> float:
        v1 = v1.strip().lower()
        v2 = v2.strip().lower()

        if field_type == "name":
            return self._fuzzy_name_match(v1, v2)
        elif field_type == "date":
            return self._date_match(v1, v2)
        elif field_type in ("exact", "number"):
            return 100.0 if v1.replace(" ", "") == v2.replace(" ", "") else 0.0
        elif field_type == "address":
            return self._token_overlap(v1, v2)
        else:
            return self._fuzzy_match(v1, v2)

    def _fuzzy_name_match(self, n1: str, n2: str) -> float:
        """
        Fuzzy name matching — handles transliteration differences.
        e.g. "Wandhare" vs "Wadhare" → 87%
        Uses both sequence ratio and token-sorted ratio to handle name order.
        """
        ratio = difflib.SequenceMatcher(None, n1, n2).ratio() * 100
        words1 = sorted(n1.split())
        words2 = sorted(n2.split())
        token_ratio = difflib.SequenceMatcher(
            None, " ".join(words1), " ".join(words2)
        ).ratio() * 100
        return round(max(ratio, token_ratio), 1)

    def _fuzzy_match(self, v1: str, v2: str) -> float:
        return round(difflib.SequenceMatcher(None, v1, v2).ratio() * 100, 1)

    def _date_match(self, d1: str, d2: str) -> float:
        """Normalize dates and compare. Returns 100 or fuzzy score."""
        n1 = self._normalize_date_str(d1)
        n2 = self._normalize_date_str(d2)
        if not n1 or not n2:
            return self._fuzzy_match(d1, d2)
        return 100.0 if n1 == n2 else 0.0

    def _normalize_date_str(self, s: str) -> Optional[str]:
        """Extract YYYY-MM-DD from various formats."""
        s = s.strip()
        if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
            return s
        m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', s)
        if m:
            return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
        # DD-MM-YY
        m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2})$', s)
        if m:
            y = int(m.group(3))
            year = f"20{m.group(3)}" if y < 50 else f"19{m.group(3)}"
            return f"{year}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
        return None

    def _token_overlap(self, a1: str, a2: str) -> float:
        """Token overlap (Jaccard) for address matching."""
        tokens1 = set(re.findall(r'\w+', a1))
        tokens2 = set(re.findall(r'\w+', a2))
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        return round(len(intersection) / len(union) * 100, 1)
