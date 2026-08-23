"""
Local NLU Pipeline
Primary: Ollama local LLM (Phi-3 / Llama 3.1 8B)
Fallback: Rule-based keyword intent matcher (always available)
No citizen data is ever sent to cloud in either path.
Architecture ref: Section 5.2.1, 6.1
"""
import re
import json
import logging
import httpx
from typing import Dict, List, Optional, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Intent & Entity Schemas
# ─────────────────────────────────────────────

INTENT_CATALOGUE = {
    "CERTIFICATE_REQUEST": [
        "certificate", "praman patra", "praman-patra", "apply", "chahiye", "need", "want",
        "income", "caste", "domicile", "obc", "ncl", "jati", "aay", "niwas",
    ],
    "STATUS_QUERY": [
        "status", "kya hua", "update", "progress", "application number", "track", "where",
        "kab milega", "kitne din", "how long",
    ],
    "PAYMENT": [
        "pay", "payment", "fee", "amount", "upi", "challan", "paisa", "rupee",
    ],
    "HELP": [
        "help", "madad", "sahayata", "guide", "what is", "kya hai", "how to", "kaise",
    ],
    "CANCEL": [
        "cancel", "band karo", "stop", "exit", "quit", "nahi chahiye",
    ],
    "CORRECTION": [
        "wrong", "galat", "change", "correct", "correction", "badlo", "sahi karo",
    ],
    "ESCALATION": [
        "officer", "human", "person", "problem", "complaint", "issue", "not working",
        "samajh nahi", "help me", "connect officer",
    ],
}

# Certificate type keywords
CERTIFICATE_TYPE_MAP = {
    "income_certificate": ["income", "aay", "aay praman", "salary", "earning", "आय"],
    "caste_certificate": ["caste", "jati", "जाति", "sc", "st", "obc certificate"],
    "obc_ncl_certificate": ["obc ncl", "non creamy", "non-creamy", "ncl", "obc non"],
    "domicile_certificate": ["domicile", "niwas", "निवास", "residence", "hometown", "local"],
}


