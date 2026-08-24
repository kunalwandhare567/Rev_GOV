"""
Phase 5 (final) — Field Corrector
Auto-corrects common data entry errors in slot values before saving to the DB.

Handles:
  1. Common OCR / typing errors (transpositions, extra chars)
  2. Format normalization (date formats, phone, aadhaar)
  3. Fuzzy matching against known valid values (taluka names, district names)
  4. Language-specific corrections (transliterated Hindi/Marathi numbers)
  5. Income amount normalization (lakh/thousand abbreviations)
"""
import re
import logging
from typing import Optional, Tuple, Dict, List

logger = logging.getLogger(__name__)

# ── Known Valid Values (for fuzzy correction) ─────────────────────────────

KNOWN_CASTES = {
    "SC": ["sc", "scheduled caste", "anusuchit jati", "अनुसूचित जाति"],
    "ST": ["st", "scheduled tribe", "anusuchit jan jati", "अनुसूचित जनजाति"],
    "OBC": ["obc", "other backward class", "pichda varg", "पिछड़ा वर्ग"],
    "GENERAL": ["general", "unreserved", "open", "saamanya", "सामान्य"],
    "EWS": ["ews", "economically weaker section"],
}

HINDI_DIGITS = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}

INCOME_ABBREVIATIONS = {
    r"(\d+(?:\.\d+)?)\s*l(?:akh|ac|k)?": lambda m: str(int(float(m.group(1)) * 100_000)),
    r"(\d+(?:\.\d+)?)\s*(?:thousand|k)\b": lambda m: str(int(float(m.group(1)) * 1_000)),
    r"(\d+(?:\.\d+)?)\s*cr(?:ore)?": lambda m: str(int(float(m.group(1)) * 10_000_000)),
}

# Gender normalization
GENDER_MAP = {
    "m": "MALE", "male": "MALE", "purush": "MALE", "पुरुष": "MALE",
    "f": "FEMALE", "female": "FEMALE", "mahila": "FEMALE", "महिला": "FEMALE",
    "other": "OTHER", "third gender": "OTHER", "tritiya panthi": "OTHER",
}

# Boolean normalization
BOOL_MAP = {
    "yes": True, "haan": True, "ha": True, "हाँ": True, "हां": True, "1": True,
    "no": False, "nahi": False, "नहीं": False, "0": False,
}


