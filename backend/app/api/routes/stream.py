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
