"""
WhatsApp Simulator Route
POST /api/v1/whatsapp/message  → process message from WhatsApp Clone UI
GET  /api/v1/whatsapp/history  → get conversation history for UI
POST /api/v1/whatsapp/voice    → process voice note (triggers STT)
POST /api/v1/whatsapp/upload   → upload document
"""
import os
import uuid
import shutil
import logging
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.channels.base import Channel, EventType
from app.channels.whatsapp.adapter import WhatsAppAdapter
from app.services.citizen_resolver import CitizenResolver
from app.services.stt_service import STTService
from app.services.notification_service import NotificationService
from app.services.language_service import language_service     # Phase 4+6
from app.services.i18n import get_template                      # Phase 6
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.event_repo import EventRepository
from app.data_layer.repositories.document_repo import DocumentRepository
from app.models.db_models import ConversationMessage, ConversationSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

_adapter = WhatsAppAdapter()
_stt = STTService()



class WhatsAppMessageRequest(BaseModel):
    from_number: str
    message_type: str = "text"   # text | audio | image | document
    text: Optional[str] = None
    language: Optional[str] = None


class WhatsAppMessageResponse(BaseModel):
    reply_text: str
    reply_audio_url: Optional[str] = None
    options: list = []
    tracking_id: Optional[str] = None
    application_id: Optional[str] = None
    session_node: Optional[str] = None
    language: str = "en"


