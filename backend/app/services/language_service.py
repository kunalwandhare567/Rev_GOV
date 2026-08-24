"""
Phase 4 completion — Language Service
Handles:
  1. Language detection from text (using langdetect or keyword heuristics)
  2. Language code normalization (ISO 639-1 → STT/TTS locale codes)
  3. Audio format conversion utility (MP3/OGG/WAV interconversion using pydub)
  4. Supported language registry for 13 Indian languages
"""
import os
import io
import logging
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Supported Languages ────────────────────────────────────────────────────

SUPPORTED_LANGUAGES = {
    "en":  {"name": "English",    "stt_locale": "en-IN",  "tts_lang": "en",  "tts_tld": "com.au"},
    "hi":  {"name": "हिंदी",       "stt_locale": "hi-IN",  "tts_lang": "hi",  "tts_tld": "co.in"},
    "mr":  {"name": "मराठी",       "stt_locale": "mr-IN",  "tts_lang": "mr",  "tts_tld": "co.in"},
    "gu":  {"name": "ગુજરાતી",     "stt_locale": "gu-IN",  "tts_lang": "gu",  "tts_tld": "co.in"},
    "te":  {"name": "తెలుగు",      "stt_locale": "te-IN",  "tts_lang": "te",  "tts_tld": "co.in"},
    "ta":  {"name": "தமிழ்",       "stt_locale": "ta-IN",  "tts_lang": "ta",  "tts_tld": "co.in"},
    "kn":  {"name": "ಕನ್ನಡ",       "stt_locale": "kn-IN",  "tts_lang": "kn",  "tts_tld": "co.in"},
    "ml":  {"name": "മലയാളം",      "stt_locale": "ml-IN",  "tts_lang": "ml",  "tts_tld": "co.in"},
    "bn":  {"name": "বাংলা",       "stt_locale": "bn-IN",  "tts_lang": "bn",  "tts_tld": "co.in"},
    "pa":  {"name": "ਪੰਜਾਬੀ",      "stt_locale": "pa-IN",  "tts_lang": "pa",  "tts_tld": "co.in"},
    "ur":  {"name": "اردو",       "stt_locale": "ur-IN",  "tts_lang": "ur",  "tts_tld": "co.in"},
    "or":  {"name": "ଓଡ଼ିଆ",       "stt_locale": "or-IN",  "tts_lang": "or",  "tts_tld": "co.in"},
    "as":  {"name": "অসমীয়া",     "stt_locale": "as-IN",  "tts_lang": "as",  "tts_tld": "co.in"},
}

# Script/character-range based language detection hints
SCRIPT_HINTS = {
    "devanagari": {
        "range": ("\u0900", "\u097F"),   # Hindi, Marathi, Sanskrit
        "candidates": ["hi", "mr"],
    },
    "gujarati": {
        "range": ("\u0A80", "\u0AFF"),
        "candidates": ["gu"],
    },
    "telugu": {
        "range": ("\u0C00", "\u0C7F"),
        "candidates": ["te"],
    },
    "tamil": {
        "range": ("\u0B80", "\u0BFF"),
        "candidates": ["ta"],
    },
    "kannada": {
        "range": ("\u0C80", "\u0CFF"),
        "candidates": ["kn"],
    },
    "malayalam": {
        "range": ("\u0D00", "\u0D7F"),
        "candidates": ["ml"],
    },
    "bengali": {
        "range": ("\u0980", "\u09FF"),
        "candidates": ["bn", "as"],
    },
    "punjabi": {
        "range": ("\u0A00", "\u0A7F"),
        "candidates": ["pa"],
    },
    "odia": {
        "range": ("\u0B00", "\u0B7F"),
        "candidates": ["or"],
    },
    "arabic": {
        "range": ("\u0600", "\u06FF"),
        "candidates": ["ur"],
    },
}

# Marathi-specific keywords (to distinguish from Hindi in Devanagari)
MARATHI_KEYWORDS = {
    "आहे", "नाही", "आणि", "हे", "ते", "मी", "तुम्ही", "त्यांनी",
    "प्रमाणपत्र", "अर्ज", "माझा", "त्यांचे", "आमच्या",
}
HINDI_KEYWORDS = {
    "है", "नहीं", "और", "यह", "वह", "मैं", "आप", "उन्होंने",
    "प्रमाण", "आवेदन", "मेरा", "उनका", "हमारे",
}


