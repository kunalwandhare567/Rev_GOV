"""
Application Configuration
All settings loaded from environment variables / .env file.
No hardcoded values.
"""
import json
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Central configuration — all values from environment variables."""

    # Application
    APP_NAME: str = "Multilingual Voice-First Revenue Services Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str

    # Database
    DATABASE_URL: str = "sqlite:///./revenue_services.db"

    # API
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # LLM
    LLM_PROVIDER: str = "local"          # local | cloud
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "phi3:mini"
    LLM_FALLBACK_ENABLED: bool = True

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

    # Storage paths (local filesystem for POC)
    STORAGE_PATH: str = "./data/uploads"
    RECEIPT_PATH: str = "./data/receipts"
    CERTIFICATE_PATH: str = "./data/certificates"
    AUDIO_PATH: str = "./data/audio"

    # Session
    SESSION_TTL_MINUTES: int = 30

    # Fraud Scoring
    FRAUD_SCORE_THRESHOLD_REVIEW: float = 0.4
    FRAUD_SCORE_THRESHOLD_REJECT: float = 0.7

    # Seed credentials
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "Admin@123"
    OFFICER_USERNAME: str = "officer"
    OFFICER_PASSWORD: str = "Officer@123"

    # Service specs directory
    SERVICE_SPECS_DIR: str = "./seed/service_specs"

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
