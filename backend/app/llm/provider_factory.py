"""
LLM Provider Factory.

Singleton pattern — creates exactly ONE provider instance per server lifetime.
Reads LLM_PROVIDER from settings and instantiates the correct implementation.

NO fallback between providers.
If the selected provider fails to initialize, the server raises at startup.
"""
import logging
from typing import Optional

from app.llm.base import LLMProvider
from app.llm.exceptions import LLMUnavailableError
from app.core.config import settings

logger = logging.getLogger(__name__)

_instance: Optional[LLMProvider] = None


class FallbackLLMWrapper(LLMProvider):
    """
    Wraps primary provider (e.g. Gemini).
    If primary raises LLMUnavailableError or rate limit error,
    automatically falls back to secondary provider (e.g. OpenRouter).
    """

    def __init__(self, primary: LLMProvider, secondary: Optional[LLMProvider] = None):
        self.primary = primary
        self.secondary = secondary

    @property
    def provider_name(self) -> str:
        return self.primary.provider_name

    @property
    def model_name(self) -> str:
        return self.primary.model_name

    def chat(self, messages, temperature=0.3):
        try:
            return self.primary.chat(messages, temperature)
        except Exception as e:
            if self.secondary:
                logger.warning(f"Primary LLM ({self.primary.provider_name}) failed: {e}. Falling back to {self.secondary.provider_name}")
                return self.secondary.chat(messages, temperature)
            raise

    def extract_nlu(self, text, language, context):
        try:
            return self.primary.extract_nlu(text, language, context)
        except Exception as e:
            if self.secondary:
                logger.warning(f"Primary LLM ({self.primary.provider_name}) NLU failed: {e}. Falling back to {self.secondary.provider_name}")
                return self.secondary.extract_nlu(text, language, context)
            raise

    def generate_slot_prompt(self, slot_name, slot_spec, language, context):
        try:
            return self.primary.generate_slot_prompt(slot_name, slot_spec, language, context)
        except Exception as e:
            if self.secondary:
                logger.warning(f"Primary LLM slot prompt failed: {e}. Falling back to {self.secondary.provider_name}")
                return self.secondary.generate_slot_prompt(slot_name, slot_spec, language, context)
            raise

    def explain_mismatch(self, field, declared_value, doc_value, language):
        try:
            return self.primary.explain_mismatch(field, declared_value, doc_value, language)
        except Exception as e:
            if self.secondary:
                return self.secondary.explain_mismatch(field, declared_value, doc_value, language)
            raise

    def answer_cross_question(self, question, pending_field, service_context, language):
        try:
            return self.primary.answer_cross_question(question, pending_field, service_context, language)
        except Exception as e:
            if self.secondary:
                return self.secondary.answer_cross_question(question, pending_field, service_context, language)
            raise

    def answer_rag(self, question, knowledge_chunks, language):
        try:
            return self.primary.answer_rag(question, knowledge_chunks, language)
        except Exception as e:
            if self.secondary:
                return self.secondary.answer_rag(question, knowledge_chunks, language)
            raise


def get_provider() -> LLMProvider:
    """
    Return the singleton LLM provider instance.
    If primary provider (e.g. Gemini) fails, wraps with secondary fallback (e.g. OpenRouter).
    """
    global _instance
    if _instance is not None:
        return _instance

    p = settings.LLM_PROVIDER.lower()
    logger.info(f"Initializing LLM provider: {p}")

    primary = None
    secondary = None

    # Load primary provider
    if p == "gemini":
        try:
            from app.llm.gemini_provider import GeminiProvider
            primary = GeminiProvider()
        except Exception as e:
            logger.warning(f"Could not initialize primary Gemini provider: {e}")

    elif p == "groq":
        try:
            from app.llm.groq_provider import GroqProvider
            primary = GroqProvider()
        except Exception as e:
            logger.warning(f"Could not initialize primary Groq provider: {e}")

    elif p == "openrouter":
        try:
            from app.llm.openrouter_provider import OpenRouterProvider
            primary = OpenRouterProvider()
        except Exception as e:
            logger.warning(f"Could not initialize primary OpenRouter provider: {e}")

    # Load fallback secondary provider (OpenRouter if configured)
    if settings.OPENROUTER_API_KEY and p != "openrouter":
        try:
            from app.llm.openrouter_provider import OpenRouterProvider
            secondary = OpenRouterProvider()
            logger.info(f"Fallback secondary OpenRouter provider ready: {secondary.model_name}")
        except Exception as e:
            logger.warning(f"Could not initialize secondary OpenRouter provider: {e}")

    if not primary and not secondary:
        raise LLMUnavailableError(
            f"No LLM provider available. "
            f"Please check your GEMINI_API_KEY or OPENROUTER_API_KEY in .env"
        )

    active_primary = primary or secondary
    active_secondary = secondary if primary else None

    _instance = FallbackLLMWrapper(active_primary, active_secondary)
    logger.info(f"LLM provider ready: {_instance.provider_name}")
    return _instance


def reset_provider():
    """Reset the singleton."""
    global _instance
    _instance = None
