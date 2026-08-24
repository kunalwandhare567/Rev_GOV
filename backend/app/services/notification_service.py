"""
Notification Service — sends in-app and simulated WhatsApp notifications.
For demo: notifications are stored in ApplicationEvent and shown in WhatsApp UI.
For production: replace _send_whatsapp() with Meta Graph API call.
"""
import logging
from sqlalchemy.orm import Session
from app.channels.base import EventType

logger = logging.getLogger(__name__)


NOTIFICATION_TEMPLATES = {
    EventType.APPLICATION_CREATED: {
        "en": "✅ Application started!\n\nService: {service_name}\nTracking ID: {tracking_id}\n\nI will guide you through the process step by step.",
        "hi": "✅ आवेदन शुरू!\n\nसेवा: {service_name}\nट्रैकिंग ID: {tracking_id}\n\nमैं आपको चरण-दर-चरण मार्गदर्शन करूंगा।",
        "mr": "✅ अर्ज सुरू!\n\nसेवा: {service_name}\nट्रॅकिंग ID: {tracking_id}\n\nमी तुम्हाला प्रत्येक पायरीवर मार्गदर्शन करेन.",
    },
    EventType.READY_FOR_REVIEW: {
        "en": "🎯 Your application is ready for final review!\n\nTracking ID: {tracking_id}\n\nPlease open the Web Portal to review and submit:\n{review_url}",
        "hi": "🎯 आपका आवेदन अंतिम समीक्षा के लिए तैयार है!\n\nट्रैकिंग ID: {tracking_id}\n\nकृपया वेब पोर्टल खोलें:\n{review_url}",
        "mr": "🎯 तुमचा अर्ज अंतिम पुनरावलोकनासाठी तयार आहे!\n\nट्रॅकिंग ID: {tracking_id}\n\nकृपया वेब पोर्टल उघडा:\n{review_url}",
    },
    EventType.SUBMITTED_FOR_VERIFICATION: {
        "en": "✅ Your {service_name} application has been submitted for government verification.\n\nTracking ID: {tracking_id}\n\nWe will notify you when the status changes.",
        "hi": "✅ आपका {service_name} आवेदन सरकारी सत्यापन के लिए भेज दिया गया है।\n\nट्रैकिंग ID: {tracking_id}",
        "mr": "✅ तुमचा {service_name} अर्ज सरकारी सत्यापनासाठी पाठवण्यात आला आहे.\n\nट्रॅकिंग ID: {tracking_id}",
    },
    EventType.VERIFICATION_STATUS_CHANGED: {
        "en": "📋 Status Update: Your {service_name} application is now *{status}*.\n\nTracking ID: {tracking_id}",
        "hi": "📋 स्थिति अपडेट: आपका {service_name} आवेदन अब *{status}* है।\n\nट्रैकिंग ID: {tracking_id}",
        "mr": "📋 स्थिती अपडेट: तुमचा {service_name} अर्ज आता *{status}* आहे.\n\nट्रॅकिंग ID: {tracking_id}",
    },
    EventType.CLARIFICATION_REQUIRED: {
        "en": "⚠️ Additional information required for your application.\n\nTracking ID: {tracking_id}\n\nPlease upload the requested document here.",
        "hi": "⚠️ आपके आवेदन के लिए अतिरिक्त जानकारी आवश्यक है।\n\nट्रैकिंग ID: {tracking_id}",
        "mr": "⚠️ तुमच्या अर्जासाठी अतिरिक्त माहिती आवश्यक आहे.\n\nट्रॅकिंग ID: {tracking_id}",
    },
    EventType.APPROVED: {
        "en": "🎉 Good news! Your {service_name} application has been approved by the government.\n\nTracking ID: {tracking_id}\n\nYour application is now ready for payment.",
        "hi": "🎉 खुशखबरी! आपका {service_name} आवेदन सरकार द्वारा स्वीकृत हो गया है।\n\nट्रैकिंग ID: {tracking_id}",
        "mr": "🎉 आनंदाची बातमी! तुमचा {service_name} अर्ज सरकारने मंजूर केला आहे.\n\nट्रॅकिंग ID: {tracking_id}",
    },
    EventType.PAYMENT_REQUIRED: {
        "en": "💳 Payment required for your {service_name} application.\n\nAmount: ₹{amount}\nTracking ID: {tracking_id}\n\nPlease complete the payment to proceed.",
        "hi": "💳 आपके {service_name} आवेदन के लिए भुगतान आवश्यक है।\n\nराशि: ₹{amount}\nट्रैकिंग ID: {tracking_id}",
        "mr": "💳 तुमच्या {service_name} अर्जासाठी पेमेंट आवश्यक आहे.\n\nरक्कम: ₹{amount}\nट्रॅकिंग ID: {tracking_id}",
    },
    EventType.PAYMENT_COMPLETED: {
        "en": "✅ Payment confirmed for your {service_name} application.\n\nAmount Paid: ₹{amount}\nTracking ID: {tracking_id}\n\nFinal submission is being processed.",
        "hi": "✅ आपके {service_name} आवेदन का भुगतान पुष्टि हो गया।\n\nभुगतान: ₹{amount}\nट्रैकिंग ID: {tracking_id}",
        "mr": "✅ तुमच्या {service_name} अर्जाचे पेमेंट मंजूर झाले.\n\nरक्कम: ₹{amount}\nट्रॅकिंग ID: {tracking_id}",
    },
    EventType.APPLICATION_COMPLETED: {
        "en": "🏛️ Your {service_name} application has been successfully completed!\n\nTracking ID: {tracking_id}\n\nYou can download your certificate from the Web Portal.",
        "hi": "🏛️ आपका {service_name} आवेदन सफलतापूर्वक पूरा हो गया है!\n\nट्रैकिंग ID: {tracking_id}",
        "mr": "🏛️ तुमचा {service_name} अर्ज यशस्वीरित्या पूर्ण झाला आहे!\n\nट्रॅकिंग ID: {tracking_id}",
    },
}


