"""
Phase 5 — NLU Intent Classifier
Classifies user utterance into structured intents using:
  1. Ollama local LLM (if available)
  2. Rule-based keyword matcher (always available fallback)

Extends the existing local_llm.py with richer classification and slot extraction.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Extended Intent Catalogue ─────────────────────────────────────────────

INTENTS = {
    "APPLY_CERTIFICATE": {
        "keywords": ["apply", "certificate", "chahiye", "praman", "aay", "jati", "niwas",
                     "income certificate", "caste certificate", "domicile", "obc", "ncl",
                     "आय प्रमाण", "जाति प्रमाण", "निवास प्रमाण", "अर्ज"],
        "weight": 2,
    },
    "CHECK_STATUS": {
        "keywords": ["status", "check", "track", "kahan hai", "kya hua", "update",
                     "application number", "kitne din", "how long", "कहाँ है", "स्थिति"],
        "weight": 2,
    },
    "PAY_FEE": {
        "keywords": ["pay", "payment", "fee", "paisa", "rupee", "upi", "₹", "challan",
                     "शुल्क", "भुगतान", "पैसे", "फीस"],
        "weight": 2,
    },
    "UPLOAD_DOCUMENT": {
        "keywords": ["upload", "document", "aadhaar", "photo", "id", "proof", "send doc",
                     "dakhil", "कागज़", "दस्तावेज़", "अपलोड"],
        "weight": 2,
    },
    "GIVE_FIELD_VALUE": {
        "keywords": [],   # Detected by slot context, not keywords
        "weight": 1,
    },
    "CONFIRM_YES": {
        "keywords": ["yes", "ok", "haan", "ha", "correct", "theek hai", "sahi", "confirm",
                     "हाँ", "ठीक", "हां", "ओके", "सही"],
        "weight": 3,
    },
    "CONFIRM_NO": {
        "keywords": ["no", "nahi", "nahi chahiye", "wrong", "galat", "cancel",
                     "नहीं", "गलत", "रद्द"],
        "weight": 3,
    },
    "CORRECT_FIELD": {
        "keywords": ["wrong", "galat", "change", "correct", "correction", "badlo",
                     "गलत", "बदलो", "सुधार"],
        "weight": 2,
    },
    "ASK_HELP": {
        "keywords": ["help", "madad", "sahayata", "what is", "kya hai", "how to",
                     "guide", "samajh", "explain", "मदद", "सहायता", "कैसे"],
        "weight": 1,
    },
    "ESCALATE": {
        "keywords": ["officer", "human", "complaint", "problem", "not working",
                     "senior", "supervisor", "शिकायत", "अधिकारी"],
        "weight": 2,
    },
    "GREETING": {
        "keywords": ["hello", "hi", "namaste", "namaskar", "good morning", "good evening",
                     "नमस्ते", "नमस्कार", "प्रणाम"],
        "weight": 1,
    },
}

# ── Service Type Detector ─────────────────────────────────────────────────

SERVICE_KEYWORDS = {
    "income_certificate":   ["income", "aay", "आय", "salary", "earning", "annual income"],
    "caste_certificate":    ["caste", "jati", "जाति", "sc", "st", "obc certificate", "जाती"],
    "obc_ncl_certificate":  ["obc ncl", "non creamy", "ncl", "non-creamy", "ओबीसी"],
    "domicile_certificate": ["domicile", "niwas", "निवास", "residence", "local", "रहिवासी"],
}

# ── Slot Value Patterns ────────────────────────────────────────────────────

SLOT_PATTERNS = {
    "aadhaar_number":   r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    "phone_number":     r"\b[6-9]\d{9}\b",
    "date_of_birth":    r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
    "annual_income":    r"\b(\d[\d,]+)\b",
    "pincode":          r"\b[1-9]\d{5}\b",
    "application_number": r"\b(REV|APP|TRK)-[A-Z0-9-]+\b",
    "tracking_id":      r"\b(TRK|TRACK)-[A-Z0-9-]+\b",
    "pan_number":       r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
}


class IntentClassifier:
    """
    Multi-tier intent classifier with keyword scoring + slot extraction.
    """

    def classify(self, text: str, language: str = "en",
                 current_slot: Optional[str] = None,
                 conversation_state: Optional[str] = None) -> Dict:
        """
        Classify intent from utterance.
        Returns: {intent, confidence, service_type, entities, needs_clarification}
        """
        text_lower = text.lower().strip()

        # Score each intent
        scores: Dict[str, float] = {}
        for intent, spec in INTENTS.items():
            keywords = spec["keywords"]
            weight = spec["weight"]
            hit_count = sum(1 for kw in keywords if kw.lower() in text_lower)
            if hit_count > 0:
                scores[intent] = hit_count * weight

        # Context boost: if we're in slot-filling mode, assume GIVE_FIELD_VALUE
        if conversation_state in ("COLLECTING_DATA", "SLOT_FILLING") and not scores:
            scores["GIVE_FIELD_VALUE"] = 1.5

        if not scores:
            intent = "UNKNOWN"
            confidence = 0.0
        else:
            intent = max(scores, key=scores.get)
            max_score = scores[intent]
            confidence = min(max_score / 5.0, 1.0)

        # Detect service type
        service_type = self._detect_service(text_lower)

        # Extract slot entities
        entities = self._extract_entities(text)

        return {
            "intent": intent,
            "confidence": round(confidence, 2),
            "service_type": service_type,
            "entities": entities,
            "needs_clarification": confidence < 0.4 and intent == "UNKNOWN",
            "raw_text": text,
            "language": language,
        }

    def _detect_service(self, text_lower: str) -> Optional[str]:
        for svc_id, keywords in SERVICE_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return svc_id
        return None

    def _extract_entities(self, text: str) -> Dict:
        entities = {}
        for slot_name, pattern in SLOT_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group()
                # Normalize
                if slot_name == "annual_income":
                    raw = raw.replace(",", "")
                elif slot_name == "aadhaar_number":
                    raw = raw.replace(" ", "")
                elif slot_name == "date_of_birth":
                    groups = match.groups()
                    if groups:
                        d, m, y = groups
                        raw = f"{d.zfill(2)}-{m.zfill(2)}-{y}"
                entities[slot_name] = raw
        return entities


# ── Slot Extractor ────────────────────────────────────────────────────────

class SlotExtractor:
    """
    Extracts field values from free-form user utterances,
    matched against a service spec's slot definitions.
    """

    def extract(self, text: str, expected_slot: Optional[str],
                slot_spec: Optional[dict] = None) -> Tuple[Optional[str], float]:
        """
        Extract value for the expected_slot from text.
        Returns (extracted_value, confidence).
        """
        if not expected_slot:
            return None, 0.0

        # Try pattern-based extraction first
        pattern = SLOT_PATTERNS.get(expected_slot)
        if pattern:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = self._normalize_value(expected_slot, match)
                return value, 0.95

        # For text fields (name, address), take the whole utterance if short
        text_clean = text.strip()
        if len(text_clean) > 2:
            return text_clean, 0.7

        return None, 0.0

    def _normalize_value(self, slot_name: str, match: re.Match) -> str:
        raw = match.group()
        if slot_name == "annual_income":
            return raw.replace(",", "")
        if slot_name == "aadhaar_number":
            return raw.replace(" ", "")
        if slot_name == "date_of_birth":
            groups = match.groups()
            if groups and len(groups) == 3:
                d, m, y = groups
                return f"{d.zfill(2)}-{m.zfill(2)}-{y}"
        return raw.strip()

    def validate_value(self, slot_name: str, value: str) -> Tuple[bool, str]:
        """Validate extracted value. Returns (is_valid, error_message)."""
        if slot_name == "aadhaar_number":
            if not re.match(r"^\d{12}$", value.replace(" ", "")):
                return False, "Aadhaar must be 12 digits"
        elif slot_name == "phone_number":
            if not re.match(r"^[6-9]\d{9}$", value):
                return False, "Phone must be 10 digits starting with 6-9"
        elif slot_name == "annual_income":
            try:
                amount = int(value.replace(",", ""))
                if amount < 0 or amount > 10_000_000:
                    return False, "Invalid income amount"
            except ValueError:
                return False, "Income must be a number"
        elif slot_name == "pincode":
            if not re.match(r"^[1-9]\d{5}$", value):
                return False, "Pincode must be 6 digits"
        return True, ""


# ── Q&A Handler ────────────────────────────────────────────────────────────

class QAHandler:
    """
    Handles help questions and cross-service queries.
    Returns pre-defined answers for common government service queries.
    """

    FAQ: Dict[str, Dict[str, str]] = {
        "what_is_income_certificate": {
            "en": "An Income Certificate is an official document proving your annual family income, issued by the Tehsildar. It is required for government schemes, scholarships, and fee waivers.",
            "hi": "आय प्रमाण पत्र एक सरकारी दस्तावेज़ है जो तहसीलदार द्वारा जारी किया जाता है और आपकी वार्षिक आय को प्रमाणित करता है। यह सरकारी योजनाओं और छात्रवृत्ति के लिए आवश्यक है।",
            "mr": "उत्पन्न प्रमाणपत्र हे तहसीलदारांद्वारे जारी केलेले अधिकृत दस्तावेज आहे जे तुमचे वार्षिक कौटुंबिक उत्पन्न सिद्ध करते.",
        },
        "what_is_caste_certificate": {
            "en": "A Caste Certificate proves your belonging to SC/ST/OBC community, required for reservations, scholarships, and government job applications.",
            "hi": "जाति प्रमाण पत्र आपकी SC/ST/OBC समुदाय से संबद्धता को प्रमाणित करता है। यह आरक्षण, छात्रवृत्ति और सरकारी नौकरी के लिए आवश्यक है।",
            "mr": "जात प्रमाणपत्र SC/ST/OBC समुदायाशी तुमचे संबंध सिद्ध करते. आरक्षण व शिष्यवृत्तीसाठी आवश्यक आहे.",
        },
        "fee": {
            "en": "Application fee is ₹50. BPL category applicants are exempt from fee.",
            "hi": "आवेदन शुल्क ₹50 है। BPL श्रेणी के आवेदकों को शुल्क से छूट है।",
            "mr": "अर्ज शुल्क ₹50 आहे. BPL श्रेणीतील अर्जदारांना शुल्क माफ आहे.",
        },
        "time": {
            "en": "Processing typically takes 7 working days after document verification.",
            "hi": "दस्तावेज़ सत्यापन के बाद प्रसंस्करण आमतौर पर 7 कार्य दिवस लेता है।",
            "mr": "कागदपत्र सत्यापनानंतर प्रक्रियेला सहसा 7 कामकाजाचे दिवस लागतात.",
        },
        "documents_required": {
            "en": "Required: Aadhaar Card, recent passport photo, and income/caste/address proof depending on the service.",
            "hi": "आवश्यक दस्तावेज़: आधार कार्ड, हाल की पासपोर्ट फोटो, और सेवा के अनुसार आय/जाति/पते का प्रमाण।",
            "mr": "आवश्यक: आधार कार्ड, अलीकडील पासपोर्ट फोटो, आणि सेवेनुसार उत्पन्न/जात/पत्त्याचा पुरावा.",
        },
    }

    def answer(self, question: str, language: str = "en") -> Optional[str]:
        """Return FAQ answer matching question keywords."""
        q_lower = question.lower()
        if "income" in q_lower or "aay" in q_lower:
            return self._get(self.FAQ["what_is_income_certificate"], language)
        if "caste" in q_lower or "jati" in q_lower or "जाति" in q_lower:
            return self._get(self.FAQ["what_is_caste_certificate"], language)
        if "fee" in q_lower or "shulk" in q_lower or "शुल्क" in q_lower or "kitna" in q_lower:
            return self._get(self.FAQ["fee"], language)
        if "time" in q_lower or "din" in q_lower or "दिन" in q_lower or "how long" in q_lower:
            return self._get(self.FAQ["time"], language)
        if "document" in q_lower or "kagaz" in q_lower or "कागज़" in q_lower:
            return self._get(self.FAQ["documents_required"], language)
        return None

    @staticmethod
    def _get(faq_entry: dict, language: str) -> str:
        return faq_entry.get(language, faq_entry.get("en", ""))


# ── Module singletons ─────────────────────────────────────────────────────
intent_classifier = IntentClassifier()
slot_extractor = SlotExtractor()
qa_handler = QAHandler()
