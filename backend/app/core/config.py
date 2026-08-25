"""
Application Configuration
All settings loaded from environment variables / .env file.
No hardcoded values. No Ollama. No local LLM. No fallback LLM.

LLM_PROVIDER must be one of: gemini | groq | openrouter
If the required API key is missing, the server will REFUSE TO START with a clear error.
There is no automatic fallback between providers.
"""
import json
import os
from pathlib import Path
from typing import List, Optional, Any, Union
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Central configuration — all values from environment variables."""

    # Application
    APP_NAME: str = "Multilingual AI-Powered Citizen Revenue Services Platform"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "revenue-services-dev-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'revenue_services.db'}"

    # API
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: Any = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:8000",
    ]

    # ─────────────────────────────────────────────
    # LLM Provider — ONE of: openrouter | gemini | groq
    # No Ollama. No phi3:mini. No local LLM.
    # No automatic fallback between providers.
    # ─────────────────────────────────────────────
    LLM_PROVIDER: str = "openrouter"
    LLM_MAX_TOKENS: int = 1000

    # OpenRouter (Primary default — 200+ models via single API key)
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "minimax/minimax-m3:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MAX_TOKENS: int = 1000

    # Gemini (free tier available)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Groq (extremely fast, Llama 3, free tier available)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama3-8b-8192"

    # ASR/TTS
    ASR_PROVIDER: str = "mock"
    TTS_PROVIDER: str = "mock"

    # Data Guard
    DATA_GUARD_ENABLED: bool = True
    DATA_GUARD_LOG_ALL: bool = True

    # Adapters
    AUTH_ADAPTER: str = "mock"
    PAYMENT_ADAPTER: str = "mock"
    DOCUMENT_ADAPTER: str = "mock"
    NOTIFICATION_ADAPTER: str = "mock"

    # Storage paths (anchored to backend directory for POC)
    STORAGE_PATH: str = str(BACKEND_DIR / "data" / "uploads")
    RECEIPT_PATH: str = str(BACKEND_DIR / "data" / "receipts")
    CERTIFICATE_PATH: str = str(BACKEND_DIR / "data" / "certificates")
    AUDIO_PATH: str = str(BACKEND_DIR / "data" / "audio")

    # Session
    SESSION_TTL_MINUTES: int = 30

    # Fraud Scoring
    FRAUD_SCORE_THRESHOLD_REVIEW: float = 0.4
    FRAUD_SCORE_THRESHOLD_REJECT: float = 0.7

    # Seed credentials — ADMIN ONLY (Officer persona removed)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "Admin@123"

    # OCR Configuration
    TESSERACT_CMD: Optional[str] = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    TESSERACT_PATH: Optional[str] = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # Service specs directory
    SERVICE_SPECS_DIR: str = str(BACKEND_DIR / "seed" / "service_specs")

    # JWT
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480   # 8 hours

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator(
        "SERVICE_SPECS_DIR",
        "STORAGE_PATH",
        "RECEIPT_PATH",
        "CERTIFICATE_PATH",
        "AUDIO_PATH",
        mode="after",
    )
    @classmethod
    def resolve_backend_relative_path(cls, v: str) -> str:
        if v and not os.path.isabs(v):
            cleaned = v.replace("\\", "/").lstrip("./")
            if cleaned.startswith("backend/"):
                cleaned = cleaned[8:]
            return str(BACKEND_DIR / cleaned)
        return v

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def resolve_database_url(cls, v: str) -> str:
        if v and v.startswith("sqlite:///"):
            raw_path = v[10:]
            if not os.path.isabs(raw_path):
                cleaned = raw_path.replace("\\", "/").lstrip("./")
                if cleaned.startswith("backend/"):
                    cleaned = cleaned[8:]
                return f"sqlite:///{BACKEND_DIR / cleaned}"
        return v

    @model_validator(mode="after")
    def validate_llm_provider(self):
        """
        Fail-fast validation: if LLM_PROVIDER is set but the required key is missing,
        raise a clear error immediately at startup.
        NO silent fallback. NO provider switching.
        """
        p = self.LLM_PROVIDER.lower()
        if p in ("openai_compatible", "open_router"):
            p = "openrouter"
            self.LLM_PROVIDER = "openrouter"

        supported = ("openrouter", "gemini", "groq")

        if p not in supported:
            raise ValueError(
                f"LLM_PROVIDER='{self.LLM_PROVIDER}' is not supported.\n"
                f"Supported providers: {', '.join(supported)}\n"
                f"Set LLM_PROVIDER in your .env file."
            )

        if p == "openrouter":
            if not self.OPENROUTER_API_KEY or "your_key" in self.OPENROUTER_API_KEY:
                raise ValueError(
                    "LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set or contains placeholder.\n"
                    "Get a key at: https://openrouter.ai"
                )

        if p == "gemini":
            if not self.GEMINI_API_KEY or "replace_with_real_key" in self.GEMINI_API_KEY:
                raise ValueError(
                    "LLM_PROVIDER=gemini but GEMINI_API_KEY is not set or contains placeholder.\n"
                    "Get a free API key at: https://aistudio.google.com"
                )

        if p == "groq" and not self.GROQ_API_KEY:
            raise ValueError(
                "LLM_PROVIDER=groq but GROQ_API_KEY is not set.\n"
                "Get a free API key at: https://console.groq.com"
            )

        return self

    model_config = {
        "env_file": [
            str(BACKEND_DIR / ".env"),
            str(BACKEND_DIR.parent / ".env"),
            ".env",
            "backend/.env",
            "../.env",
            "../../.env",
        ],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