class LanguageService:
    """
    Detect language, normalize codes, and provide locale mappings.
    Three-tier detection:
      1. Script-based detection (Devanagari, Gujarati, etc.)
      2. Keyword disambiguation (Hindi vs Marathi in Devanagari)
      3. langdetect library fallback (if installed)
      4. Default to 'en'
    """

    def detect_language(self, text: str, fallback: str = "en") -> str:
        """
        Detect language code from text. Returns ISO 639-1 code.
        """
        if not text or len(text.strip()) < 3:
            return fallback

        text_stripped = text.strip()

        # ── 1. Script-based detection ──
        detected_script = self._detect_script(text_stripped)
        if detected_script:
            candidates = SCRIPT_HINTS[detected_script]["candidates"]
            if len(candidates) == 1:
                lang = candidates[0]
                logger.debug(f"Script-detected language: {lang} ({detected_script})")
                return lang

            # ── 2. Keyword disambiguation for Devanagari (hi vs mr) ──
            if detected_script == "devanagari":
                lang = self._disambiguate_devanagari(text_stripped)
                logger.debug(f"Disambiguated Devanagari → {lang}")
                return lang

        # ── 3. langdetect fallback ──
        try:
            from langdetect import detect
            detected = detect(text_stripped)
            # Map langdetect output to our codes
            mapped = self._normalize_langdetect(detected)
            if mapped in SUPPORTED_LANGUAGES:
                logger.debug(f"langdetect → {mapped}")
                return mapped
        except Exception:
            pass  # langdetect not installed or failed

        # ── 4. ASCII fallback → English ──
        if all(ord(c) < 128 for c in text_stripped.replace(" ", "")):
            return "en"

        return fallback

    def _detect_script(self, text: str) -> Optional[str]:
        """Detect predominant script in text by character range counting."""
        script_counts = {}
        for script_name, info in SCRIPT_HINTS.items():
            lo, hi = info["range"]
            count = sum(1 for c in text if lo <= c <= hi)
            if count > 0:
                script_counts[script_name] = count

        if not script_counts:
            return None
        return max(script_counts, key=script_counts.get)

    def _disambiguate_devanagari(self, text: str) -> str:
        """Distinguish Marathi from Hindi in Devanagari script."""
        words = set(text.split())
        mr_score = len(words & MARATHI_KEYWORDS)
        hi_score = len(words & HINDI_KEYWORDS)
        if mr_score > hi_score:
            return "mr"
        return "hi"

    @staticmethod
    def _normalize_langdetect(code: str) -> str:
        """Map langdetect codes to our ISO codes."""
        mapping = {
            "en": "en", "hi": "hi", "mr": "mr", "gu": "gu",
            "te": "te", "ta": "ta", "kn": "kn", "ml": "ml",
            "bn": "bn", "pa": "pa", "ur": "ur",
        }
        return mapping.get(code, "en")

    def get_stt_locale(self, lang: str) -> str:
        """Get Google/Whisper STT locale code for a language."""
        return SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["en"])["stt_locale"]

    def get_tts_config(self, lang: str) -> dict:
        """Get gTTS config (lang, tld) for a language."""
        cfg = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["en"])
        return {"lang": cfg["tts_lang"], "tld": cfg["tts_tld"]}

    def is_supported(self, lang: str) -> bool:
        return lang in SUPPORTED_LANGUAGES

    def get_language_name(self, lang: str) -> str:
        return SUPPORTED_LANGUAGES.get(lang, {}).get("name", lang)

    def list_supported(self) -> list:
        return [
            {"code": code, "name": info["name"], "stt_locale": info["stt_locale"]}
            for code, info in SUPPORTED_LANGUAGES.items()
        ]


# ── Audio Format Converter ─────────────────────────────────────────────────

class AudioConverter:
    """
    Convert audio between formats needed by the pipeline:
      - WhatsApp sends OGG/Opus → convert to WAV for Whisper STT
      - gTTS outputs MP3 → convert to OGG for WhatsApp delivery
    Uses pydub (requires ffmpeg on PATH). Gracefully degrades if not available.
    """

    @staticmethod
    def _pydub_available() -> bool:
        try:
            import pydub  # noqa
            return True
        except ImportError:
            return False

    @classmethod
    def ogg_to_wav(cls, input_path: str, output_path: Optional[str] = None) -> str:
        """Convert OGG/Opus to WAV for Whisper STT."""
        if not output_path:
            output_path = input_path.replace(".ogg", ".wav").replace(".opus", ".wav")

        if not cls._pydub_available():
            logger.warning("pydub not available — returning original OGG path for Whisper")
            return input_path

        from pydub import AudioSegment
        audio = AudioSegment.from_ogg(input_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(output_path, format="wav")
        logger.debug(f"Audio converted: {input_path} → {output_path}")
        return output_path

    @classmethod
    def mp3_to_ogg(cls, input_path: str, output_path: Optional[str] = None) -> str:
        """Convert gTTS MP3 output to OGG/Opus for WhatsApp voice notes."""
        if not output_path:
            output_path = input_path.replace(".mp3", ".ogg")

        if not cls._pydub_available():
            logger.warning("pydub not available — returning original MP3 path")
            return input_path

        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(input_path)
        audio.export(output_path, format="ogg", codec="libopus")
        logger.debug(f"Audio converted: {input_path} → {output_path}")
        return output_path

    @classmethod
    def mp3_to_wav(cls, input_path: str, output_path: Optional[str] = None) -> str:
        """Convert MP3 to WAV for Whisper (alternative to OGG)."""
        if not output_path:
            output_path = input_path.replace(".mp3", ".wav")

        if not cls._pydub_available():
            return input_path

        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(input_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(output_path, format="wav")
        return output_path

    @classmethod
    def get_audio_duration_seconds(cls, path: str) -> float:
        """Return audio duration in seconds (for IVR timeout logic)."""
        if not cls._pydub_available():
            return 0.0
        try:
            from pydub import AudioSegment
            ext = Path(path).suffix.lower().lstrip(".")
            audio = AudioSegment.from_file(path, format=ext)
            return len(audio) / 1000.0
        except Exception as e:
            logger.warning(f"Could not get audio duration: {e}")
            return 0.0


# Module-level singletons
language_service = LanguageService()
audio_converter = AudioConverter()
