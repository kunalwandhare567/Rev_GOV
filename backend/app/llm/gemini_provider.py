"""
Gemini LLM Provider.

Uses google-generativeai SDK (Gemini 1.5 Flash by default).
All calls return LLMResponse or raise LLMUnavailableError.
No fallback to keywords or other providers.

Responsibilities:
- Multi-turn chat for citizen conversation
- Structured NLU extraction with JSON mode
- Dynamic slot prompt generation in citizen's language
- Natural mismatch explanation
- Cross-question answer + resume pending slot
- RAG-grounded answers using retrieved knowledge chunks
"""
import json
import logging
from typing import List, Dict, Optional

from app.llm.base import LLMProvider, LLMResponse, Message
from app.llm.exceptions import LLMUnavailableError
from app.core.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# System Prompts
# ─────────────────────────────────────────────

NLU_SYSTEM_PROMPT = """You are an NLU system for an Indian government certificate services platform.
Analyze the user utterance and return ONLY a valid JSON object with these exact fields:
{
  "intent": "CERTIFICATE_REQUEST|STATUS_QUERY|PAYMENT|HELP|CANCEL|CORRECTION|CROSS_QUESTION|SLOT_ANSWER|UNKNOWN",
  "service_type": "income_certificate|caste_certificate|obc_ncl_certificate|domicile_certificate|null",
  "entities": {"field_name": "extracted_value"},
  "pii_detected": ["list_of_pii_fields"],
  "literacy_level": "LOW|MEDIUM|HIGH",
  "language": "detected_iso_639_1_code",
  "is_cross_question": true,
  "cross_question_target": "field_name_or_null"
}

Rules:
- intent=CROSS_QUESTION when citizen asks "why", "what is", "explain", about a field or requirement
- intent=SLOT_ANSWER when citizen is providing a value for the pending question
- intent=STATUS_QUERY when citizen asks "what is my status", "track", application number
- Extract ONLY explicitly stated entity values — never infer or invent
- PII: aadhaar_number, dob, mobile_number, bank_account
- Literacy: LOW=1-3 words/unclear, MEDIUM=4-15 words, HIGH=formal full sentences
- language: detect from script and vocabulary (hi=Hindi, mr=Marathi, en=English, etc.)
Return ONLY the JSON. No markdown. No explanation."""

SERVICE_SYSTEM_PROMPT = """You are a helpful, warm, and professional AI assistant for a Government Revenue Services platform in India.
You help citizens apply for Income Certificates, Caste Certificates, Domicile Certificates, and OBC-NCL Certificates.

Core rules:
- Be concise, warm, and professional — never robotic
- Always respond in the same language the citizen is using
- Never invent government requirements — only state what is provided in context
- Never reveal technical field names, database IDs, or internal system details
- After answering any digression question, always return to the pending application field
- If you don't know something, say "I don't have that information. Please visit your nearest Seva Kendra."
- Format responses as natural human speech, not bullet points (unless listing documents/fields)"""


# ─────────────────────────────────────────────
# Provider
# ─────────────────────────────────────────────

