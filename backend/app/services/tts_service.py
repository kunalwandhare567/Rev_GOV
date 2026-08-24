"""
TTS Service — Text-to-Speech (free, offline-first)
Primary: gTTS (Google Text-to-Speech, free tier, supports 13 Indian languages)
Output formats: MP3 (gTTS), OGG Opus (WhatsApp), WAV (IVR)
"""
import os
import logging
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    file_path: str
    format: str   # "mp3", "ogg", "wav"
    language: str
    provider: str


class TTSService:
    """
    Text-to-Speech using gTTS (free, no API key required).
    For 13 Indian languages: en, hi, mr, bn, gu, ta, te, kn, ml, pa, or, as, ur.
    """

    GTTS_LANGUAGE_MAP = {
        "en": "en",   # English (India)
        "hi": "hi",   # Hindi
        "mr": "mr",   # Marathi
        "bn": "bn",   # Bengali
        "gu": "gu",   # Gujarati
        "ta": "ta",   # Tamil
        "te": "te",   # Telugu
        "kn": "kn",   # Kannada
        "ml": "ml",   # Malayalam
        "pa": "pa",   # Punjabi
        "or": "or",   # Odia (may not be available — falls back to English)
        "as": "as",   # Assamese (may fall back)
        "ur": "ur",   # Urdu
    }

    def synthesize(self, text: str, language: str = "en",
                   output_format: str = "mp3", output_dir: str = None) -> TTSResult:
        """
        Convert text to speech audio file.
        output_format: "mp3" | "ogg" | "wav"
        Returns TTSResult with file path.
        """
        if output_dir is None:
            output_dir = "data/audio"
        os.makedirs(output_dir, exist_ok=True)

        lang_code = self.GTTS_LANGUAGE_MAP.get(language, "en")
        mp3_path = os.path.join(output_dir, f"tts_{hash(text[:50])}_{language}.mp3")

        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang=lang_code, slow=False)
            tts.save(mp3_path)
            logger.debug(f"TTS generated: {mp3_path}")
        except Exception as e:
            logger.warning(f"gTTS error for language {language}: {e}, falling back to English")
            try:
                from gtts import gTTS
                tts = gTTS(text=text, lang="en", slow=False)
                tts.save(mp3_path)
            except Exception as e2:
                logger.error(f"gTTS completely failed: {e2}")
                return TTSResult(file_path="", format=output_format,
                                 language=language, provider="error")

        # Convert to requested format
        if output_format == "mp3":
            return TTSResult(file_path=mp3_path, format="mp3",
                             language=language, provider="gtts")

        elif output_format == "ogg":
            # WhatsApp requires OGG Opus
            ogg_path = mp3_path.replace(".mp3", ".ogg")
            converted = self._convert_audio(mp3_path, ogg_path, "libopus")
            return TTSResult(file_path=converted or mp3_path, format="ogg",
                             language=language, provider="gtts")

        elif output_format == "wav":
            wav_path = mp3_path.replace(".mp3", ".wav")
            converted = self._convert_audio(mp3_path, wav_path, "pcm_s16le")
            return TTSResult(file_path=converted or mp3_path, format="wav",
                             language=language, provider="gtts")

        return TTSResult(file_path=mp3_path, format="mp3", language=language, provider="gtts")

    def synthesize_for_whatsapp(self, text: str, language: str = "en",
                                output_dir: str = None) -> str:
        """Returns OGG Opus path suitable for WhatsApp audio messages."""
        result = self.synthesize(text, language, output_format="ogg", output_dir=output_dir)
        return result.file_path

    def synthesize_for_ivr(self, text: str, language: str = "en",
                           output_dir: str = None) -> str:
        """Returns WAV path suitable for IVR/phone playback."""
        result = self.synthesize(text, language, output_format="wav", output_dir=output_dir)
        return result.file_path

    def _convert_audio(self, input_path: str, output_path: str, codec: str) -> str | None:
        """Convert audio using ffmpeg (if available)."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-i", input_path, "-c:a", codec, output_path, "-y"],
                capture_output=True, timeout=30
            )
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None
