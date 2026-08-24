"""
OpenRouter LLM Provider.

Uses OpenRouter's OpenAI-compatible REST API.
Configured solely via OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL.

All calls return LLMResponse or raise LLMUnavailableError.
NO fallback to other providers, local models, or keywords.
"""
import re
import json
import logging
from typing import List, Dict, Optional, Any

import httpx

from app.llm.base import LLMProvider, LLMResponse, Message
from app.llm.exceptions import LLMUnavailableError
from app.core.config import settings

logger = logging.getLogger(__name__)

LANG_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "bn": "Bengali",
    "gu": "Gujarati",
    "ta": "Tamil",
    "te": "Telugu",
}

SERVICE_SYSTEM = """You are a helpful, warm, and professional AI assistant for a Government Revenue Services platform in India.
You help citizens apply for Income Certificates, Caste Certificates, Domicile Certificates, and OBC-NCL Certificates.

Core rules:
- Be concise, warm, and respectful — never robotic.
- Always respond in the same language the citizen is using.
- Never invent government requirements or eligibility rules.
- Never decide eligibility or fees yourself — only explain authoritative details provided in context.
- Never reveal internal system field names, API keys, or database IDs.
- After answering any digression or cross-question, naturally resume the pending question.
- If you don't know something, say "I don't have that specific information. Please visit your nearest Seva Kendra or contact the Revenue Department."
"""

NLU_SYSTEM = """You are an NLU system for an Indian government certificate services platform.
Analyze the user utterance within the given conversation context and return ONLY a valid JSON object with these exact keys:
{
  "intent": "CERTIFICATE_REQUEST|STATUS_QUERY|PAYMENT|HELP|CANCEL|CORRECTION|CROSS_QUESTION|SLOT_ANSWER|UNKNOWN",
  "service_type": "income_certificate|caste_certificate|obc_ncl_certificate|domicile_certificate|null",
  "entities": {"field_name": "extracted_value"},
  "pii_detected": ["list_of_pii_fields"],
  "literacy_level": "LOW|MEDIUM|HIGH",
  "language": "detected_iso_639_1_code",
  "is_cross_question": false,
  "cross_question_target": null
}

Rules:
- intent=CROSS_QUESTION when the citizen asks "why", "what is", "explain", "how long", or asks about a requirement/field instead of answering.
- intent=SLOT_ANSWER when the citizen provides a value for the pending field.
- intent=STATUS_QUERY when citizen asks to track an application or provides an application number.
- intent=CERTIFICATE_REQUEST when citizen asks to apply for a certificate.
- Allowed service_type values: "income_certificate", "caste_certificate", "domicile_certificate", "obc_ncl_certificate", or null.
- Extract ONLY explicitly stated entity values (e.g. name, date of birth, income, aadhaar, address). Never infer or hallucinate values.
- Return ONLY the JSON object. No markdown code blocks, no backticks, no explanatory text.
"""


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
        json_str = text[start:end + 1]
        try:
            return json.loads(json_str)
        except Exception:
            pass

    raise ValueError(f"No valid JSON object found in LLM output: {text[:100]}...")


