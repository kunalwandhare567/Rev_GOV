"""
OpenRouter LLM Provider.

Uses OpenRouter's OpenAI-compatible API, giving access to 200+ models.
Free tier available with models like meta-llama/llama-3.1-8b-instruct:free.

All calls return LLMResponse or raise LLMUnavailableError.
No fallback to other providers.
"""
import re
import json
import logging
from typing import List, Dict, Optional

import httpx

from app.llm.base import LLMProvider, LLMResponse, Message
from app.llm.exceptions import LLMUnavailableError
from app.core.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

SERVICE_SYSTEM = """You are a helpful AI assistant for a Government Revenue Services platform in India.
Help citizens apply for government certificates. Be warm, concise, multilingual.
Never invent government requirements. Always respond in the citizen's language."""

NLU_SYSTEM = """You are an NLU system for an Indian government certificate services platform.
Extract intent and entities from citizen utterance.
Allowed service_type values: "income_certificate", "caste_certificate", "domicile_certificate", "obc_ncl_certificate", or null.
Return ONLY valid JSON with: intent, service_type, entities, pii_detected,
literacy_level, language, is_cross_question, cross_question_target. JSON only."""


def _extract_json_from_llm(result_text: str) -> Dict:
    """Extract and parse JSON object from LLM response text, ignoring markdown wrappers."""
    if not result_text or not result_text.strip():
        raise ValueError("Empty response text from LLM")
    
    text = result_text.strip()
    
    # 1. Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2. Extract content from ```json { ... } ``` or ``` { ... } ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    # 3. Find first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end+1]
        try:
            return json.loads(json_str)
        except Exception:
            pass

    raise ValueError(f"No valid JSON object found in LLM output: {text[:100]}...")


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider using OpenAI-compatible API."""

    def __init__(self):
        if not settings.OPENROUTER_API_KEY:
            raise LLMUnavailableError(
                "OPENROUTER_API_KEY is not configured. "
                "Get a free key at https://openrouter.ai"
            )
        self._api_key = settings.OPENROUTER_API_KEY
        self._model = settings.OPENROUTER_MODEL or "meta-llama/llama-3.1-8b-instruct:free"
        logger.info(f"OpenRouterProvider initialized: {self._model}")

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def model_name(self) -> str:
        return self._model

    def _call(self, messages: list, temperature: float = 0.3, timeout: float = 30.0) -> str:
        """Make API call to OpenRouter. Raises LLMUnavailableError on failure."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://revenue-gov-platform.local",
            "X-Title": "Revenue Gov Platform",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        try:
            response = httpx.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            raise LLMUnavailableError("OpenRouter API request timed out")
        except httpx.HTTPStatusError as e:
            raise LLMUnavailableError(f"OpenRouter HTTP error {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.error(f"OpenRouter API call failed: {e}")
            raise LLMUnavailableError(f"OpenRouter call error: {e}")

    def chat(self, messages: List[Message], temperature: float = 0.3) -> LLMResponse:
        msgs = [{"role": "system", "content": SERVICE_SYSTEM}]
        for m in messages:
            role = "assistant" if m.role == "assistant" else m.role
            if role != "system":
                msgs.append({"role": role, "content": m.content})
        text = self._call(msgs, temperature)
        return LLMResponse(text=text, provider="openrouter", model=self._model)

    def extract_nlu(self, text: str, language: str, context: Optional[Dict]) -> Dict:
        msgs = [
            {"role": "system", "content": NLU_SYSTEM},
            {"role": "user", "content": f"Utterance: {text}\nLanguage: {language}\nContext: {json.dumps(context or {})}"}
        ]
        result_text = ""
        try:
            result_text = self._call(msgs, temperature=0.1)
            return _extract_json_from_llm(result_text)
        except Exception as e:
            logger.warning(f"OpenRouter NLU parse warning: {e}. Retrying with strict JSON prompt.")
            try:
                if result_text:
                    msgs.append({"role": "assistant", "content": result_text})
                    msgs.append({"role": "user", "content": "Return ONLY valid raw JSON object. No conversational text."})
                retry_text = self._call(msgs, temperature=0.0)
                return _extract_json_from_llm(retry_text)
            except Exception as e2:
                logger.error(f"OpenRouter NLU retry failed: {e2}")
                raise LLMUnavailableError(f"OpenRouter NLU non-JSON output: {e}")

    def generate_slot_prompt(self, slot_name: str, slot_spec: Dict, language: str, context: Dict) -> str:
        lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi", "gu": "Gujarati", "ta": "Tamil", "te": "Telugu"}
        lang_full = lang_map.get(language, "English")
        service = context.get("service_name", "certificate")
        try:
            msgs = [
                {"role": "system", "content": SERVICE_SYSTEM},
                {"role": "user", "content": (
                    f"Generate a natural {lang_full} question to ask a citizen for "
                    f"'{slot_name}' during their {service} application. "
                    f"Return ONLY the question."
                )}
            ]
            return self._call(msgs)
        except Exception as e:
            logger.warning(f"OpenRouter slot prompt failed: {e}")
            yaml_prompts = slot_spec.get("prompt", {})
            if isinstance(yaml_prompts, dict):
                return yaml_prompts.get(language, yaml_prompts.get("en", f"Please provide your {slot_name}:"))
            return f"Please provide your {slot_name}:"

    def explain_mismatch(self, field: str, declared_value: str, doc_value: str, language: str) -> str:
        lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
        try:
            msgs = [
                {"role": "system", "content": SERVICE_SYSTEM},
                {"role": "user", "content": (
                    f"In {lang_map.get(language, 'English')}: citizen's '{field}' "
                    f"is '{declared_value}' in application but '{doc_value}' in document. "
                    f"Explain and ask which to keep. Be brief and warm."
                )}
            ]
            return self._call(msgs)
        except Exception as e:
            logger.warning(f"OpenRouter mismatch failed: {e}")
            return f"Your {field}: application '{declared_value}' vs document '{doc_value}'. Which to keep?"

    def answer_cross_question(self, question: str, pending_field: str, service_context: Dict, language: str) -> str:
        lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
        knowledge = service_context.get("knowledge", "")
        try:
            msgs = [
                {"role": "system", "content": SERVICE_SYSTEM},
                {"role": "user", "content": (
                    f"In {lang_map.get(language, 'English')}: Answer '{question}' "
                    f"using: {knowledge}\nThen ask for '{pending_field}'. Max 4 sentences."
                )}
            ]
            return self._call(msgs)
        except Exception as e:
            logger.warning(f"OpenRouter cross-question failed: {e}")
            return f"Could you please provide your {pending_field.replace('_', ' ')}?"

    def answer_rag(self, question: str, knowledge_chunks: List[str], language: str) -> str:
        lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
        context = "\n\n".join(knowledge_chunks[:5])
        try:
            msgs = [
                {"role": "system", "content": f"Answer ONLY using:\n{context}\nIf unknown: refer to Seva Kendra."},
                {"role": "user", "content": f"In {lang_map.get(language, 'English')}: {question}"}
            ]
            return self._call(msgs)
        except Exception as e:
            logger.warning(f"OpenRouter RAG failed: {e}")
            return "Please visit your nearest Seva Kendra for that information."
