"""
Groq LLM Provider.

Uses Groq's OpenAI-compatible REST API with Llama 3.
Groq is extremely fast (300+ tokens/sec) with a generous free tier.

All calls return LLMResponse or raise LLMUnavailableError.
No fallback to other providers.
"""
import json
import logging
from typing import List, Dict, Optional

import httpx

from app.llm.base import LLMProvider, LLMResponse, Message
from app.llm.exceptions import LLMUnavailableError
from app.core.config import settings

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

NLU_SYSTEM = """You are an NLU system for an Indian government certificate platform.
Extract intent, entities, language from the user utterance.
Allowed service_type values: "income_certificate", "caste_certificate", "domicile_certificate", "obc_ncl_certificate", or null.
Return ONLY a JSON object with: intent, service_type, entities, pii_detected,
literacy_level, language, is_cross_question, cross_question_target.
No markdown. No explanation. JSON only."""

SERVICE_SYSTEM = """You are a helpful AI assistant for a Government Revenue Services platform in India.
Help citizens apply for certificates. Be warm, concise, multilingual.
Never invent government requirements. Always respond in the citizen's language."""


class GroqProvider(LLMProvider):
    """Groq provider using OpenAI-compatible API with Llama 3."""

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise LLMUnavailableError(
                "GROQ_API_KEY is not configured. "
                "Get a free key at https://console.groq.com"
            )
        self._api_key = settings.GROQ_API_KEY
        self._model = settings.GROQ_MODEL or "llama3-8b-8192"
        logger.info(f"GroqProvider initialized: {self._model}")

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    def _call(
        self,
        messages: list,
        temperature: float = 0.3,
        json_mode: bool = False,
        timeout: float = 30.0
    ) -> str:
        """Make API call to Groq. Raises LLMUnavailableError on any failure."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": getattr(settings, "LLM_MAX_TOKENS", 100),
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = httpx.post(GROQ_API_URL, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            raise LLMUnavailableError("Groq API request timed out")
        except httpx.HTTPStatusError as e:
            raise LLMUnavailableError(f"Groq API HTTP error {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise LLMUnavailableError(f"Groq request failed: {e}")

    def chat(self, messages: List[Message], temperature: float = 0.3) -> LLMResponse:
        msgs = []
        has_system = False
        for m in messages:
            role = "assistant" if m.role == "assistant" else m.role
            if role == "system" and not has_system:
                msgs.insert(0, {"role": "system", "content": SERVICE_SYSTEM + "\n\n" + m.content})
                has_system = True
            elif role != "system":
                msgs.append({"role": role, "content": m.content})
        if not has_system:
            msgs.insert(0, {"role": "system", "content": SERVICE_SYSTEM})

        text = self._call(msgs, temperature)
        return LLMResponse(text=text, provider="groq", model=self._model)

    def extract_nlu(self, text: str, language: str, context: Optional[Dict]) -> Dict:
        msgs = [
            {"role": "system", "content": NLU_SYSTEM},
            {"role": "user", "content": f"Utterance: {text}\nLanguage hint: {language}\nContext: {json.dumps(context or {})}"}
        ]
        try:
            result = self._call(msgs, temperature=0.1, json_mode=True)
            return json.loads(result)
        except json.JSONDecodeError:
            raise LLMUnavailableError("Groq NLU returned non-JSON response")

    def generate_slot_prompt(self, slot_name: str, slot_spec: Dict, language: str, context: Dict) -> str:
        lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi", "gu": "Gujarati", "ta": "Tamil", "te": "Telugu"}
        lang_full = lang_map.get(language, "English")
        service = context.get("service_name", "certificate")

        # Use YAML fallback if Groq fails
        try:
            msgs = [
                {"role": "system", "content": SERVICE_SYSTEM},
                {"role": "user", "content": (
                    f"Generate a natural {lang_full} question to ask a citizen for "
                    f"'{slot_name}' for their {service} application. Return ONLY the question."
                )}
            ]
            return self._call(msgs)
        except Exception as e:
            logger.warning(f"Groq slot prompt failed: {e}")
            yaml_prompts = slot_spec.get("prompt", {})
            if isinstance(yaml_prompts, dict):
                return yaml_prompts.get(language, yaml_prompts.get("en", f"Please provide your {slot_name}:"))
            return f"Please provide your {slot_name}:"

    def explain_mismatch(self, field: str, declared_value: str, doc_value: str, language: str) -> str:
        lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
        msgs = [
            {"role": "system", "content": SERVICE_SYSTEM},
            {"role": "user", "content": (
                f"In {lang_map.get(language, 'English')}, explain to a citizen that their '{field}' "
                f"shows '{declared_value}' in the application but '{doc_value}' in their document. "
                f"Ask them to choose which to keep. Be brief and warm."
            )}
        ]
        try:
            return self._call(msgs)
        except Exception as e:
            logger.warning(f"Groq mismatch explain failed: {e}")
            return f"Mismatch in {field}: application has '{declared_value}', document has '{doc_value}'. Which should we keep?"

    def answer_cross_question(self, question: str, pending_field: str, service_context: Dict, language: str) -> str:
        lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
        knowledge = service_context.get("knowledge", "")
        msgs = [
            {"role": "system", "content": SERVICE_SYSTEM},
            {"role": "user", "content": (
                f"In {lang_map.get(language, 'English')}, answer: '{question}'\n"
                f"Context: {knowledge}\n"
                f"Then ask for '{pending_field}'. Max 4 sentences."
            )}
        ]
        try:
            return self._call(msgs)
        except Exception as e:
            logger.warning(f"Groq cross-question failed: {e}")
            return f"Good question! Could you also share your {pending_field.replace('_', ' ')}?"

    def answer_rag(self, question: str, knowledge_chunks: List[str], language: str) -> str:
        lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
        context = "\n\n".join(knowledge_chunks[:5])
        msgs = [
            {"role": "system", "content": f"Answer ONLY using:\n{context}\nIf unknown: 'Please visit Seva Kendra.'"},
            {"role": "user", "content": f"In {lang_map.get(language, 'English')}: {question}"}
        ]
        try:
            return self._call(msgs)
        except Exception as e:
            logger.warning(f"Groq RAG failed: {e}")
            return "I don't have that information. Please visit your nearest Seva Kendra."