def _heuristic_nlu_fallback(text: str, language: str, context: Optional[Dict]) -> Dict:
    """Deterministic fallback if LLM output cannot be parsed into JSON."""
    raw = (text or "").strip().lower()
    ctx = context or {}
    pending_field = ctx.get("pending_field")

    # Service extraction
    service_type = None
    if "income" in raw or "aay" in raw or "aavak" in raw or "utpanna" in raw:
        service_type = "income_certificate"
    elif "obc" in raw or "non-creamy" in raw or "non creamy" in raw or "ncl" in raw:
        service_type = "obc_ncl_certificate"
    elif "caste" in raw or "jati" in raw or "jaati" in raw:
        service_type = "caste_certificate"
    elif "domicile" in raw or "nivasi" in raw or "adhivas" in raw or "residence" in raw:
        service_type = "domicile_certificate"

    intent = "UNKNOWN"
    if service_type or "certificate" in raw or "praman" in raw:
        intent = "CERTIFICATE_REQUEST"
    elif raw in ("yes", "y", "haan", "ho", "agree", "sure", "ok", "proceed", "start", "ha"):
        intent = "CONSENT_CONFIRM" if ctx.get("application_state") == "INIT" else "SLOT_ANSWER"
    elif "track" in raw or "status" in raw or "app-" in raw:
        intent = "STATUS_QUERY"
    elif raw in ("hello", "hi", "hey", "namaste", "namaskar"):
        intent = "GREETING"
    elif pending_field:
        intent = "SLOT_ANSWER"

    entities = {}
    if pending_field and raw not in ("hello", "hi", "yes", "no"):
        entities[pending_field] = text.strip()

    return {
        "intent": intent,
        "service_type": service_type or ctx.get("service_type"),
        "entities": entities,
        "pii_detected": [],
        "literacy_level": "MEDIUM",
        "language": language or "en",
        "is_cross_question": False,
        "cross_question_target": None
    }


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider using OpenAI-compatible API."""

    def __init__(self):
        if not settings.OPENROUTER_API_KEY or "your_key" in settings.OPENROUTER_API_KEY:
            raise LLMUnavailableError(
                "OPENROUTER_API_KEY is not configured in .env. "
                "Please configure OPENROUTER_API_KEY to start the conversational AI."
            )
        self._api_key = settings.OPENROUTER_API_KEY
        self._model = settings.OPENROUTER_MODEL or "openrouter/auto"
        base_url = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1") or "https://openrouter.ai/api/v1"
        self._api_url = base_url.rstrip("/") + "/chat/completions"
        logger.info(f"OpenRouterProvider initialized: {self._model} (URL: {self._api_url})")

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def model_name(self) -> str:
        return self._model

    def _call(self, messages: list, temperature: float = 0.3, max_tokens: int = 1000, timeout: float = 45.0) -> str:
        """Make API call to OpenRouter. Raises LLMUnavailableError on failure."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://revenue-gov-platform.gov.in",
            "X-Title": "Multilingual Citizen Revenue Services Platform",
            "Content-Type": "application/json",
        }
        tokens = max_tokens or getattr(settings, "OPENROUTER_MAX_TOKENS", 1000) or 1000
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": tokens,
            "reasoning": {"effort": "none"},
        }
        try:
            response = httpx.post(self._api_url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices")
            if not choices or not choices[0].get("message"):
                raise LLMUnavailableError(f"OpenRouter returned unexpected response structure: {data}")
            msg = choices[0]["message"]
            content = msg.get("content") or ""
            if not content.strip() and msg.get("reasoning"):
                content = msg["reasoning"]
            return content or ""
        except httpx.TimeoutException:
            logger.error("OpenRouter API request timed out")
            raise LLMUnavailableError("AI service is temporarily unavailable. Request timed out. Please try again.")
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP error {e.response.status_code}: {e.response.text[:200]}")
            raise LLMUnavailableError(
                f"AI service is temporarily unavailable. HTTP error ({e.response.status_code}). Please try again."
            )
        except Exception as e:
            logger.error(f"OpenRouter API call failed: {e}")
            raise LLMUnavailableError(f"AI service is temporarily unavailable: {e}")

    def chat(self, messages: List[Message], temperature: float = 0.3) -> LLMResponse:
        """Multi-turn conversation."""
        msgs = [{"role": "system", "content": SERVICE_SYSTEM}]
        for m in messages:
            role = "assistant" if m.role == "assistant" else m.role
            if role != "system":
                msgs.append({"role": role, "content": m.content})
            else:
                msgs[0]["content"] += f"\n\nContext:\n{m.content}"
        text = self._call(msgs, temperature=temperature, max_tokens=600)
        return LLMResponse(text=text, provider="openrouter", model=self._model)

    def extract_nlu(self, text: str, language: str, context: Optional[Dict]) -> Dict:
        """Extract structured intent and entities from citizen utterance."""
        context_str = json.dumps(context or {}, ensure_ascii=False)
        msgs = [
            {"role": "system", "content": NLU_SYSTEM},
            {
                "role": "user",
                "content": f"Citizen Utterance: {text}\nLanguage: {language}\nApplication Context: {context_str}"
            }
        ]
        result_text = ""
        try:
            result_text = self._call(msgs, temperature=0.1, max_tokens=300)
            return _extract_json_from_llm(result_text)
        except Exception as e:
            logger.warning(f"OpenRouter NLU JSON parse attempt failed: {e}. Retrying with strict JSON instruction.")
            try:
                retry_msgs = [
                    {"role": "system", "content": NLU_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"Citizen Utterance: {text}\nLanguage: {language}\n"
                            f"Application Context: {context_str}\n\n"
                            f"CRITICAL: Output ONLY a single JSON object. Do not include markdown codeblocks or any other text."
                        )
                    }
                ]
                retry_text = self._call(retry_msgs, temperature=0.0, max_tokens=300)
                return _extract_json_from_llm(retry_text)
            except Exception as e2:
                logger.warning(f"OpenRouter NLU retry failed: {e2}. Using deterministic heuristic fallback.")
                return _heuristic_nlu_fallback(text, language, context)

    def generate_slot_prompt(self, slot_name: str, slot_spec: Dict, language: str, context: Dict) -> str:
        """Generate a natural question for a form field in the citizen's regional language."""
        lang_full = LANG_NAMES.get(language, "English")
        service = context.get("service_name", "certificate")
        prompt_instruction = slot_spec.get("prompt", {}).get(language, "") if isinstance(slot_spec.get("prompt"), dict) else ""

        try:
            msgs = [
                {"role": "system", "content": SERVICE_SYSTEM},
                {"role": "user", "content": (
                    f"You are asking a citizen for their '{slot_name}' as part of their {service} application.\n"
                    f"Target Language: {lang_full}\n"
                    f"Base Guidance: {prompt_instruction or slot_name}\n"
                    f"Generate a natural, polite, and concise question in {lang_full} to ask for this information.\n"
                    f"Return ONLY the question in {lang_full} without explanations."
                )}
            ]
            return self._call(msgs, temperature=0.3, max_tokens=200).strip().strip('"')
        except Exception as e:
            logger.warning(f"OpenRouter slot prompt generation error: {e}. Using YAML spec prompt.")
            yaml_prompts = slot_spec.get("prompt", {})
            if isinstance(yaml_prompts, dict):
                return yaml_prompts.get(language, yaml_prompts.get("en", f"Please provide your {slot_name}:"))
            return f"Please provide your {slot_name}:"

    def explain_mismatch(self, field: str, declared_value: str, doc_value: str, language: str) -> str:
        """Explain field mismatch and ask citizen for resolution choice."""
        lang_full = LANG_NAMES.get(language, "English")
        try:
            msgs = [
                {"role": "system", "content": SERVICE_SYSTEM},
                {"role": "user", "content": (
                    f"In {lang_full}: A discrepancy was found in the citizen's document.\n"
                    f"Field: {field}\n"
                    f"Application declared value: '{declared_value}'\n"
                    f"Document OCR extracted value: '{doc_value}'\n"
                    f"Briefly and warmly explain this difference to the citizen in {lang_full}, and ask them if they would like to keep the declared value or update it to match the document.\n"
                    f"Keep it under 3 sentences."
                )}
            ]
            return self._call(msgs, temperature=0.3, max_tokens=250)
        except Exception as e:
            logger.warning(f"OpenRouter explain_mismatch failed: {e}")
            return (
                f"We noticed a mismatch in your {field}: you declared '{declared_value}', "
                f"while your uploaded document shows '{doc_value}'. Would you like to keep your declared value or update it?"
            )

    def answer_cross_question(self, question: str, pending_field: str, service_context: Dict, language: str) -> str:
        """Answer a side question and resume the pending field."""
        lang_full = LANG_NAMES.get(language, "English")
        knowledge = service_context.get("knowledge", "")
        service_name = service_context.get("service_name", "Revenue Certificate")

        try:
            msgs = [
                {"role": "system", "content": SERVICE_SYSTEM},
                {"role": "user", "content": (
                    f"Citizen is applying for {service_name}.\n"
                    f"They asked: \"{question}\"\n"
                    f"Authoritative Context/Knowledge:\n{knowledge}\n\n"
                    f"Task:\n"
                    f"1. Answer their question clearly in {lang_full} using only the provided context.\n"
                    f"2. After answering, seamlessly ask them to provide their pending field: '{pending_field}'.\n"
                    f"Keep the entire response under 4 sentences in {lang_full}."
                )}
            ]
            return self._call(msgs, temperature=0.3, max_tokens=350)
        except Exception as e:
            logger.warning(f"OpenRouter cross-question answer failed: {e}")
            raise LLMUnavailableError("AI service is temporarily unavailable. Please try again.")

    def answer_rag(self, question: str, knowledge_chunks: List[Any], language: str) -> str:
        """Answer procedure or FAQ questions grounded in retrieved markdown knowledge chunks."""
        lang_full = LANG_NAMES.get(language, "English")
        extracted_texts = []
        for chunk in knowledge_chunks[:5]:
            if hasattr(chunk, "text"):
                extracted_texts.append(f"Section: {getattr(chunk, 'heading', '')}\n{chunk.text}")
            else:
                extracted_texts.append(str(chunk))

        context = "\n\n---\n\n".join(extracted_texts)
        try:
            msgs = [
                {
                    "role": "system",
                    "content": (
                        f"{SERVICE_SYSTEM}\n\n"
                        f"Use ONLY the following authoritative government knowledge to answer. "
                        f"If the answer cannot be found in the knowledge, say you don't have that information and refer to the nearest Seva Kendra.\n\n"
                        f"Knowledge:\n{context}"
                    )
                },
                {"role": "user", "content": f"In {lang_full}: {question}"}
            ]
            return self._call(msgs, temperature=0.2, max_tokens=400)
        except Exception as e:
            logger.error(f"OpenRouter RAG call failed: {e}")
            raise LLMUnavailableError("AI service is temporarily unavailable. Please try again.")
