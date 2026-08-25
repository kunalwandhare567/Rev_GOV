"""
Gemini Dialogue Service
Wraps Gemini 1.5 Flash for natural-language response generation.

IMPORTANT: This service ONLY formats/elaborates responses.
The state machine (orchestrator.py) drives ALL logic and transitions.
Gemini here is used purely as a language model to make responses feel
natural, conversational, and culturally appropriate — not for decision-making.

Gracefully degrades: if Gemini API key is missing or call fails,
returns the original fallback text unchanged.
"""
import re
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class GeminiDialogueService:
    """
    Natural dialogue generation using Gemini 1.5 Flash.

    Responsibilities:
      - rephrase()          : Make any template response sound natural
      - format_mismatch()   : Generate a human-friendly mismatch report
      - explain_mismatch_field() : Explain WHY a specific field mismatches
      - answer_question()   : Answer a citizen's general question using their context
      - voice_friendly()    : Shorten a response for TTS/voice output
      - slot_prompt()       : Generate a natural prompt for a form field
    """

    SYSTEM_PROMPT = (
        "You are a helpful assistant for an Indian government certificate services platform. "
        "You help citizens apply for Income, Caste, OBC-NCL, and Domicile certificates. "
        "You speak in a warm, clear, respectful tone — like a knowledgeable government clerk "
        "who genuinely wants to help. Your responses are concise, free of jargon, and practical. "
        "You do NOT make decisions — you only explain, clarify, and guide. "
        "Always keep responses under 5 sentences unless formatting a detailed report."
    )

    def __init__(self):
        self._model = None
        self._available: Optional[bool] = None

    # ── Public API ──────────────────────────────────────────────────────────

    def rephrase(
        self,
        raw_response: str,
        language: str = "en",
        context: Optional[Dict] = None,
    ) -> str:
        """
        Make a template response sound natural.
        Falls back to raw_response if Gemini unavailable.
        """
        if not self._is_available():
            return raw_response

        lang_instruction = self._lang_instruction(language)
        context_str = self._context_summary(context) if context else ""

        prompt = (
            f"{lang_instruction}\n"
            f"Rephrase the following government portal message to sound natural, warm, "
            f"and conversational — NOT like a robotic template. Keep all facts exactly the same. "
            f"Do NOT add new information. Do NOT change numbers, names, or dates.\n"
            f"{context_str}\n"
            f"Original message:\n{raw_response}\n\n"
            f"Rephrased (respond in {self._lang_name(language)} only):"
        )

        result = self._generate(prompt, max_tokens=400)
        return result if result else raw_response

    def format_mismatch(
        self,
        matched_fields: list,
        mismatched_fields: list,
        field_scores: dict,
        fields_not_in_doc: list,
        overall_score: float,
        language: str = "en",
    ) -> str:
        """
        Generate a detailed, natural-language mismatch report for the citizen.
        Includes matched fields, mismatched fields with scores, and missing fields.
        Falls back to a structured template if Gemini is unavailable.
        """
        # Build structured summary for Gemini context
        match_summary = []
        for f in matched_fields:
            s = field_scores.get(f, {})
            match_summary.append(
                f"  - {f.replace('_', ' ').title()}: ✅ Match ({s.get('score', 100):.0f}%)"
            )

        mismatch_summary = []
        for f in mismatched_fields:
            s = field_scores.get(f, {})
            mismatch_summary.append(
                f"  - {f.replace('_', ' ').title()}:\n"
                f"    You entered: \"{s.get('app_value', 'N/A')}\"\n"
                f"    Document says: \"{s.get('ocr_value', 'N/A')}\"\n"
                f"    Match score: {s.get('score', 0):.0f}%"
            )

        missing_summary = []
        for f in fields_not_in_doc:
            missing_summary.append(
                f"  - {f.replace('_', ' ').title()}: ⚠️ Not found in document"
            )

        if not self._is_available():
            return self._fallback_mismatch_message(
                matched_fields, mismatched_fields, field_scores,
                fields_not_in_doc, overall_score, language
            )

        lang_instruction = self._lang_instruction(language)
        prompt = (
            f"{lang_instruction}\n"
            f"You are helping a citizen understand the result of comparing their declared information "
            f"with what was extracted from their uploaded document using OCR.\n\n"
            f"Results:\n"
            f"Overall match score: {overall_score:.1f}%\n\n"
            f"Matched fields:\n" + ("\n".join(match_summary) if match_summary else "  None") + "\n\n"
            f"Mismatched fields:\n" + ("\n".join(mismatch_summary) if mismatch_summary else "  None") + "\n\n"
            f"Fields not found in document:\n" + ("\n".join(missing_summary) if missing_summary else "  None") + "\n\n"
            f"Write a clear, friendly message to the citizen explaining this result. "
            f"For each mismatch, briefly explain what differs. "
            f"End by asking them to choose: 1️⃣ Use document value, 2️⃣ Keep my entered value, 3️⃣ Enter new value.\n"
            f"Respond in {self._lang_name(language)} only. Be warm and helpful, not bureaucratic."
        )

        result = self._generate(prompt, max_tokens=600)
        return result if result else self._fallback_mismatch_message(
            matched_fields, mismatched_fields, field_scores,
            fields_not_in_doc, overall_score, language
        )

    def explain_field_mismatch(
        self,
        field_name: str,
        app_value: str,
        ocr_value: str,
        score: float,
        language: str = "en",
    ) -> str:
        """
        Explain WHY a specific field doesn't match — e.g. transliteration variants,
        date format differences, abbreviation differences.
        Falls back to a simple comparison string.
        """
        if not self._is_available():
            return (
                f"{field_name.replace('_', ' ').title()}: "
                f"You entered '{app_value}', document says '{ocr_value}' "
                f"(Match: {score:.0f}%)"
            )

        lang_instruction = self._lang_instruction(language)
        prompt = (
            f"{lang_instruction}\n"
            f"A citizen's {field_name.replace('_', ' ')} doesn't fully match their document.\n"
            f"Entered: \"{app_value}\"\n"
            f"Document: \"{ocr_value}\"\n"
            f"Similarity: {score:.0f}%\n\n"
            f"In 1-2 sentences, explain why these might differ "
            f"(e.g. spelling variation, transliteration, date format, OCR error). "
            f"Do not add advice, just explain the difference briefly. "
            f"Respond in {self._lang_name(language)} only."
        )

        result = self._generate(prompt, max_tokens=150)
        return result if result else (
            f"'{app_value}' vs '{ocr_value}' ({score:.0f}% match)"
        )

    def answer_question(
        self,
        question: str,
        app_context: Optional[Dict] = None,
        language: str = "en",
    ) -> str:
        """
        Answer a citizen's general question using their application context.
        Used when IntentClassifier detects ASK_HELP intent.
        Falls back to None so orchestrator uses FAQ handler instead.
        """
        if not self._is_available():
            return None

        lang_instruction = self._lang_instruction(language)
        context_str = self._context_summary(app_context) if app_context else ""

        prompt = (
            f"{lang_instruction}\n"
            f"A citizen is asking a question about their government certificate application.\n"
            f"{context_str}\n"
            f"Their question: \"{question}\"\n\n"
            f"Answer clearly and accurately in 2-3 sentences. "
            f"Only answer what you know about Indian government certificate services "
            f"(Income, Caste, OBC-NCL, Domicile certificates). "
            f"If you don't know, say so honestly. "
            f"Respond in {self._lang_name(language)} only."
        )

        result = self._generate(prompt, max_tokens=250)
        return result

    def voice_friendly(self, text: str, language: str = "en") -> str:
        """
        Shorten and simplify a response for TTS/voice output.
        Removes markdown formatting, emojis, and long sentences.
        """
        # Strip markdown symbols first (always, without Gemini)
        cleaned = re.sub(r'[*_`#\[\]]', '', text)
        cleaned = re.sub(r'[\U0001F300-\U0001FFFF\u2600-\u27FF]', '', cleaned)  # strip emojis
        cleaned = re.sub(r'\n+', '. ', cleaned)
        cleaned = re.sub(r'\.{2,}', '.', cleaned)
        cleaned = cleaned.strip()

        if not self._is_available() or len(cleaned) < 100:
            return cleaned

        lang_instruction = self._lang_instruction(language)
        prompt = (
            f"{lang_instruction}\n"
            f"Convert this text to a short, spoken-aloud format suitable for a voice assistant. "
            f"Remove lists, bullet points, numbers, and formatting. "
            f"Keep only the most important information in 2-3 sentences. "
            f"Respond in {self._lang_name(language)} only.\n\n"
            f"Text: {cleaned}"
        )

        result = self._generate(prompt, max_tokens=150)
        return result if result else cleaned

    def slot_prompt(
        self,
        slot_name: str,
        slot_description: str,
        filled_slots: dict,
        language: str = "en",
        literacy_level: str = "MEDIUM",
    ) -> str:
        """
        Generate a natural prompt for a form field, aware of context already filled.
        Falls back to slot_description directly.
        """
        if not self._is_available():
            return slot_description

        literacy_note = {
            "LOW": "Use very simple words. Keep under 10 words.",
            "MEDIUM": "Use clear, everyday language.",
            "HIGH": "Use formal, precise language.",
        }.get(literacy_level, "Use clear language.")

        filled_summary = ", ".join(
            f"{k.replace('_', ' ')}={v}" for k, v in (filled_slots or {}).items()
        )

        lang_instruction = self._lang_instruction(language)
        prompt = (
            f"{lang_instruction}\n"
            f"You are collecting information for a government certificate application. "
            f"The citizen has already provided: {filled_summary or 'nothing yet'}.\n"
            f"Now ask for: {slot_name.replace('_', ' ')} — {slot_description}\n"
            f"{literacy_note}\n"
            f"Write only the question, nothing else. Respond in {self._lang_name(language)} only."
        )

        result = self._generate(prompt, max_tokens=80)
        return result if result else slot_description

    # ── Internal helpers ────────────────────────────────────────────────────

    def _is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from app.core.config import settings
            if not settings.GEMINI_API_KEY:
                self._available = False
                return False
            # Validate key format — real Gemini keys start with AIza
            if not settings.GEMINI_API_KEY.startswith("AIza"):
                logger.warning(
                    "GeminiDialogueService: GEMINI_API_KEY does not appear to be a valid "
                    "Gemini API key (should start with 'AIza'). Natural dialogue disabled."
                )
                self._available = False
                return False
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._model = genai.GenerativeModel(
                "gemini-1.5-flash",
                system_instruction=self.SYSTEM_PROMPT,
            )
            self._available = True
            logger.info("GeminiDialogueService: Gemini 1.5 Flash ready for natural dialogue.")
        except Exception as e:
            logger.warning(f"GeminiDialogueService: Not available — {e}")
            self._available = False
        return self._available

    def _generate(self, prompt: str, max_tokens: int = 100) -> Optional[str]:
        """Call Gemini and return text, or None on any failure."""
        if not self._model:
            return None
        try:
            from app.core.config import settings
            max_limit = getattr(settings, "LLM_MAX_TOKENS", 100)
            tokens = min(max_tokens, max_limit)
            response = self._model.generate_content(
                prompt,
                generation_config={"max_output_tokens": tokens, "temperature": 0.4},
            )
            text = response.text.strip()
            return text if text else None
        except Exception as e:
            logger.warning(f"GeminiDialogueService._generate error: {e}")
            return None

    @staticmethod
    def _lang_instruction(language: str) -> str:
        instructions = {
            "en": "Respond in English.",
            "hi": "हिंदी में उत्तर दें।",
            "mr": "मराठीत उत्तर द्या.",
        }
        return instructions.get(language, "Respond in English.")

    @staticmethod
    def _lang_name(language: str) -> str:
        names = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
        return names.get(language, "English")

    @staticmethod
    def _context_summary(context: Optional[Dict]) -> str:
        if not context:
            return ""
        parts = []
        if context.get("service_type"):
            parts.append(f"Service: {context['service_type']}")
        if context.get("current_node"):
            parts.append(f"Stage: {context['current_node']}")
        if context.get("filled_slots"):
            filled = context["filled_slots"]
            parts.append(f"Citizen info: {', '.join(f'{k}={v}' for k, v in filled.items())}")
        return "Context: " + " | ".join(parts) if parts else ""

    def _fallback_mismatch_message(
        self,
        matched_fields: list,
        mismatched_fields: list,
        field_scores: dict,
        fields_not_in_doc: list,
        overall_score: float,
        language: str,
    ) -> str:
        """
        Structured fallback mismatch message when Gemini is unavailable.
        Multilingual, clear, actionable.
        """
        templates = {
            "en": {
                "header": f"📋 Document Verification Result — Overall Match: {overall_score:.1f}%\n",
                "match_label": "✅ Matched Fields:",
                "mismatch_label": "⚠️ Mismatched Fields:",
                "missing_label": "❓ Not Found in Document:",
                "app_val": "You entered",
                "doc_val": "Document says",
                "score": "Match",
                "footer": (
                    "\nHow would you like to resolve the mismatches?\n"
                    "1️⃣ Use document value\n"
                    "2️⃣ Keep my entered value\n"
                    "3️⃣ Enter a new value manually"
                ),
            },
            "hi": {
                "header": f"📋 दस्तावेज़ सत्यापन परिणाम — कुल मिलान: {overall_score:.1f}%\n",
                "match_label": "✅ मिलान हुए:",
                "mismatch_label": "⚠️ अंतर मिला:",
                "missing_label": "❓ दस्तावेज़ में नहीं मिला:",
                "app_val": "आपने दर्ज किया",
                "doc_val": "दस्तावेज़ में है",
                "score": "मिलान",
                "footer": (
                    "\nआप क्या करना चाहते हैं?\n"
                    "1️⃣ दस्तावेज़ का मान उपयोग करें\n"
                    "2️⃣ अपना दर्ज मान रखें\n"
                    "3️⃣ नया मान स्वयं दर्ज करें"
                ),
            },
            "mr": {
                "header": f"📋 कागदपत्र पडताळणी निकाल — एकूण जुळणी: {overall_score:.1f}%\n",
                "match_label": "✅ जुळलेले:",
                "mismatch_label": "⚠️ फरक आढळला:",
                "missing_label": "❓ कागदपत्रात सापडले नाही:",
                "app_val": "तुम्ही दिलेले",
                "doc_val": "कागदपत्रात",
                "score": "जुळणी",
                "footer": (
                    "\nतुम्हाला काय करायचे आहे?\n"
                    "1️⃣ कागदपत्राचे मूल्य वापरा\n"
                    "2️⃣ माझे दिलेले मूल्य ठेवा\n"
                    "3️⃣ नवीन मूल्य स्वतः टाका"
                ),
            },
        }
        t = templates.get(language, templates["en"])
        lines = [t["header"]]

        if matched_fields:
            lines.append(t["match_label"])
            for f in matched_fields:
                s = field_scores.get(f, {})
                lines.append(
                    f"  • {f.replace('_', ' ').title()} ({s.get('score', 100):.0f}%)"
                )
            lines.append("")

        if mismatched_fields:
            lines.append(t["mismatch_label"])
            for f in mismatched_fields:
                s = field_scores.get(f, {})
                lines.append(f"  • **{f.replace('_', ' ').title()}**")
                lines.append(f"    {t['app_val']}: \"{s.get('app_value', 'N/A')}\"")
                lines.append(f"    {t['doc_val']}: \"{s.get('ocr_value', 'N/A')}\"")
                lines.append(f"    {t['score']}: {s.get('score', 0):.0f}%")
            lines.append("")

        if fields_not_in_doc:
            lines.append(t["missing_label"])
            for f in fields_not_in_doc:
                lines.append(f"  • {f.replace('_', ' ').title()}")
            lines.append("")

        if mismatched_fields:
            lines.append(t["footer"])

        return "\n".join(lines)


# Module singleton — import this everywhere
gemini_dialogue = GeminiDialogueService()
