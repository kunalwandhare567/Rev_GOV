"""
Matching Service — Field-level data match scoring
Compares OCR-extracted document fields vs application-declared fields.

IMPORTANT: This is a DATA MATCH SCORE — NOT a document authenticity score.
"""
import difflib
import re
import logging
from dataclasses import dataclass
from typing import Optional

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
    field_scores: dict     # {field_name: FieldMatchResult}
    overall_score: float   # Weighted average
    mismatched_fields: list
    matched_fields: list
    data_match_disclaimer: str = (
        "This score compares your declared information with data extracted from your document. "
        "It does not verify document authenticity."
    )


# Field type determines matching algorithm
FIELD_TYPES = {
    "full_name": "name",
    "father_name": "name",
    "mother_name": "name",
    "spouse_name": "name",
    "dob": "date",
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
}


class MatchingService:
    """
    Compares OCR-extracted fields with application-declared fields.
    Uses different algorithms per field type for best accuracy.
    """

    MATCH_THRESHOLD = 85.0  # Score >= this is considered a match

    def compare_fields(self, app_value: str, ocr_value: str,
                       field_name: str) -> FieldMatchResult:
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

    def compare_document(self, app_fields: dict, ocr_fields: dict) -> DocumentMatchResult:
        """
        Compare all overlapping fields between application and document.
        Only compares fields that exist in BOTH.
        """
        field_scores = {}
        mismatched = []
        matched = []

        # Find overlapping fields
        common_fields = set(app_fields.keys()) & set(ocr_fields.keys())

        for field in common_fields:
            app_val = app_fields.get(field)
            ocr_val = ocr_fields.get(field)

            if app_val is None or ocr_val is None:
                continue

            result = self.compare_fields(str(app_val), str(ocr_val), field)
            field_scores[field] = {
                "app_value": result.app_value,
                "ocr_value": result.ocr_value,
                "score": result.score,
                "match": result.match,
            }

            if result.match:
                matched.append(field)
            else:
                mismatched.append(field)

        # Compute weighted overall score
        if field_scores:
            scores = [v["score"] for v in field_scores.values()]
            overall = sum(scores) / len(scores)
        else:
            overall = 0.0

        return DocumentMatchResult(
            field_scores=field_scores,
            overall_score=round(overall, 1),
            mismatched_fields=mismatched,
            matched_fields=matched,
        )

    def _compute_score(self, v1: str, v2: str, field_type: str) -> float:
        v1 = v1.strip().lower()
        v2 = v2.strip().lower()

        if field_type == "name":
            return self._fuzzy_name_match(v1, v2)
        elif field_type == "date":
            return self._date_match(v1, v2)
        elif field_type in ("exact", "number"):
            # Remove spaces and compare
            return 100.0 if v1.replace(" ", "") == v2.replace(" ", "") else 0.0
        elif field_type == "address":
            return self._token_overlap(v1, v2)
        else:
            return self._fuzzy_match(v1, v2)

    def _fuzzy_name_match(self, n1: str, n2: str) -> float:
        """
        Fuzzy name matching — handles transliteration differences.
        e.g. "Wandhare" vs "Wadhare" → 87%
        """
        # Sequence matcher
        ratio = difflib.SequenceMatcher(None, n1, n2).ratio() * 100

        # Token sort ratio (handles word order differences)
        words1 = sorted(n1.split())
        words2 = sorted(n2.split())
        token_ratio = difflib.SequenceMatcher(None, " ".join(words1), " ".join(words2)).ratio() * 100

        return round(max(ratio, token_ratio), 1)

    def _fuzzy_match(self, v1: str, v2: str) -> float:
        return round(difflib.SequenceMatcher(None, v1, v2).ratio() * 100, 1)

    def _date_match(self, d1: str, d2: str) -> float:
        """Normalize dates and compare. Returns 100 or 0."""
        n1 = self._normalize_date_str(d1)
        n2 = self._normalize_date_str(d2)
        if not n1 or not n2:
            return self._fuzzy_match(d1, d2)
        return 100.0 if n1 == n2 else 0.0

    def _normalize_date_str(self, s: str) -> Optional[str]:
        """Extract YYYY-MM-DD from various formats."""
        s = s.strip()
        # Already normalized
        if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
            return s
        # DD/MM/YYYY or DD-MM-YYYY
        m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', s)
        if m:
            return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
        return None

    def _token_overlap(self, a1: str, a2: str) -> float:
        """Token overlap for address matching."""
        tokens1 = set(re.findall(r'\w+', a1))
        tokens2 = set(re.findall(r'\w+', a2))
        if not tokens1 or not tokens2:
            return 0.0
        # Jaccard similarity
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        return round(len(intersection) / len(union) * 100, 1)

    def generate_mismatch_message(self, doc_result: DocumentMatchResult,
                                  language: str = "en") -> str:
        """
        Generate human-readable mismatch explanation in citizen's language.
        Returns chat message for WhatsApp/IVR.
        """
        if not doc_result.mismatched_fields:
            return ""

        messages = {
            "en": self._mismatch_en(doc_result),
            "hi": self._mismatch_hi(doc_result),
            "mr": self._mismatch_mr(doc_result),
        }
        return messages.get(language, messages["en"])

    def _mismatch_en(self, r: DocumentMatchResult) -> str:
        lines = ["⚠️ I found some differences between your application and document:\n"]
        for field in r.mismatched_fields:
            s = r.field_scores[field]
            lines.append(f"📋 *{field.replace('_', ' ').title()}*")
            lines.append(f"   Your application: {s['app_value']}")
            lines.append(f"   Document says: {s['ocr_value']}")
            lines.append(f"   Match: {s['score']}%\n")
        lines.append("How would you like to resolve this?")
        lines.append("1️⃣ Use document value")
        lines.append("2️⃣ Keep my application value")
        lines.append("3️⃣ Enter a new value manually")
        return "\n".join(lines)

    def _mismatch_hi(self, r: DocumentMatchResult) -> str:
        lines = ["⚠️ आपके आवेदन और दस्तावेज़ में कुछ अंतर मिला:\n"]
        for field in r.mismatched_fields:
            s = r.field_scores[field]
            lines.append(f"📋 *{field.replace('_', ' ').title()}*")
            lines.append(f"   आवेदन में: {s['app_value']}")
            lines.append(f"   दस्तावेज़ में: {s['ocr_value']}")
            lines.append(f"   मिलान: {s['score']}%\n")
        lines.append("आप क्या करना चाहते हैं?")
        lines.append("1️⃣ दस्तावेज़ का मान उपयोग करें")
        lines.append("2️⃣ आवेदन का मान रखें")
        lines.append("3️⃣ स्वयं बदलाव करें")
        return "\n".join(lines)

    def _mismatch_mr(self, r: DocumentMatchResult) -> str:
        lines = ["⚠️ तुमच्या अर्जात आणि कागदपत्रात काही फरक आढळला:\n"]
        for field in r.mismatched_fields:
            s = r.field_scores[field]
            lines.append(f"📋 *{field.replace('_', ' ').title()}*")
            lines.append(f"   अर्जातील: {s['app_value']}")
            lines.append(f"   कागदपत्रातील: {s['ocr_value']}")
            lines.append(f"   जुळणी: {s['score']}%\n")
        lines.append("तुम्हाला काय करायचे आहे?")
        lines.append("1️⃣ कागदपत्राचे नाव वापरा")
        lines.append("2️⃣ अर्जाचे नाव ठेवा")
        lines.append("3️⃣ स्वतः बदल करा")
        return "\n".join(lines)
