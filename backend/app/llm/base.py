"""
Abstract LLM Provider Base Class.

Every provider (Gemini, Groq, OpenRouter) must implement all abstract methods.
No fallback logic is ever placed in this class.
If the provider is unavailable, implementations raise LLMUnavailableError.

Adding a new provider: create a new class implementing LLMProvider,
then register it in provider_factory.py.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class Message:
    """A single conversation message."""
    role: str       # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    """Standard response from any LLM provider."""
    text: str
    provider: str
    model: str
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """
    Abstract base class that every LLM provider must implement.
    Each method has a single, well-defined responsibility.

    RULE: No fallback logic is ever placed in any implementation.
    If the provider fails → raise LLMUnavailableError.
    The caller (API layer) handles the error and returns 503.
    """

    # ─────────────────────────────────────────────
    # Core Conversation
    # ─────────────────────────────────────────────

    @abstractmethod
    def chat(self, messages: List[Message], temperature: float = 0.3) -> LLMResponse:
        """
        Multi-turn conversation with the citizen.
        Used by the orchestrator for general conversation flow.

        Args:
            messages: Full conversation history as list of Message objects.
            temperature: 0.0 = deterministic, 1.0 = creative.

        Returns: LLMResponse with the assistant's reply.
        Raises: LLMUnavailableError on provider failure.
        """
        pass

    # ─────────────────────────────────────────────
    # NLU
    # ─────────────────────────────────────────────

    @abstractmethod
    def extract_nlu(
        self,
        text: str,
        language: str,
        context: Optional[Dict]
    ) -> Dict:
        """
        Extract structured NLU from citizen utterance.

        Returns dict with keys:
          intent: CERTIFICATE_REQUEST | STATUS_QUERY | PAYMENT | HELP |
                  CANCEL | CORRECTION | CROSS_QUESTION | SLOT_ANSWER | UNKNOWN
          service_type: income_certificate | caste_certificate | ... | null
          entities: {field_name: value}
          pii_detected: [list of PII field names found]
          literacy_level: LOW | MEDIUM | HIGH
          language: detected ISO 639-1 code
          is_cross_question: true | false
          cross_question_target: field name or null

        Raises: LLMUnavailableError on provider failure.
        """
        pass

    # ─────────────────────────────────────────────
    # Dynamic Question Generation
    # ─────────────────────────────────────────────

    @abstractmethod
    def generate_slot_prompt(
        self,
        slot_name: str,
        slot_spec: Dict,
        language: str,
        context: Dict
    ) -> str:
        """
        Generate a natural, friendly prompt for a required slot in citizen's language.

        Args:
            slot_name: Field name (e.g., "father_name")
            slot_spec: YAML slot spec dict with validation, prompt templates etc.
            language: ISO code (en/hi/mr/gu/ta/te)
            context: {service_name, filled_slots_count, total_slots, ...}

        Returns: Natural language question string in the citizen's language.
        Raises: LLMUnavailableError on provider failure.
        """
        pass

    # ─────────────────────────────────────────────
    # Mismatch Explanation
    # ─────────────────────────────────────────────

    @abstractmethod
    def explain_mismatch(
        self,
        field: str,
        declared_value: str,
        doc_value: str,
        language: str
    ) -> str:
        """
        Explain a document-vs-declaration field mismatch in natural language.
        Ask citizen to choose: keep declared or use document value.

        Returns: Explanation string in citizen's language.
        Raises: LLMUnavailableError on provider failure.
        """
        pass

    # ─────────────────────────────────────────────
    # Cross-Question Handling
    # ─────────────────────────────────────────────

    @abstractmethod
    def answer_cross_question(
        self,
        question: str,
        pending_field: str,
        service_context: Dict,
        language: str
    ) -> str:
        """
        Answer a citizen's digression question and return to the pending slot.

        Example:
            question = "Why do you need my father's name?"
            pending_field = "father_name"
            → Returns: explanation of why + natural return to the pending question.

        Args:
            question: The citizen's cross-question.
            pending_field: The slot that was being asked when citizen digressed.
            service_context: {service_name, knowledge (RAG chunks)}
            language: ISO code.

        Returns: Answer + smooth return to pending_field, in citizen's language.
        Raises: LLMUnavailableError on provider failure.
        """
        pass

    # ─────────────────────────────────────────────
    # RAG-Grounded Answers
    # ─────────────────────────────────────────────

    @abstractmethod
    def answer_rag(
        self,
        question: str,
        knowledge_chunks: List[str],
        language: str
    ) -> str:
        """
        Answer a citizen question using ONLY the retrieved knowledge chunks.
        LLM must NOT invent government requirements.

        If answer not in chunks: "I don't have that information. Please visit your nearest Seva Kendra."

        Args:
            question: Citizen's question.
            knowledge_chunks: Top-N relevant text chunks from knowledge base.
            language: ISO code.

        Returns: Grounded answer in citizen's language.
        Raises: LLMUnavailableError on provider failure.
        """
        pass

    # ─────────────────────────────────────────────
    # Provider Identity
    # ─────────────────────────────────────────────

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """e.g., 'gemini', 'groq', 'openrouter'"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """e.g., 'gemini-1.5-flash', 'llama3-8b-8192'"""
        pass