@router.post("/message", response_model=WhatsAppMessageResponse)
async def receive_message(
    request: WhatsAppMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Main WhatsApp message handler.
    Phase 6: Auto-detects language on first message.
    """
    channel_msg = _adapter.normalize_inbound(request.dict())

    # 1. Resolve citizen
    resolver = CitizenResolver(db)
    citizen = resolver.create_or_resolve_whatsapp(
        request.from_number,
        language=request.language or "en"
    )

    # 2. Phase 6: Auto-detect language from message content
    incoming_text = channel_msg.text_content or ""
    if incoming_text and len(incoming_text) > 3:
        detected_lang = language_service.detect_language(
            incoming_text, fallback=citizen.preferred_language
        )
        if detected_lang != citizen.preferred_language:
            from app.data_layer.repositories.citizen_repo import CitizenRepository
            CitizenRepository(db).update_language(citizen.citizen_ref, detected_lang)
            citizen.preferred_language = detected_lang

    lang = citizen.preferred_language or "en"

    # 3. Get or create conversation session
    session = _get_or_create_session(citizen.citizen_ref, db)

    # 4. Get active application
    app_repo = ApplicationRepository(db)
    application = app_repo.get_active_for_citizen(citizen.citizen_ref)

    # 5. Process through orchestrator
    from app.orchestration.state_machine.orchestrator import ConversationOrchestrator
    orchestrator = ConversationOrchestrator(db)

    result = orchestrator.process_message(
        citizen_ref=citizen.citizen_ref,
        text=incoming_text,
        channel=Channel.WHATSAPP.value,
        language=lang,
    )

    # 6. Update last channel on application
    if result.get("application_id"):
        app_repo.update_last_channel(result["application_id"], Channel.WHATSAPP.value)

    return WhatsAppMessageResponse(
        reply_text=result.get("response", ""),
        options=result.get("options", []),
        tracking_id=result.get("tracking_id"),
        application_id=result.get("application_id"),
        session_node=session.current_node,
        language=lang,
    )



@router.post("/voice")
async def receive_voice(
    from_number: str = Form(...),
    language: str = Form(default="en"),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Process voice note from WhatsApp Clone UI.
    1. Save audio file
    2. STT transcription (Whisper)
    3. Process as text message
    """
    os.makedirs("data/audio", exist_ok=True)
    ext = audio_file.filename.rsplit(".", 1)[-1] if audio_file.filename else "wav"
    audio_path = f"data/audio/wa_{uuid.uuid4().hex}.{ext}"

    with open(audio_path, "wb") as f:
        shutil.copyfileobj(audio_file.file, f)

    # STT
    wav_path = _stt.convert_to_wav(audio_path)
    stt_result = _stt.transcribe(wav_path, language=language)
    transcribed_text = stt_result.text
    detected_language = stt_result.detected_language or language

    # Process as text
    resolver = CitizenResolver(db)
    citizen = resolver.create_or_resolve_whatsapp(from_number, language=detected_language)
    session = _get_or_create_session(citizen.citizen_ref, db)

    from app.orchestration.state_machine.orchestrator import ConversationOrchestrator
    orchestrator = ConversationOrchestrator(db)
    result = orchestrator.process_message(
        citizen_ref=citizen.citizen_ref,
        text=transcribed_text,
        channel=Channel.WHATSAPP.value,
        language=detected_language,
    )


    return {
        "transcribed_text": transcribed_text,
        "detected_language": detected_language,
        "reply_text": result.get("response", ""),
        "options": result.get("options", []),
        "tracking_id": result.get("tracking_id"),
    }


@router.post("/upload")
async def upload_document(
    from_number: str = Form(...),
    doc_type: str = Form(default="UNKNOWN"),
    application_id: str = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Document upload from WhatsApp Clone UI.
    Saves file, creates Document record, triggers OCR background task.
    """
    resolver = CitizenResolver(db)
    citizen = resolver.create_or_resolve_whatsapp(from_number)

    app_repo = ApplicationRepository(db)
    if application_id:
        application = app_repo.get_by_id(application_id)
    else:
        application = app_repo.get_active_for_citizen(citizen.citizen_ref)

    if not application:
        return {"error": "No active application found. Please start an application first."}

    # Save file
    upload_dir = f"data/uploads/{application.id}"
    os.makedirs(upload_dir, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "pdf"
    file_path = f"{upload_dir}/wa_{uuid.uuid4().hex}.{ext}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create document record
    doc_repo = DocumentRepository(db)
    doc = doc_repo.create(
        application_id=application.id,
        doc_type=doc_type,
        file_ref=file_path,
        upload_channel="WHATSAPP",
    )

    # Emit DOCUMENT_UPLOADED event
    event_repo = EventRepository(db)
    event_repo.create_event(
        application_id=application.id,
        citizen_ref=citizen.citizen_ref,
        event_type=EventType.DOCUMENT_UPLOADED.value,
        source_channel="WHATSAPP",
        event_data={"document_id": doc.id, "doc_type": doc_type},
    )

    # Run OCR in background (async)
    import asyncio
    asyncio.create_task(_run_ocr_background(doc.id, application.id, application_id, db))

    return {
        "document_id": doc.id,
        "status": "uploaded",
        "message": "✅ Document received! Verifying against your application details. I will notify you shortly.",
        "tracking_id": application.tracking_id,
    }


async def _run_ocr_background(doc_id: str, application_id: str, _, db: Session):
    """Run OCR + matching in background."""
    try:
        from app.services.ocr_service import OCRService
        from app.services.matching_service import MatchingService
        from app.data_layer.repositories.document_repo import DocumentRepository
        from app.data_layer.repositories.application_repo import ApplicationRepository

        doc_repo = DocumentRepository(db)
        app_repo = ApplicationRepository(db)

        doc = doc_repo.get(doc_id)
        if not doc:
            return

        # OCR
        doc_repo.update_status(doc_id, "OCR_PROCESSING")
        ocr_svc = OCRService()
        ocr_result = ocr_svc.run_ocr(doc.file_ref, doc.doc_type)
        doc_repo.update_ocr_result(doc_id, ocr_result.extracted_fields, ocr_result.confidence)

        # Auto-detect doc type
        if doc.doc_type == "UNKNOWN" and ocr_result.doc_type_detected != "UNKNOWN":
            doc = doc_repo.update_status(doc_id, "VALIDATING")

        # Match against application fields
        app_fields = app_repo.get_fields(application_id)
        matcher = MatchingService()
        match_result = matcher.compare_document(app_fields, ocr_result.extracted_fields)

        doc_repo.update_match_scores(
            doc_id, match_result.field_scores,
            match_result.overall_score, match_result.mismatched_fields
        )

    except Exception as e:
        logger.error(f"OCR background task error: {e}")


@router.get("/history/{from_number}")
async def get_history(from_number: str, db: Session = Depends(get_db)):
    """Get conversation history for WhatsApp Clone UI."""
    resolver = CitizenResolver(db)
    citizen = resolver.resolve(whatsapp_number=from_number)
    if not citizen:
        return {"messages": []}

    session = (
        db.query(ConversationSession)
        .filter(ConversationSession.citizen_ref == citizen.citizen_ref)
        .order_by(ConversationSession.updated_at.desc())
        .first()
    )
    if not session:
        return {"messages": []}

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.session_id == session.id)
        .order_by(ConversationMessage.created_at)
        .all()
    )

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "modality": m.modality,
                "audio_ref": m.audio_ref,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "session_node": session.current_node,
        "language": session.language,
        "application_id": session.application_id,
    }


def _get_or_create_session(citizen_ref: str, db: Session) -> ConversationSession:
    """Get or create conversation session for citizen."""
    session = (
        db.query(ConversationSession)
        .filter(ConversationSession.citizen_ref == citizen_ref,
                ConversationSession.channel == "WHATSAPP")
        .order_by(ConversationSession.updated_at.desc())
        .first()
    )
    if not session:
        session = ConversationSession(
            citizen_ref=citizen_ref,
            channel="WHATSAPP",
            current_node="INIT",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def _save_message(session_id: str, role: str, content: str, db: Session) -> None:
    msg = ConversationMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    db.commit()


# ── Officer → Citizen Notification Endpoint (Phase 13) ────────────────────

class NotifyRequest(BaseModel):
    application_number: str
    event_type: str = "STATUS_CHANGED"
    new_status: str = ""
    custom_message: Optional[str] = None


@router.post("/notify")
def notify_citizen(body: NotifyRequest, db: Session = Depends(get_db)):
    """
    Officer-triggered notification to citizen via WhatsApp (simulator).
    Phase 13: Called by OfficerReview 'Notify Citizen' button.
    """
    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_number(body.application_number)
    if not app:
        return {"success": False, "error": "Application not found"}

    # Get citizen language preference
    from app.data_layer.repositories.citizen_repo import CitizenRepository
    citizen = CitizenRepository(db).get_by_ref(app.citizen_ref)
    lang = citizen.preferred_language if citizen else "en"

    # Build notification message
    if body.custom_message:
        message = body.custom_message
    else:
        status_details = {
            "UNDER_REVIEW": "An officer has started reviewing your application.",
            "APPROVED": "🎉 Your application has been APPROVED! Certificate will be ready soon.",
            "REJECTED": "Your application has been reviewed. Please check the portal for details.",
            "ESCALATED": "Your application has been escalated to a senior officer for review.",
            "CERTIFICATE_READY": "📜 Your certificate is ready! Download from the web portal.",
        }
        details = status_details.get(body.new_status, f"Status updated to {body.new_status}")
        message = get_template(
            "status_update", lang,
            tracking_id=app.tracking_id or body.application_number,
            status=body.new_status,
            details=details,
        )

    # Log as a system message in the conversation
    from app.models.db_models import ConversationSession
    session = (
        db.query(ConversationSession)
        .filter(ConversationSession.citizen_ref == app.citizen_ref,
                ConversationSession.channel == "WHATSAPP")
        .order_by(ConversationSession.updated_at.desc())
        .first()
    )
    if session:
        _save_message(session.id, "SYSTEM", f"📲 [Notification] {message}", db)

    logger.info(f"Officer notification sent for {body.application_number}: {body.new_status}")
    return {
        "success": True,
        "message_sent": message,
        "language": lang,
        "tracking_id": app.tracking_id,
    }