class NotificationService:
    """
    Sends notifications when application events occur.
    Primary channel: WhatsApp Chat Simulator (in-app notification).
    Also stores in ApplicationEvent for cross-channel display.
    """

    def __init__(self, db: Session):
        self.db = db

    def send_event_notification(self, event_type: str, application,
                                extra_data: dict = None) -> bool:
        """
        Send notification for an application event.
        Finds citizen's preferred channel and sends accordingly.
        """
        extra = extra_data or {}
        language = application.language or "en"
        service_name = application.service.name_en if application.service else "Certificate"

        template_key = None
        for et in EventType:
            if et.value == event_type:
                template_key = et
                break

        if not template_key:
            return False

        templates = NOTIFICATION_TEMPLATES.get(template_key, {})
        template = templates.get(language, templates.get("en", ""))

        if not template:
            return False

        message = template.format(
            service_name=service_name,
            tracking_id=application.tracking_id or "N/A",
            status=application.status,
            review_url=f"http://localhost:5173/applications/{application.id}/review",
            amount=extra.get("amount", "0"),
        )

        # Store notification for WhatsApp UI to display
        self._store_notification(application.id, application.citizen_ref,
                                 event_type, message)

        # Log (in production: send via Meta API)
        logger.info(f"[NOTIFICATION] → {application.citizen_ref}: {message[:100]}...")
        return True

    def _store_notification(self, application_id: str, citizen_ref: str,
                            event_type: str, message: str) -> None:
        """Store notification as a conversation message for WhatsApp UI display."""
        from app.models.db_models import ConversationSession, ConversationMessage
        session = (
            self.db.query(ConversationSession)
            .filter(
                ConversationSession.citizen_ref == citizen_ref,
                ConversationSession.application_id == application_id,
            )
            .order_by(ConversationSession.updated_at.desc())
            .first()
        )
        if session:
            msg = ConversationMessage(
                session_id=session.id,
                role="ASSISTANT",
                content=message,
                modality="TEXT",
                classification="NON_SENSITIVE",
            )
            self.db.add(msg)
            self.db.commit()

    def get_notification_message(self, event_type: str, application,
                                 language: str = "en", extra: dict = None) -> str:
        """Get formatted notification message without sending."""
        extra = extra or {}
        for et in EventType:
            if et.value == event_type:
                templates = NOTIFICATION_TEMPLATES.get(et, {})
                template = templates.get(language, templates.get("en", ""))
                if template:
                    return template.format(
                        service_name=application.service.name_en if application.service else "",
                        tracking_id=application.tracking_id or "N/A",
                        status=application.status,
                        review_url=f"http://localhost:5173/applications/{application.id}/review",
                        amount=extra.get("amount", "0"),
                    )
        return ""
