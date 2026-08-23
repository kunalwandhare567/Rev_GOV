"""
Main FastAPI Application
Entry point for the Multilingual Voice-First Revenue Services Platform backend.
"""
import os
import sys
import logging
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# Force UTF-8 on Windows to avoid cp1252 emoji encoding errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes import conversation, applications, dashboard, data_guard, auth

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
    for path in [settings.STORAGE_PATH, settings.RECEIPT_PATH, settings.CERTIFICATE_PATH, settings.AUDIO_PATH]:
        os.makedirs(path, exist_ok=True)
    logger.info("✅ Storage directories ready")

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

        # Seed officer user
        if not db.query(User).filter(User.username == settings.OFFICER_USERNAME).first():
            db.add(User(
                username=settings.OFFICER_USERNAME,
                hashed_password=pwd_ctx.hash(settings.OFFICER_PASSWORD),
                role="OFFICER",
            ))
            logger.info(f"✅ Officer user created: {settings.OFFICER_USERNAME}")

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
    lifespan=lifespan,
)

# ── Middleware ──
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
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


# ── Global Error Handler ──

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
