"""
Rate limiting + Security middleware — Phase 14
- Rate limiting per IP for WhatsApp simulator and document upload routes
- Request size limiting
- Security headers injection
- Ownership verification helper
"""
import time
import logging
from collections import defaultdict, deque
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ── Simple In-Memory Rate Limiter ──────────────────────────────────────────

class RateLimiter:
    """
    Token-bucket style rate limiter using a sliding window.
    Stores request timestamps per (IP, route_prefix).
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window = self._windows[key]

        # Evict old entries outside the window
        while window and window[0] < now - self.window_seconds:
            window.popleft()

        if len(window) >= self.max_requests:
            return False

        window.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.time()
        window = self._windows[key]
        active = sum(1 for t in window if t >= now - self.window_seconds)
        return max(0, self.max_requests - active)


# Route-specific limiters
_whatsapp_limiter = RateLimiter(max_requests=60, window_seconds=60)   # 60 msgs/min
_upload_limiter   = RateLimiter(max_requests=20, window_seconds=60)   # 20 uploads/min
_ivr_limiter      = RateLimiter(max_requests=30, window_seconds=60)   # 30 calls/min
_tracking_limiter = RateLimiter(max_requests=100, window_seconds=60)  # 100 lookups/min


RATE_LIMIT_ROUTES = {
    "/api/v1/whatsapp/": _whatsapp_limiter,
    "/api/v1/ivr/":      _ivr_limiter,
    "/api/v1/tracking/": _tracking_limiter,
}

UPLOAD_ROUTE_PREFIXES = [
    "/api/v1/whatsapp/upload",
    "/api/v1/payment/verify-receipt",
    "/api/v1/documents/upload",
]


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Applies:
      1. Rate limiting for channel simulator routes
      2. Security response headers (HSTS, XSS, etc.)
      3. Max request body size for non-upload routes
    """

    MAX_BODY_SIZE = 10 * 1024 * 1024   # 10 MB
    MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB for uploads

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # ── 1. Rate Limiting ──
        for prefix, limiter in RATE_LIMIT_ROUTES.items():
            if path.startswith(prefix):
                key = f"{client_ip}:{prefix}"
                if not limiter.is_allowed(key):
                    logger.warning(f"Rate limit exceeded: {client_ip} → {path}")
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limit_exceeded",
                            "message": "Too many requests. Please slow down.",
                            "retry_after": 60,
                        },
                        headers={"Retry-After": "60"},
                    )

        # ── 2. Upload size guard ──
        content_length = request.headers.get("content-length")
        is_upload = any(path.startswith(p) for p in UPLOAD_ROUTE_PREFIXES)
        max_size = self.MAX_UPLOAD_SIZE if is_upload else self.MAX_BODY_SIZE

        if content_length and int(content_length) > max_size:
            return JSONResponse(
                status_code=413,
                content={"error": "payload_too_large", "max_size_mb": max_size // (1024 * 1024)},
            )

        # ── 3. Process request ──
        response = await call_next(request)

        # ── 4. Add security headers ──
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(self), camera=()"
        # Note: HSTS only in production (not on localhost)
        if "localhost" not in (request.headers.get("host") or ""):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# ── Ownership Verification ────────────────────────────────────────────────

def verify_application_ownership(
    application_id: str,
    citizen_ref: Optional[str],
    db,
) -> None:
    """
    Raise HTTP 403 if citizen_ref doesn't own this application.
    Used as a dependency in officer/citizen-facing endpoints.
    Skip if citizen_ref is None (officer access, already auth-guarded).
    """
    if citizen_ref is None:
        return  # Officer / admin — skip ownership check

    from app.data_layer.repositories.application_repo import ApplicationRepository
    repo = ApplicationRepository(db)
    app = repo.get_by_id(application_id) or repo.get_by_number(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.citizen_ref != citizen_ref:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this application",
        )


# ── Tracking ID PII Guard ─────────────────────────────────────────────────

def sanitize_tracking_response(app_data: dict) -> dict:
    """
    Remove PII fields from public tracking endpoint responses.
    Tracking ID should expose status only, never citizen identity.
    """
    SAFE_FIELDS = {
        "tracking_id", "application_number", "service_id", "service_name",
        "status", "current_step", "progress_percent",
        "channel_origin", "last_channel",
        "created_at", "submitted_at", "completed_at",
        "payment_status",
        "sla_days",
        "timeline",
    }
    return {k: v for k, v in app_data.items() if k in SAFE_FIELDS}


# ── Admin Auth Dependency ─────────────────────────────────────────────────

def require_admin(request: Request):
    """
    FastAPI dependency: validates admin Bearer token.
    In POC mode: accepts any non-empty token OR the ADMIN_SECRET env var.
    In production: replace with JWT validation.
    """
    import os
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else ""

    # POC mode: accept any token (can be tightened later)
    admin_secret = os.getenv("ADMIN_SECRET_KEY", "")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Admin authentication required. Include Authorization: Bearer <token> header.",
        )

    if admin_secret and token != admin_secret:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin token.",
        )

    return {"role": "ADMIN", "token": token}
