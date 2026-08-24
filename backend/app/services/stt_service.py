"""
STT Service — Speech-to-Text adapter (free, offline-first)
Primary: OpenAI Whisper (local, free, 100+ languages including all Indian languages)
Fallback: Mock (returns empty string with log warning)
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
    Speech-to-Text using Whisper (local, free, works offline).
    Supports all 13+ Indian languages natively.
    """

    WHISPER_LANGUAGE_MAP = {
        "en": "en", "hi": "hi", "mr": "mr", "bn": "bn",
        "gu": "gu", "ta": "ta", "te": "te", "kn": "kn",
        "ml": "ml", "pa": "pa", "or": "or", "as": "as", "ur": "ur",
    }

    _model = None

    @classmethod
    def _get_model(cls, model_size: str = "base"):
        if cls._model is None:
            try:
                import whisper
                cls._model = whisper.load_model(model_size)
                logger.info(f"Whisper model '{model_size}' loaded successfully")
            except ImportError:
                logger.warning("Whisper not installed. Run: pip install openai-whisper")
                cls._model = "UNAVAILABLE"
        return cls._model

    def transcribe(self, audio_file_path: str, language: str = None) -> STTResult:
        """
        Transcribe audio file to text.
        language: ISO 639-1 code or None for auto-detect
        """
        if not os.path.exists(audio_file_path):
            return STTResult(text="", detected_language=language or "en",
                             confidence=0.0, provider="none")

        model = self._get_model()

        if model == "UNAVAILABLE":
            return self._mock_transcribe(audio_file_path, language)

        try:
            whisper_lang = self.WHISPER_LANGUAGE_MAP.get(language) if language else None
            result = model.transcribe(
                audio_file_path,
                language=whisper_lang,
                task="transcribe",
                fp16=False,  # CPU mode
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
            return STTResult(text="", detected_language=language or "en",
                             confidence=0.0, provider="whisper_error")

    def convert_to_wav(self, input_path: str) -> str:
        """Convert audio to WAV format for Whisper (uses ffmpeg if available)."""
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
        # If ffmpeg not available, try to use original file
        return input_path

    def _mock_transcribe(self, audio_file_path: str, language: str) -> STTResult:
        logger.warning(f"STT mock: Whisper not available, returning empty for {audio_file_path}")
        return STTResult(text="[voice input not transcribed — whisper not installed]",
                         detected_language=language or "en",
                         confidence=0.0, provider="mock")
