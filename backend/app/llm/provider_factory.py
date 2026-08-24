"""
LLM Provider Factory.

Singleton pattern — creates exactly ONE provider instance per server lifetime.
Reads LLM_PROVIDER from settings and instantiates the correct implementation.

NO fallback between providers.
If the selected provider fails to initialize or make calls, it raises LLMUnavailableError.
"""
import logging
from typing import Optional

from app.llm.base import LLMProvider
from app.llm.exceptions import LLMUnavailableError
from app.core.config import settings

logger = logging.getLogger(__name__)

_instance: Optional[LLMProvider] = None


def get_provider() -> LLMProvider:
    """
    Return the singleton LLM provider instance.
    Directly instantiates ONLY the configured LLM_PROVIDER.
    NO fallback to other providers, local models, or keywords.
    """
    global _instance
    if _instance is not None:
        return _instance

    p = settings.LLM_PROVIDER.lower()
    logger.info(f"Initializing configured LLM provider: {p}")

    if p == "openrouter":
        try:
            from app.llm.openrouter_provider import OpenRouterProvider
            _instance = OpenRouterProvider()
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouterProvider: {e}")
            raise LLMUnavailableError(
                f"OpenRouter provider failed to initialize: {e}. Check OPENROUTER_API_KEY in .env"
            )

    elif p == "gemini":
        try:
            from app.llm.gemini_provider import GeminiProvider
            _instance = GeminiProvider()
        except Exception as e:
            logger.error(f"Failed to initialize GeminiProvider: {e}")
            raise LLMUnavailableError(
                f"Gemini provider failed to initialize: {e}. Check GEMINI_API_KEY in .env"
            )

    elif p == "groq":
        try:
            from app.llm.groq_provider import GroqProvider
            _instance = GroqProvider()
        except Exception as e:
            logger.error(f"Failed to initialize GroqProvider: {e}")
            raise LLMUnavailableError(
                f"Groq provider failed to initialize: {e}. Check GROQ_API_KEY in .env"
            )

    else:
        raise LLMUnavailableError(
            f"Unsupported LLM provider '{settings.LLM_PROVIDER}'. Supported: openrouter, gemini, groq"
        )

    logger.info(f"LLM provider active: {_instance.provider_name} (Model: {_instance.model_name})")
    return _instance


def reset_provider():
    """Reset the singleton (useful in tests)."""
    global _instance
    _instance = None
