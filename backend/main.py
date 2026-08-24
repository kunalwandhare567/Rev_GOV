"""
Main FastAPI Application
Entry point for the Multilingual Voice-First Revenue Services Platform backend.
"""
import os
import sys
import uuid
import logging
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

# Force UTF-8 on Windows to avoid cp1252 emoji encoding errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes import conversation, applications, dashboard, data_guard, auth
from app.llm.exceptions import LLMUnavailableError
from app.api.routes import whatsapp, ivr, tracking, documents, payment, stream
from app.core.security import SecurityMiddleware


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)



# ─────────────────────────────────────────────
# Startup / Shutdown lifecycle
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, load service specs, and create required directories."""
    logger.info("🚀 Starting Revenue Services Platform...")

    # Create all SQLite tables
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables initialized (SQLite)")

    # Pre-load all YAML service specs into cache
    from app.rules_engine.engine import ServiceSpecLoader
    specs = ServiceSpecLoader.load_all()
    logger.info(f"✅ Service specs loaded: {list(specs.keys())}")

    # Create required storage directories
    for path in [
        settings.STORAGE_PATH, settings.RECEIPT_PATH,
        settings.CERTIFICATE_PATH, settings.AUDIO_PATH,
        "data/audio/ivr",          # IVR TTS audio
        "data/audio/whatsapp",     # WhatsApp TTS/voice
        "data/uploads",            # Document uploads
        "data/ocr_cache",          # OCR result cache
    ]:
        os.makedirs(path, exist_ok=True)
    # Initialize & verify OCR Service / Tesseract OCR
    from app.services.ocr_service import OCRService
    ocr_service_init = OCRService()
    if ocr_service_init.is_tesseract_available:
        logger.info(f"✅ OCR Engine ready (Tesseract OCR: {ocr_service_init.tesseract_path})")
    else:
        logger.info(f"ℹ️ OCR Engine ready (Vision / Fallback OCR active)")

    # Seed database if empty
    _seed_database()

    logger.info(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} is ready!")
    logger.info(f"📖 API Docs: http://localhost:8000/docs")

    yield

    logger.info("👋 Shutting down Revenue Services Platform")


def _seed_database():
    """Seed initial data: admin user, service catalogue entries."""
    from app.core.database import SessionLocal
    from app.models.db_models import User, Service
    from app.rules_engine.engine import ServiceSpecLoader
    from passlib.context import CryptContext

    db = SessionLocal()
    pwd_ctx = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

    try:
        # Seed admin user
        if not db.query(User).filter(User.username == settings.ADMIN_USERNAME).first():
            db.add(User(
                username=settings.ADMIN_USERNAME,
                hashed_password=pwd_ctx.hash(settings.ADMIN_PASSWORD),
                role="ADMIN",
            ))
            logger.info(f"✅ Admin user created: {settings.ADMIN_USERNAME}")

        # Officer persona removed — Admin absorbs all review functions

        # Seed service catalogue from YAML specs
        specs = ServiceSpecLoader.load_all()
        for spec in specs.values():
            if not db.query(Service).filter(Service.id == spec.id).first():
                db.add(Service(
                    id=spec.id,
                    name_en=spec.name.get("en", spec.id),
                    name_hi=spec.name.get("hi"),
                    name_ta=spec.name.get("ta"),
                    name_te=spec.name.get("te"),
                    department=spec.department,
                    fee_amount=spec.fee_amount,
                    fee_currency=spec.fee_currency,
                    sla_days=spec.sla_days,
                    required_docs=spec.required_docs,
                    waiver_conditions=spec.waiver_conditions,
                ))
                logger.info(f"✅ Service seeded: {spec.id}")

        db.commit()
    except Exception as e:
        logger.error(f"Seed error: {e}")
        db.rollback()
    finally:
        db.close()


import json
from typing import Any

class SafeJSONResponse(JSONResponse):
    """
    JSONResponse subclass that sanitizes UTF-16 surrogates before UTF-8 encoding
    to prevent UnicodeEncodeError crashes on Windows / LLM responses.
    """
    def render(self, content: Any) -> bytes:
        def _sanitize(obj):
            if isinstance(obj, str):
                return obj.encode("utf-8", "replace").decode("utf-8", "replace")
            elif isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_sanitize(v) for v in obj]
            return obj

        sanitized_content = _sanitize(content)
        return json.dumps(
            sanitized_content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8", "replace")


# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Enterprise-grade Multilingual Voice-First Revenue Services Platform. "
        "Supports Income, Caste, OBC-NCL, and Domicile certificate applications "
        "with omnichannel continuity, Data Guard trust boundary, and full audit trail."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=SafeJSONResponse,
    lifespan=lifespan,
)

# ── Middleware ──
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SecurityMiddleware)         # ← Phase 14: rate limiting + security headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ──
PREFIX = settings.API_V1_PREFIX

app.include_router(auth.router, prefix=PREFIX)
app.include_router(conversation.router, prefix=PREFIX)
app.include_router(applications.router, prefix=PREFIX)
app.include_router(dashboard.router, prefix=PREFIX)
app.include_router(data_guard.router, prefix=PREFIX)

# ── NEW Omnichannel Routes ──
app.include_router(whatsapp.router, prefix=PREFIX)   # WhatsApp Clone UI
app.include_router(ivr.router, prefix=PREFIX)        # IVR Phone Simulator
app.include_router(tracking.router, prefix=PREFIX)   # Public Tracking Lookup
app.include_router(documents.router, prefix=PREFIX)  # Documents + fields + resolve

# ── Phase 11-12 Routes ──
app.include_router(payment.router, prefix=PREFIX)    # Payment initiate + receipt verify
app.include_router(stream.router, prefix=PREFIX)     # SSE real-time events

# ── Phase 8: Mock Government Adapter ──
try:
    from app.api.routes import mock_government
    app.include_router(mock_government.router, prefix=PREFIX)
except ImportError:
    pass  # Created in Phase 8

# ── Static Files Mount ──
app.mount("/data", StaticFiles(directory="data"), name="data")



# ── Root / Health ──

@app.get("/", tags=["health"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


@app.get("/health", tags=["health"])
def health_check():
    return {
        "status": "healthy",
        "database": "sqlite",
        "data_guard": "active",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


# ── Global Error Handlers ──

def _cors_headers(request: Request) -> dict:
    origin = request.headers.get("origin") or "*"
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*",
    }


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Phase 15: Consistent JSON error shape for all HTTP errors (404, 400, 403, etc.).
    Adds request_id for traceability.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    return SafeJSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "request_id": request_id,
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Phase 15: Return readable validation errors with field paths.
    Prevents confusing 422 payloads being silently swallowed by frontend.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err["loc"])
        errors.append({"field": field, "message": err["msg"], "type": err["type"]})
    logger.warning(f"Validation error [{request_id}]: {errors}")
    return SafeJSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "errors": errors,
            "request_id": request_id,
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(LLMUnavailableError)
async def llm_unavailable_handler(request: Request, exc):
    """Return 503 when LLM provider is unreachable. NEVER fall back silently."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    logger.warning(f"LLM unavailable [{request_id}]: {exc}")
    return SafeJSONResponse(
        status_code=503,
        content={
            "detail": "AI service is temporarily unavailable. Please try again in a moment.",
            "request_id": request_id,
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    logger.error(f"Unhandled error [{request_id}]: {exc}", exc_info=True)
    return SafeJSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {str(exc)}",
            "type": type(exc).__name__,
            "request_id": request_id,
        },
        headers=_cors_headers(request),
    )


# ── LLM Health Check ──
@app.get("/api/v1/health/llm", tags=["health"])
def llm_health():
    """Check LLM provider health. Returns provider name and model. Does NOT expose API key."""
    try:
        from app.llm.provider_factory import get_provider
        p = get_provider()
        return {
            "status": "ok",
            "provider": p.provider_name,
            "model": p.model_name,
            "reachable": True,
        }
    except Exception as e:
        return {
            "status": "error",
            "provider": settings.LLM_PROVIDER,
            "reachable": False,
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