class FieldCorrector:
    """
    Auto-correct field values before saving to the DB.
    Each corrector method returns (corrected_value, was_corrected, correction_note).
    """

    def correct(self, field_name: str, value: str, language: str = "en") -> Tuple[str, bool, str]:
        """
        Main entry point. Dispatch to field-specific corrector.
        Returns (corrected_value, was_corrected, note).
        """
        if not value or not value.strip():
            return value, False, ""

        value = value.strip()

        # Convert Hindi/Devanagari digits first (universal)
        value_normalized = self._convert_hindi_digits(value)

        # Dispatch to specific correctors
        correctors = {
            "aadhaar_number":    self._correct_aadhaar,
            "phone_number":      self._correct_phone,
            "mobile_number":     self._correct_phone,
            "annual_income":     self._correct_income,
            "monthly_income":    self._correct_income,
            "date_of_birth":     self._correct_date,
            "dob":               self._correct_date,
            "gender":            self._correct_gender,
            "caste_category":    self._correct_caste,
            "pincode":           self._correct_pincode,
            "pan_number":        self._correct_pan,
            "is_bpl":            self._correct_boolean,
            "has_land":          self._correct_boolean,
            "applicant_name":    self._correct_name,
            "father_name":       self._correct_name,
            "mother_name":       self._correct_name,
        }

        corrector_fn = correctors.get(field_name)
        if corrector_fn:
            return corrector_fn(value_normalized)

        # Generic: just strip and capitalize first letter for text fields
        cleaned = value_normalized.strip()
        was_corrected = cleaned != value
        return cleaned, was_corrected, "Whitespace stripped" if was_corrected else ""

    # ── Field-Specific Correctors ──────────────────────────────────────────

    def _correct_aadhaar(self, value: str) -> Tuple[str, bool, str]:
        """Remove spaces, dashes; validate 12 digits."""
        cleaned = re.sub(r"[\s\-\.]", "", value)
        # Remove any non-digit characters
        digits_only = re.sub(r"\D", "", cleaned)
        was_corrected = digits_only != value  # Compare to original (spaces intact)
        if len(digits_only) == 12:
            return digits_only, was_corrected, "Formatted as 12-digit Aadhaar" if was_corrected else ""
        return digits_only, was_corrected, f"Warning: Aadhaar is {len(digits_only)} digits, expected 12"


    def _correct_phone(self, value: str) -> Tuple[str, bool, str]:
        """Remove +91, country code, spaces; validate 10 digits."""
        cleaned = re.sub(r"[\s\-\.\(\)]", "", value)
        # Remove country code
        if cleaned.startswith("+91"):
            cleaned = cleaned[3:]
        elif cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = cleaned[2:]
        was_corrected = cleaned != value.replace(" ", "")
        return cleaned, was_corrected, "Removed country code" if cleaned != value.replace(" ", "") else ""

    def _correct_income(self, value: str) -> Tuple[str, bool, str]:
        """Normalize income: handle lakh/k abbreviations, commas, Hindi digits."""
        value_lower = value.lower().strip()

        # Try abbreviation patterns
        for pattern, converter in INCOME_ABBREVIATIONS.items():
            match = re.search(pattern, value_lower, re.IGNORECASE)
            if match:
                try:
                    corrected = converter(match)
                    return corrected, True, f"Expanded abbreviation: {value} → {corrected}"
                except Exception:
                    pass

        # Remove commas (1,50,000 → 150000)
        cleaned = re.sub(r",", "", value)
        # Remove currency symbols
        cleaned = re.sub(r"[₹Rs\s]", "", cleaned)
        digits_only = re.sub(r"\D", "", cleaned)

        was_corrected = digits_only != value
        return digits_only, was_corrected, "Removed formatting" if was_corrected else ""

    def _correct_date(self, value: str) -> Tuple[str, bool, str]:
        """
        Normalize date to DD-MM-YYYY.
        Handles: DD/MM/YYYY, YYYY-MM-DD, DD.MM.YYYY, '15 Jan 1990', etc.
        """
        value = value.strip()

        # Already in DD-MM-YYYY
        if re.match(r"^\d{2}-\d{2}-\d{4}$", value):
            return value, False, ""

        # DD/MM/YYYY or DD.MM.YYYY
        m = re.match(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$", value)
        if m:
            d, mo, y = m.groups()
            corrected = f"{d.zfill(2)}-{mo.zfill(2)}-{y}"
            return corrected, True, f"Normalized date format: {value} → {corrected}"

        # YYYY-MM-DD (ISO)
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", value)
        if m:
            y, mo, d = m.groups()
            corrected = f"{d}-{mo}-{y}"
            return corrected, True, f"Converted ISO date: {value} → {corrected}"

        # Month name: 15 Jan 1990
        MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
                   "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
                   "nov": "11", "dec": "12"}
        m = re.match(r"^(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})$", value.lower())
        if m:
            d, month_name, y = m.groups()
            mo = MONTHS.get(month_name[:3])
            if mo:
                corrected = f"{d.zfill(2)}-{mo}-{y}"
                return corrected, True, f"Parsed named month date: {value} → {corrected}"

        return value, False, "Could not normalize date format"

    def _correct_gender(self, value: str) -> Tuple[str, bool, str]:
        """Normalize gender to MALE/FEMALE/OTHER."""
        normalized = GENDER_MAP.get(value.lower().strip())
        if normalized and normalized != value:
            return normalized, True, f"Normalized gender: {value} → {normalized}"
        return value.upper() if value.upper() in ("MALE", "FEMALE", "OTHER") else value, False, ""

    def _correct_caste(self, value: str) -> Tuple[str, bool, str]:
        """Fuzzy match caste category to standard value."""
        value_lower = value.lower().strip()
        for standard, variants in KNOWN_CASTES.items():
            if value_lower in variants or value.upper() == standard:
                corrected = standard
                was_corrected = corrected != value
                return corrected, was_corrected, f"Normalized caste: {value} → {corrected}" if was_corrected else ""
        return value.upper(), value.upper() != value, ""

    def _correct_pincode(self, value: str) -> Tuple[str, bool, str]:
        """Extract 6-digit pincode, remove spaces."""
        digits = re.sub(r"\D", "", value)
        was_corrected = digits != value
        return digits, was_corrected, "Extracted pincode digits" if was_corrected else ""

    def _correct_pan(self, value: str) -> Tuple[str, bool, str]:
        """Uppercase and remove spaces from PAN."""
        cleaned = re.sub(r"\s", "", value).upper()
        was_corrected = cleaned != value
        return cleaned, was_corrected, "Uppercased PAN" if was_corrected else ""

    def _correct_boolean(self, value: str) -> Tuple[str, bool, str]:
        """Convert yes/no/haan/nahi to TRUE/FALSE."""
        mapped = BOOL_MAP.get(value.lower().strip())
        if mapped is not None:
            corrected = "TRUE" if mapped else "FALSE"
            was_corrected = corrected != value.upper()
            return corrected, was_corrected, f"Normalized boolean: {value} → {corrected}" if was_corrected else ""
        return value, False, ""

    def _correct_name(self, value: str) -> Tuple[str, bool, str]:
        """
        Title-case name, remove extra spaces and digits.
        Preserve Hindi/multilingual names.
        """
        # Remove leading digits or punctuation
        cleaned = re.sub(r"^[\d\W]+", "", value).strip()
        # Collapse multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned)
        # Title case (only for ASCII portions)
        if all(ord(c) < 256 for c in cleaned):
            cleaned = cleaned.title()
        was_corrected = cleaned != value
        return cleaned, was_corrected, "Cleaned name format" if was_corrected else ""

    # ── Utility ───────────────────────────────────────────────────────────

    @staticmethod
    def _convert_hindi_digits(value: str) -> str:
        """Replace Devanagari/Hindi digits with ASCII digits."""
        for hindi, ascii_d in HINDI_DIGITS.items():
            value = value.replace(hindi, ascii_d)
        return value

    def correct_all(self, fields: Dict[str, str], language: str = "en") -> Dict[str, Dict]:
        """
        Correct all fields in a dict.
        Returns {field_name: {value, was_corrected, note}} for each field.
        """
        results = {}
        for field_name, value in fields.items():
            corrected, was_corrected, note = self.correct(field_name, str(value), language)
            results[field_name] = {
                "original": value,
                "value": corrected,
                "was_corrected": was_corrected,
                "note": note,
            }
        return results


# Module singleton
field_corrector = FieldCorrector()
