"""
Phase 3 — NLU Module (v3.0)

Replaces LocalNLU (Ollama + keyword fallback) with NLUService.
NLUService delegates to the configured LLM provider (Gemini/Groq/OpenRouter).

NO Ollama. NO phi3:mini. NO keyword-only fallback for conversation.
If LLM fails → raise LLMUnavailableError → API returns 503.

Preserved: LiteracyAdaptiveDialogue (deterministic, not LLM — kept as-is)
Removed: LocalNLU, _analyze_with_keywords, _analyze_with_llm (Ollama), INTENT_CATALOGUE
"""
import logging
from typing import Dict, Optional

from app.llm.llm_service import LLMService
from app.llm.exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)


class NLUService:
    """
    LLM-powered NLU service.

    Calls the configured LLM provider (Gemini/Groq/OpenRouter) for:
    - Intent detection (CERTIFICATE_REQUEST, STATUS_QUERY, CROSS_QUESTION, SLOT_ANSWER, etc.)
    - Entity extraction (field_name → value)
    - Language detection
    - Literacy level estimation
    - Cross-question detection (is citizen asking a digression question?)

    NEVER uses keyword matching as the primary analysis method.
    NEVER calls Ollama or phi3:mini.

    On LLM failure: raises LLMUnavailableError → caller returns 503 to citizen.
    """

    def __init__(self):
        self._llm = LLMService()

    def analyze(
        self,
        text: str,
        language: str = "en",
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze citizen utterance and return structured NLU result.

        Returns dict with keys:
          intent: str  (CERTIFICATE_REQUEST | STATUS_QUERY | PAYMENT | HELP |
                        CANCEL | CORRECTION | CROSS_QUESTION | SLOT_ANSWER | UNKNOWN)
          service_type: str | None
          entities: dict[str, str]  — extracted field values
          pii_detected: list[str]   — field names containing PII
          literacy_level: str       — LOW | MEDIUM | HIGH
          language: str             — detected ISO 639-1 code
          is_cross_question: bool   — True if citizen is asking a digression
          cross_question_target: str | None — field name they're asking about

        Raises:
          LLMUnavailableError — when LLM provider fails. NEVER falls back to keywords.
        """
        result = self._llm.extract_nlu(text, language=language, context=context)

        # Normalize: ensure all expected keys are present and correctly typed
        result.setdefault("intent", "UNKNOWN")
        result.setdefault("service_type", None)
        result.setdefault("pii_detected", [])
        result.setdefault("literacy_level", "MEDIUM")
        result.setdefault("language", language)
        result.setdefault("is_cross_question", False)
        result.setdefault("cross_question_target", None)

        # Ensure entities is strictly a dict
        entities = result.get("entities")
        if isinstance(entities, list):
            new_entities = {}
            for item in entities:
                if isinstance(item, dict):
                    k = item.get("name") or item.get("entity") or item.get("slot") or item.get("field")
                    v = item.get("value")
                    if k and v:
                        new_entities[str(k)] = str(v)
                elif isinstance(item, str):
                    new_entities[item] = item
            result["entities"] = new_entities
        elif not isinstance(entities, dict):
            result["entities"] = {}

        logger.debug(
            f"NLU [{result['language']}] intent={result['intent']} "
            f"service={result.get('service_type')} "
            f"entities={list(result['entities'].keys())} "
            f"cross_q={result['is_cross_question']}"
        )

        return result


# ─────────────────────────────────────────────
# Literacy Adaptive Dialogue
# Kept as-is — deterministic, no LLM required.
# ─────────────────────────────────────────────

class LiteracyAdaptiveDialogue:
    """
    Adjusts response style based on detected literacy level.
    Deterministic — no LLM calls.
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
            if language == "hi":
                prompt += " (हाँ या नहीं बताएं)"
            elif language == "mr":
                prompt += " (होय किंवा नाही सांगा)"
            else:
                prompt += " (Please say YES or NO)"
        return prompt

    @classmethod
    def get_slot_prompt(cls, slot_spec, language: str, literacy_level: str) -> str:
        """Get appropriate prompt for a slot in the correct language (YAML fallback)."""
        prompts = (
            slot_spec.prompt
            if hasattr(slot_spec, "prompt")
            else slot_spec.get("prompt", {})
        )
        if isinstance(prompts, dict):
            prompt = prompts.get(language, prompts.get("en", ""))
        else:
            prompt = str(prompts)
        slot_name = (
            slot_spec.name if hasattr(slot_spec, "name") else slot_spec.get("name", "value")
        )
        if not prompt:
            prompt = f"Please provide your {slot_name.replace('_', ' ')}:"
        return cls.adapt_prompt(prompt, literacy_level, language)


# ─────────────────────────────────────────────
# Backward-compatible alias
# Any code importing LocalNLU will get NLUService.
# ─────────────────────────────────────────────
LocalNLU = NLUService
