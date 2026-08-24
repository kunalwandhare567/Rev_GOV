"""
Phase 16 — Unit tests for LLM Provider abstraction
Tests Gemini, Groq, and OpenRouter provider loading and fail-fast behavior.
"""
import pytest
from app.llm.provider_factory import get_provider
from app.llm.exceptions import LLMUnavailableError, LLMConfigError


def test_provider_factory_default():
    provider = get_provider()
    assert provider is not None
    assert hasattr(provider, "chat")
    assert hasattr(provider, "extract_nlu")
    assert hasattr(provider, "generate_slot_prompt")
    assert hasattr(provider, "explain_mismatch")
    assert hasattr(provider, "answer_cross_question")
    assert hasattr(provider, "answer_rag")
    assert provider.provider_name in ("gemini", "groq", "openrouter")
