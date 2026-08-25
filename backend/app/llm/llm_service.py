"""
LLM Service Facade.

ALL modules in the codebase must import THIS class, not individual providers.
This decouples business logic from provider specifics.

Usage:
    from app.llm.llm_service import LLMService

    llm = LLMService()
    nlu = llm.extract_nlu(text, language, context)
    prompt = llm.generate_slot_prompt("father_name", slot_spec, "hi", ctx)
    answer = llm.answer_cross_question(question, pending_field, svc_ctx, "mr")
"""
import logging
from typing import List, Dict, Optional

from app.llm.provider_factory import get_provider
from app.llm.base import LLMResponse, Message
from app.llm.exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)

__all__ = ["LLMService", "LLMUnavailableError"]


class LLMService:
    """
    Facade over the configured LLM provider.
    Instantiating this class does NOT create a new provider — it reuses the singleton.
    """

    def __init__(self):
        self._provider = get_provider()

    # ─────────────────────────────────────────────
    # Core Chat
    # ─────────────────────────────────────────────

    def chat(self, messages: List[Message], temperature: float = 0.3) -> LLMResponse:
        """Multi-turn conversation. Raises LLMUnavailableError on failure."""
        return self._provider.chat(messages, temperature)

    def chat_simple(self, text: str, system: Optional[str] = None) -> str:
        """Single-turn chat convenience method. Returns text string."""
        messages = []
        if system:
            messages.append(Message(role="system", content=system))
        messages.append(Message(role="user", content=text))
        result = self._provider.chat(messages)
        return result.text

    # ─────────────────────────────────────────────
    # NLU
    # ─────────────────────────────────────────────

    def extract_nlu(
        self,
        text: str,
        language: str = "en",
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Extract structured NLU from citizen utterance.
        Raises LLMUnavailableError on failure — no keyword fallback.
        """
        return self._provider.extract_nlu(text, language, context)

    # ─────────────────────────────────────────────
    # Dynamic Slot Questions
    # ─────────────────────────────────────────────

    def generate_slot_prompt(
        self,
        slot_name: str,
        slot_spec: Dict,
        language: str,
        context: Dict
    ) -> str:
        """Generate a natural slot question in citizen's language."""
        return self._provider.generate_slot_prompt(slot_name, slot_spec, language, context)

    # ─────────────────────────────────────────────
    # Mismatch Explanation
    # ─────────────────────────────────────────────

    def explain_mismatch(
        self,
        field: str,
        declared_value: str,
        doc_value: str,
        language: str = "en"
    ) -> str:
        """Explain field mismatch and ask citizen for resolution choice."""
        return self._provider.explain_mismatch(field, declared_value, doc_value, language)

    # ─────────────────────────────────────────────
    # Cross-Question Handling
    # ─────────────────────────────────────────────

    def answer_cross_question(
        self,
        question: str,
        pending_field: str,
        service_context: Dict,
        language: str = "en"
    ) -> str:
        """Answer citizen's digression, then return to pending slot."""
        return self._provider.answer_cross_question(question, pending_field, service_context, language)

    # ─────────────────────────────────────────────
    # RAG-Grounded Answers
    # ─────────────────────────────────────────────

    def answer_rag(
        self,
        question: str,
        knowledge_chunks: List[str],
        language: str = "en"
    ) -> str:
        """Answer using ONLY retrieved knowledge chunks. No hallucination."""
        return self._provider.answer_rag(question, knowledge_chunks, language)

    # ─────────────────────────────────────────────
    # OCR Normalization
    # ─────────────────────────────────────────────

    def normalize_ocr_fields(
        self,
        raw_text: str,
        extracted_fields: Dict,
        doc_type: str
    ) -> Dict:
        """
        Normalize noisy OCR extraction into clean fields with confidence scores.
        Raises LLMUnavailableError on provider failure.
        """
        return self._provider.normalize_ocr_fields(raw_text, extracted_fields, doc_type)

    # ─────────────────────────────────────────────
    # Provider Info
    # ─────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        return self._provider.model_name
