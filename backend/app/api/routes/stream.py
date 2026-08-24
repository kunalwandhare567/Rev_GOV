"""
SSE (Server-Sent Events) + EventBus — Phase 12
Real-time application updates pushed to frontend.

Endpoints:
  GET /api/v1/stream/applications/{application_id}/events
  GET /api/v1/stream/health
"""
import asyncio
import json
import logging
import datetime
from typing import AsyncGenerator, Dict, Set
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.data_layer.repositories.event_repo import EventRepository
from app.data_layer.repositories.application_repo import ApplicationRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stream", tags=["sse"])


# ── In-Memory EventBus ─────────────────────────────────────────────────────
# For production: replace with Redis pub/sub or RabbitMQ

class EventBus:
    """Simple in-process pub/sub bus for application events."""

    def __init__(self):
        # application_id → set of asyncio.Queue for each connected SSE client
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, application_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.setdefault(application_id, set()).add(q)
        return q

    def unsubscribe(self, application_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(application_id, set())
        subs.discard(q)
        if not subs:
            self._subscribers.pop(application_id, None)

    async def publish(self, application_id: str, event: dict) -> None:
        """Publish event to all subscribers for this application."""
        for q in list(self._subscribers.get(application_id, set())):
            try:
                await q.put(event)
            except asyncio.QueueFull:
                logger.warning(f"SSE queue full for {application_id}, dropping event")

    def publish_sync(self, application_id: str, event: dict) -> None:
        """Synchronous publish — use from non-async context (routes, services)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.publish(application_id, event))
            else:
                loop.run_until_complete(self.publish(application_id, event))
        except Exception as exc:
            logger.warning(f"EventBus.publish_sync failed: {exc}")

    def subscriber_count(self, application_id: str) -> int:
        return len(self._subscribers.get(application_id, set()))


# Singleton bus — imported by routes and services
bus = EventBus()


# ── SSE Endpoints ─────────────────────────────────────────────────────────

async def _event_generator(
    request: Request,
    application_id: str,
    q: asyncio.Queue,
    db: Session,
) -> AsyncGenerator[str, None]:
    """Generate SSE text/event-stream data."""
    app_repo = ApplicationRepository(db)
    event_repo = EventRepository(db)

    # Send current state immediately on connect
    app = app_repo.get_by_id(application_id)
    if app:
        yield _format_event("connected", {
            "application_id": application_id,
            "tracking_id": app.tracking_id,
            "status": app.status,
            "progress": app.progress_percent or 0,
            "channel": app.last_channel or app.channel_origin,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        })

    # Stream incoming events
    try:
        while True:
            # Check client disconnect
            if await request.is_disconnected():
                break

            try:
                event = await asyncio.wait_for(q.get(), timeout=20.0)
                yield _format_event(event.get("type", "update"), event)
            except asyncio.TimeoutError:
                # Send heartbeat keep-alive every 20 seconds
                yield _format_event("heartbeat", {"ts": datetime.datetime.utcnow().isoformat()})

    except asyncio.CancelledError:
        pass
    finally:
        logger.debug(f"SSE client disconnected: {application_id}")


def _format_event(event_type: str, data: dict) -> str:
    """Format a single SSE message."""
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.get("/applications/{application_id}/events")
async def application_events_stream(
    application_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    SSE endpoint for real-time application status updates.
    Frontend connects here and receives push updates when:
      - Application status changes
      - Document OCR completes
      - Mismatch detected/resolved
      - Payment completed
      - Officer acts on the application
    """
    q = bus.subscribe(application_id)

    async def cleanup_on_disconnect():
        await request.is_disconnected()
        bus.unsubscribe(application_id, q)

    return StreamingResponse(
        _event_generator(request, application_id, q, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/health")
def stream_health():
    """EventBus health check — show number of active SSE connections."""
    return {
        "status": "ok",
        "active_subscriptions": sum(
            len(v) for v in bus._subscribers.values()
        ),
        "watched_applications": len(bus._subscribers),
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


# ── Phase 13: Broadcast Helpers ────────────────────────────────────────────
# These are imported by mock_government.py and payment_service after decisions.

async def broadcast_status_change(
    tracking_id: str,
    new_status: str,
    extra: dict = None,
) -> None:
    """
    Phase 13 — Broadcast a status change to all clients subscribed to this
    tracking_id. Used by:
      - mock_government.py after APPROVE/REJECT/CLARIFICATION decision
      - payment_service after payment completes
      - certificate_service after certificate generation

    Publishes to both tracking_id AND application_id keys (two-way lookup).
    """
    event = {
        "type": "status_change",
        "tracking_id": tracking_id,
        "new_status": new_status,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        **(extra or {}),
    }
    await bus.publish(tracking_id, event)


def broadcast_status_change_sync(
    application_id: str,
    tracking_id: str,
    new_status: str,
    progress: int = 0,
    actor: str = "SYSTEM",
    extra: dict = None,
) -> None:
    """
    Phase 13 — Synchronous wrapper for broadcast (call from non-async context).
    Used from PaymentService, CertificateService, etc.
    """
    event = {
        "type": "status_change",
        "application_id": application_id,
        "tracking_id": tracking_id,
        "new_status": new_status,
        "progress": progress,
        "actor": actor,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        **(extra or {}),
    }
    # Publish to both application_id and tracking_id channels
    bus.publish_sync(application_id, event)
    if tracking_id and tracking_id != application_id:
        bus.publish_sync(tracking_id, event)


async def broadcast_notification(
    citizen_ref: str,
    message: str,
    notification_type: str = "INFO",
) -> None:
    """
    Phase 13 — Push a notification to a citizen's SSE channel.
    Frontend subscribes on citizen_ref key for non-application events.
    """
    event = {
        "type": "notification",
        "citizen_ref": citizen_ref,
        "message": message,
        "notification_type": notification_type,
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    await bus.publish(citizen_ref, event)


@router.get("/citizen/{citizen_ref}/events")
async def citizen_events_stream(
    citizen_ref: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Phase 13 — SSE stream for citizen-level notifications.
    Separate from application-level events — used for:
      - 'Your application has been approved'
      - 'Your certificate is ready'
      - 'Clarification required'
    Frontend subscribes on login with citizen_ref.
    """
    q = bus.subscribe(citizen_ref)

    return StreamingResponse(
        _citizen_event_generator(request, citizen_ref, q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _citizen_event_generator(
    request: Request,
    citizen_ref: str,
    q: asyncio.Queue,
) -> AsyncGenerator[str, None]:
    """Generate citizen-level SSE events."""
    yield _format_event("connected", {
        "citizen_ref": citizen_ref,
        "message": "Connected to notification stream",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    })

    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(q.get(), timeout=25.0)
                yield _format_event(event.get("type", "notification"), event)
            except asyncio.TimeoutError:
                yield _format_event("heartbeat", {"ts": datetime.datetime.utcnow().isoformat()})
    except asyncio.CancelledError:
        pass
    finally:
        bus.unsubscribe(citizen_ref, q)
        logger.debug(f"Citizen SSE disconnected: {citizen_ref}")