class LocalNLU:
    """
    NLU Pipeline: Ollama local LLM with keyword fallback.
    Input: raw text (already transcribed, if voice)
    Output: {intent, sub_intent, entities, pii_detected, literacy_level}
    """

    def __init__(self):
        self.ollama_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.fallback_enabled = settings.LLM_FALLBACK_ENABLED
        self._ollama_available: Optional[bool] = None  # Lazily tested

    def analyze(self, text: str, language: str = "en", context: Optional[Dict] = None) -> Dict:
        """
        Analyze utterance and return intent/entities.
        Tries Ollama first, falls back to keyword matcher.
        """
        text_clean = text.strip()

        if settings.LLM_PROVIDER == "local" and self._is_ollama_available():
            try:
                return self._analyze_with_llm(text_clean, language, context)
            except Exception as e:
                logger.warning(f"Ollama analysis failed, using fallback: {e}")

        return self._analyze_with_keywords(text_clean, language)

    def _is_ollama_available(self) -> bool:
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            resp = httpx.get(f"{self.ollama_url}/api/tags", timeout=2.0)
            self._ollama_available = resp.status_code == 200
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def _analyze_with_llm(self, text: str, language: str, context: Optional[Dict]) -> Dict:
        """Call Ollama for structured intent/entity extraction."""
        system_prompt = """You are an NLU system for an Indian government certificate services platform.
Analyze the user utterance and return ONLY a JSON object with these exact fields:
{
  "intent": "CERTIFICATE_REQUEST|STATUS_QUERY|PAYMENT|HELP|CANCEL|CORRECTION|ESCALATION|UNKNOWN",
  "service_type": "income_certificate|caste_certificate|obc_ncl_certificate|domicile_certificate|null",
  "entities": {field_name: value},
  "pii_detected": [list of PII field names found],
  "literacy_level": "LOW|MEDIUM|HIGH",
  "language": "detected ISO language code"
}
Rules:
- Extract ONLY explicitly stated entities (do not infer)
- PII: names, aadhaar, dates of birth, phone numbers
- Literacy: LOW=one-word answers/unclear, MEDIUM=full sentences, HIGH=formal language
Return ONLY the JSON, no explanation."""

        user_prompt = f"Utterance: {text}\nContext: {json.dumps(context or {})}"

        response = httpx.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.model,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "format": "json",
            },
            timeout=15.0,
        )

        if response.status_code == 200:
            result_text = response.json().get("response", "{}")
            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                logger.warning("LLM returned non-JSON, using keyword fallback")
                return self._analyze_with_keywords(text, language)
        else:
            raise RuntimeError(f"Ollama API error: {response.status_code}")

    def _analyze_with_keywords(self, text: str, language: str) -> Dict:
        """Rule-based keyword intent matcher — always available fallback."""
        text_lower = text.lower()

        # Detect intent
        intent = "UNKNOWN"
        for candidate_intent, keywords in INTENT_CATALOGUE.items():
            if any(kw in text_lower for kw in keywords):
                intent = candidate_intent
                break

        # Detect service type
        service_type = None
        for svc_id, keywords in CERTIFICATE_TYPE_MAP.items():
            if any(kw in text_lower for kw in keywords):
                service_type = svc_id
                break

        # Simple entity extraction (numbers, dates)
        entities = {}
        # Extract 12-digit Aadhaar
        aadhaar_match = re.search(r"\b\d{12}\b", text)
        if aadhaar_match:
            entities["aadhaar_number"] = aadhaar_match.group()

        # Extract date patterns DD-MM-YYYY or DD/MM/YYYY
        date_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", text)
        if date_match:
            d, m, y = date_match.groups()
            entities["applicant_dob"] = f"{d.zfill(2)}-{m.zfill(2)}-{y}"

        # Extract income (number followed by rupee context)
        income_match = re.search(r"\b(\d[\d,]+)\b", text)
        if income_match and intent == "CERTIFICATE_REQUEST" and "income" in text_lower:
            entities["annual_income"] = income_match.group().replace(",", "")

        # PII detection (basic)
        pii_detected = []
        if aadhaar_match:
            pii_detected.append("aadhaar_number")
        if date_match:
            pii_detected.append("applicant_dob")

        # Literacy level estimation
        word_count = len(text.split())
        if word_count <= 2:
            literacy = "LOW"
        elif word_count <= 10:
            literacy = "MEDIUM"
        else:
            literacy = "HIGH"

        return {
            "intent": intent,
            "service_type": service_type,
            "entities": entities,
            "pii_detected": pii_detected,
            "literacy_level": literacy,
            "language": language,
            "method": "keyword_fallback",
        }


class LiteracyAdaptiveDialogue:
    """
    Adjusts response style based on detected literacy level.
    Architecture ref: Section 5.2.4
    """

    ADAPTATION_RULES = {
        "LOW": {
            "max_words_per_prompt": 15,
            "use_examples": True,
            "repeat_confirmation": True,
            "vocabulary": "basic",
        },
        "MEDIUM": {
            "max_words_per_prompt": 30,
            "use_examples": False,
            "repeat_confirmation": False,
            "vocabulary": "standard",
        },
        "HIGH": {
            "max_words_per_prompt": 60,
            "use_examples": False,
            "repeat_confirmation": False,
            "vocabulary": "formal",
        },
    }

    @classmethod
    def adapt_prompt(cls, prompt: str, literacy_level: str, language: str = "en") -> str:
        """Simplify prompt for low-literacy users."""
        rules = cls.ADAPTATION_RULES.get(literacy_level, cls.ADAPTATION_RULES["MEDIUM"])
        words = prompt.split()
        if len(words) > rules["max_words_per_prompt"]:
            prompt = " ".join(words[:rules["max_words_per_prompt"]]) + "..."
        if rules.get("repeat_confirmation"):
            prompt += " (Please say YES or NO)"
        return prompt

    @classmethod
    def get_slot_prompt(cls, slot_spec, language: str, literacy_level: str) -> str:
        """Get appropriate prompt for a slot in the correct language."""
        prompts = slot_spec.prompt if isinstance(slot_spec, dict) else getattr(slot_spec, "prompt", {})
        # Try exact language, then "en" as fallback
        prompt = prompts.get(language, prompts.get("en", f"Please provide: {slot_spec.get('name', 'value') if isinstance(slot_spec, dict) else slot_spec.name}"))
        return cls.adapt_prompt(prompt, literacy_level, language)