class GeminiProvider(LLMProvider):
    """Gemini 1.5 Flash provider using google-generativeai SDK."""

    def __init__(self):
        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise LLMUnavailableError(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )

        api_key = settings.GEMINI_API_KEY
        if not api_key or "replace_with_real_key" in api_key:
            raise LLMUnavailableError(
                "GEMINI_API_KEY is missing or contains placeholder. "
                "Get one at https://aistudio.google.com"
            )

        genai.configure(api_key=api_key)
        self._model_name = settings.GEMINI_MODEL or "gemini-1.5-flash"
        self._base_model = genai.GenerativeModel(self._model_name)
        logger.info(f"GeminiProvider initialized: {self._model_name}")

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _make_model(self, system_instruction: str, json_mode: bool = False):
        """Create a Gemini model with system instruction."""
        import google.generativeai as genai
        cfg = genai.GenerationConfig(temperature=0.1 if json_mode else 0.3)
        if json_mode:
            cfg = genai.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        return genai.GenerativeModel(
            self._model_name,
            system_instruction=system_instruction,
            generation_config=cfg,
        )

    def chat(self, messages: List[Message], temperature: float = 0.3) -> LLMResponse:
        """Multi-turn citizen conversation."""
        try:
            import google.generativeai as genai

            system_parts = [SERVICE_SYSTEM_PROMPT]
            history = []

            for m in messages:
                if m.role == "system":
                    system_parts.append(m.content)
                elif m.role == "user":
                    history.append({"role": "user", "parts": [m.content]})
                elif m.role == "assistant":
                    history.append({"role": "model", "parts": [m.content]})

            model = genai.GenerativeModel(
                self._model_name,
                system_instruction="\n\n".join(system_parts),
                generation_config=genai.GenerationConfig(temperature=temperature),
            )

            # Start chat with all history except the last user message
            prior = history[:-1] if len(history) > 1 else []
            last_msg = history[-1]["parts"][0] if history else "Hello"

            chat_session = model.start_chat(history=prior)
            response = chat_session.send_message(last_msg)
            text = response.text.strip()

            return LLMResponse(text=text, provider="gemini", model=self._model_name)

        except LLMUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            raise LLMUnavailableError(f"Gemini chat failed: {e}")

    def extract_nlu(self, text: str, language: str, context: Optional[Dict]) -> Dict:
        """Extract structured NLU using Gemini JSON mode."""
        try:
            model = self._make_model(NLU_SYSTEM_PROMPT, json_mode=True)
            prompt = (
                f"Utterance: {text}\n"
                f"Language hint: {language}\n"
                f"Conversation context: {json.dumps(context or {}, ensure_ascii=False)}"
            )
            response = model.generate_content(prompt)
            result = json.loads(response.text)
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Gemini NLU returned invalid JSON: {e}")
            raise LLMUnavailableError("Gemini NLU returned non-JSON response")
        except Exception as e:
            logger.error(f"Gemini NLU error: {e}")
            raise LLMUnavailableError(f"Gemini NLU failed: {e}")

    def generate_slot_prompt(
        self,
        slot_name: str,
        slot_spec: Dict,
        language: str,
        context: Dict
    ) -> str:
        """Generate a natural slot question in citizen's language."""
        try:
            lang_map = {
                "en": "English", "hi": "Hindi", "mr": "Marathi",
                "gu": "Gujarati", "ta": "Tamil", "te": "Telugu",
                "bn": "Bengali", "kn": "Kannada"
            }
            lang_full = lang_map.get(language, "English")
            service_name = context.get("service_name", "certificate")
            filled = context.get("filled_count", 0)
            total = context.get("total_count", 0)
            progress = f" ({filled}/{total} fields done)" if total else ""

            validation_hint = ""
            v = slot_spec.get("validation", {})
            if isinstance(v, dict):
                if v.get("format"):
                    validation_hint = f" Format: {v['format']}."
                if v.get("options"):
                    validation_hint = f" Options: {', '.join(str(o) for o in v['options'])}."
                if v.get("length"):
                    validation_hint = f" Must be exactly {v['length']} digits."

            # Use YAML prompt as fallback hint
            yaml_hint = ""
            yaml_prompts = slot_spec.get("prompt", {})
            if isinstance(yaml_prompts, dict) and language in yaml_prompts:
                yaml_hint = f" Base prompt: {yaml_prompts[language]}"

            prompt = (
                f"Generate a single, natural, friendly {lang_full} question to ask a citizen "
                f"applying for an Indian government {service_name}{progress}. "
                f"Ask them for: '{slot_name}'.{validation_hint}{yaml_hint} "
                f"Make it sound human and warm, not robotic. "
                f"Return ONLY the question. No explanation. No alternatives."
            )

            response = self._base_model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            logger.warning(f"Gemini slot prompt failed, using YAML fallback: {e}")
            # Graceful fallback to YAML prompt
            yaml_prompts = slot_spec.get("prompt", {})
            if isinstance(yaml_prompts, dict):
                return yaml_prompts.get(language, yaml_prompts.get("en", f"Please provide your {slot_name}:"))
            return f"Please provide your {slot_name}:"

    def explain_mismatch(
        self,
        field: str,
        declared_value: str,
        doc_value: str,
        language: str
    ) -> str:
        """Explain field mismatch in citizen's language and ask for resolution."""
        try:
            lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
            lang_full = lang_map.get(language, "English")

            prompt = (
                f"In {lang_full}, explain to a citizen applying for a government certificate "
                f"that there is a mismatch in their '{field}' field.\n\n"
                f"Their application says: '{declared_value}'\n"
                f"Their uploaded document shows: '{doc_value}'\n\n"
                f"Explain this clearly and warmly. Then ask them to choose:\n"
                f"1. Keep the application value: '{declared_value}'\n"
                f"2. Update to document value: '{doc_value}'\n\n"
                f"Be brief (3-4 sentences max). No technical jargon."
            )
            response = self._base_model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            logger.warning(f"Gemini mismatch explanation failed: {e}")
            return (
                f"There is a mismatch in your {field}.\n"
                f"Application: '{declared_value}'\n"
                f"Document: '{doc_value}'\n"
                f"Which value would you like to keep?\n"
                f"Reply '1' to keep application value or '2' to use document value."
            )

    def answer_cross_question(
        self,
        question: str,
        pending_field: str,
        service_context: Dict,
        language: str
    ) -> str:
        """Answer citizen's digression question, then return to pending slot."""
        try:
            lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
            lang_full = lang_map.get(language, "English")
            service_name = service_context.get("service_name", "certificate")
            knowledge = service_context.get("knowledge", "")

            prompt = (
                f"A citizen is applying for a government {service_name} in India. "
                f"They were being asked for their '{pending_field}' when they asked: '{question}'\n\n"
                f"Relevant service information:\n{knowledge}\n\n"
                f"In {lang_full}:\n"
                f"1. Answer their question briefly and accurately using the information above.\n"
                f"2. Then naturally transition back to asking for their '{pending_field}'.\n"
                f"Keep your response under 4 sentences total. Sound warm, not robotic."
            )
            response = self._base_model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            logger.warning(f"Gemini cross-question failed: {e}")
            return (
                f"That's a good question! I'll answer that after we complete your application. "
                f"Could you please provide your {pending_field.replace('_', ' ')}?"
            )

    def answer_rag(
        self,
        question: str,
        knowledge_chunks: List[str],
        language: str
    ) -> str:
        """Answer using ONLY the retrieved knowledge chunks — no hallucination."""
        try:
            lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
            lang_full = lang_map.get(language, "English")
            context = "\n\n---\n\n".join(knowledge_chunks[:5])

            prompt = (
                f"Using ONLY the following government service information:\n\n"
                f"{context}\n\n"
                f"Answer this citizen question in {lang_full}: '{question}'\n\n"
                f"IMPORTANT RULES:\n"
                f"- Use ONLY information from the context above\n"
                f"- If the answer is not in the context, say exactly: "
                f"'I don't have that specific information. Please visit your nearest Seva Kendra or call the helpline.'\n"
                f"- Do not invent requirements, fees, timelines, or documents\n"
                f"- Be clear and concise (3-5 sentences max)"
            )
            response = self._base_model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            logger.warning(f"Gemini RAG answer failed: {e}")
            return (
                "I don't have that information right now. "
                "Please visit your nearest Seva Kendra or call the government helpline for assistance."
            )
