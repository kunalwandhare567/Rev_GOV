"""
STT Service — Speech-to-Text adapter (free, offline-first)
Priority chain:
  1. Gemini Audio API (if GEMINI_API_KEY is valid) — best multilingual accuracy
  2. OpenAI Whisper (local, free, 100+ languages including all Indian languages)
  3. Mock (returns placeholder with log warning)
"""
import os
import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class STTResult:
    text: str
    detected_language: str
    confidence: float
    provider: str


class STTService:
    """
    Speech-to-Text using Gemini Audio API (primary) or Whisper (local fallback).
    Supports all Indian languages.
    """

    WHISPER_LANGUAGE_MAP = {
        "en": "en", "hi": "hi", "mr": "mr", "bn": "bn",
        "gu": "gu", "ta": "ta", "te": "te", "kn": "kn",
        "ml": "ml", "pa": "pa", "or": "or", "as": "as", "ur": "ur",
    }

    _whisper_model = None
    _gemini_available: Optional[bool] = None

    def transcribe(self, audio_file_path: str, language: str = None) -> STTResult:
        """
        Transcribe audio file to text.
        Tries Gemini Audio API first (if key is valid), then falls back to Whisper.
        language: ISO 639-1 code or None for auto-detect
        """
        if not os.path.exists(audio_file_path):
            return STTResult(text="", detected_language=language or "en",
                             confidence=0.0, provider="none")

        # 1. Try Gemini Audio transcription
        gemini_result = self._transcribe_with_gemini(audio_file_path, language)
        if gemini_result:
            return gemini_result

        # 2. Try local Whisper
        whisper_result = self._transcribe_with_whisper(audio_file_path, language)
        if whisper_result:
            return whisper_result

        # 3. Mock fallback
        return self._mock_transcribe(audio_file_path, language)

    def _transcribe_with_gemini(
        self, audio_file_path: str, language: str = None
    ) -> Optional[STTResult]:
        """
        Use Gemini 1.5 Flash to transcribe audio.
        Returns None if key is invalid or call fails (graceful degradation).
        """
        if STTService._gemini_available is False:
            return None

        try:
            from app.core.config import settings
            if not settings.GEMINI_API_KEY or not settings.GEMINI_API_KEY.startswith("AIza"):
                STTService._gemini_available = False
                return None

            import google.generativeai as genai
            import pathlib

            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-1.5-flash")

            # Upload audio file via Files API
            audio_bytes = pathlib.Path(audio_file_path).read_bytes()
            ext = audio_file_path.rsplit(".", 1)[-1].lower()
            mime_map = {
                "wav": "audio/wav", "mp3": "audio/mpeg",
                "ogg": "audio/ogg", "m4a": "audio/mp4",
                "webm": "audio/webm", "flac": "audio/flac",
            }
            mime_type = mime_map.get(ext, "audio/wav")

            import base64
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

            lang_hint = ""
            if language and language != "en":
                lang_names = {"hi": "Hindi", "mr": "Marathi", "bn": "Bengali",
                              "gu": "Gujarati", "ta": "Tamil", "te": "Telugu"}
                lang_name = lang_names.get(language, language)
                lang_hint = f" The audio is in {lang_name}."

            prompt = (
                f"Transcribe this audio file to text.{lang_hint} "
                f"Return ONLY the transcribed text, nothing else. "
                f"If the audio is silent or unclear, return an empty string."
            )

            response = model.generate_content([
                {"mime_type": mime_type, "data": audio_b64},
                prompt,
            ])

            text = response.text.strip()
            STTService._gemini_available = True

            return STTResult(
                text=text,
                detected_language=language or "en",
                confidence=0.92,
                provider="gemini_audio",
            )

        except Exception as e:
            logger.warning(f"Gemini STT failed, falling back to Whisper: {e}")
            if "API_KEY" in str(e) or "key" in str(e).lower():
                STTService._gemini_available = False
            return None

    def _transcribe_with_whisper(
        self, audio_file_path: str, language: str = None
    ) -> Optional[STTResult]:
        """Transcribe using local OpenAI Whisper model."""
        model = self._get_whisper_model()
        if model == "UNAVAILABLE":
            return None
        try:
            whisper_lang = self.WHISPER_LANGUAGE_MAP.get(language) if language else None
            result = model.transcribe(
                audio_file_path,
                language=whisper_lang,
                task="transcribe",
                fp16=False,
            )
            detected = result.get("language", language or "en")
            return STTResult(
                text=result["text"].strip(),
                detected_language=detected,
                confidence=0.9,
                provider="whisper_local",
            )
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return None

    @classmethod
    def _get_whisper_model(cls, model_size: str = "base"):
        if cls._whisper_model is None:
            try:
                import whisper
                cls._whisper_model = whisper.load_model(model_size)
                logger.info(f"Whisper model '{model_size}' loaded")
            except ImportError:
                logger.warning("Whisper not installed. Run: pip install openai-whisper")
                cls._whisper_model = "UNAVAILABLE"
        return cls._whisper_model

    def convert_to_wav(self, input_path: str) -> str:
        """Convert audio to WAV format using ffmpeg if available."""
        wav_path = input_path.rsplit(".", 1)[0] + ".wav"
        if os.path.exists(wav_path):
            return wav_path
        try:
            result = subprocess.run(
                ["ffmpeg", "-i", input_path, "-ar", "16000", "-ac", "1", wav_path, "-y"],
                capture_output=True, timeout=30
            )
            if result.returncode == 0:
                return wav_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return input_path

    def _mock_transcribe(self, audio_file_path: str, language: str) -> STTResult:
        logger.warning(
            f"STT: Both Gemini and Whisper unavailable. "
            f"Voice input from {audio_file_path} will not be transcribed."
        )
        return STTResult(
            text="[voice input not transcribed — install whisper or add valid GEMINI_API_KEY]",
            detected_language=language or "en",
            confidence=0.0,
            provider="mock",
        )

