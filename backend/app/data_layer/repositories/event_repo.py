"""
Application Event Repository
"""
from sqlalchemy.orm import Session
from app.models.db_models import ApplicationEvent
import datetime


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_event(self, application_id: str, citizen_ref: str,
                     event_type: str, source_channel: str,
                     event_data: dict = None) -> ApplicationEvent:
        ev = ApplicationEvent(
            application_id=application_id,
            citizen_ref=citizen_ref,
            event_type=event_type,
            source_channel=source_channel,
            event_data=event_data or {},
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)
        return ev

    def get_pending_notifications(self, limit: int = 50) -> list[ApplicationEvent]:
        return (
            self.db.query(ApplicationEvent)
            .filter(ApplicationEvent.notification_sent == False)
            .order_by(ApplicationEvent.created_at)
            .limit(limit)
            .all()
        )

    def mark_notification_sent(self, event_id: str, channel: str) -> None:
        ev = self.db.query(ApplicationEvent).filter(ApplicationEvent.id == event_id).first()
        if ev:
            ev.notification_sent = True
            ev.notification_channel = channel
            self.db.commit()

    def mark_notification_error(self, event_id: str, error: str) -> None:
        ev = self.db.query(ApplicationEvent).filter(ApplicationEvent.id == event_id).first()
        if ev:
            ev.notification_error = error
            self.db.commit()

    def get_for_application(self, application_id: str) -> list[ApplicationEvent]:
        return (
            self.db.query(ApplicationEvent)
            .filter(ApplicationEvent.application_id == application_id)
            .order_by(ApplicationEvent.created_at)
            .all()
        )

    def get_new_events(self, application_id: str, since: datetime.datetime) -> list[ApplicationEvent]:
        return (
            self.db.query(ApplicationEvent)
            .filter(
                ApplicationEvent.application_id == application_id,
                ApplicationEvent.created_at > since,
            )
            .order_by(ApplicationEvent.created_at)
            .all()
        )
