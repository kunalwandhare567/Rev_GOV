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
    from_number: Optional[str] = None
    citizen_identifier: Optional[str] = None
    message_type: str = "text"   # text | audio | image | document
    text: Optional[str] = None
    message: Optional[str] = None
    language: Optional[str] = None


class WhatsAppMessageResponse(BaseModel):
    reply_text: str = ""
    response: Optional[str] = None
    reply_audio_url: Optional[str] = None
    options: list = []
    tracking_id: Optional[str] = None
    application_id: Optional[str] = None
    session_id: Optional[str] = None
    session_node: Optional[str] = None
    current_node: Optional[str] = None
    consent_given: Optional[bool] = None
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
    req_dict = request.dict()
    if not req_dict.get("from_number") and req_dict.get("citizen_identifier"):
        req_dict["from_number"] = req_dict["citizen_identifier"]
    if not req_dict.get("text") and req_dict.get("message"):
        req_dict["text"] = req_dict["message"]
    channel_msg = _adapter.normalize_inbound(req_dict)

    # 1. Resolve citizen
    from_num = request.from_number or request.citizen_identifier or req_dict.get("from_number") or "unknown"
    resolver = CitizenResolver(db)
    citizen = resolver.create_or_resolve_whatsapp(
        from_num,
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

    reply_text = result.get("response", "")
    return WhatsAppMessageResponse(
        reply_text=reply_text,
        response=reply_text,
        reply_audio_url=result.get("reply_audio_url"),
        options=result.get("options", []),
        tracking_id=result.get("tracking_id"),
        application_id=result.get("application_id"),
        session_id=session.id,
        session_node=session.current_node,
        current_node=session.current_node,
        consent_given=session.consent_given,
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
    asyncio.create_task(_run_ocr_background(doc.id, application.id, citizen.citizen_ref))

    return {
        "document_id": doc.id,
        "status": "uploaded",
        "message": "✅ Document received! Verifying against your application details. I will notify you shortly.",
        "tracking_id": application.tracking_id,
    }


async def _run_ocr_background(doc_id: str, application_id: str, citizen_ref: str = None, _=None):
    """
    Run OCR + field matching in background with an independent DB session.
    Posts a structured mismatch message into the citizen's WhatsApp conversation.
    Uses GeminiDialogueService for natural language output when available.
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
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

        # Mark processing started
        doc_repo.update_status(doc_id, "OCR_PROCESSING")

        # Run OCR (Gemini Vision → Tesseract → mock)
        ocr_svc = OCRService()
        ocr_result = ocr_svc.run_ocr(doc.file_ref, doc.doc_type)
        doc_repo.update_ocr_result(doc_id, ocr_result.extracted_fields, ocr_result.confidence)

        logger.info(
            f"WhatsApp OCR complete for doc {doc_id}: "
            f"provider={ocr_result.provider}, "
            f"fields={list(ocr_result.extracted_fields.keys())}, "
            f"confidence={ocr_result.confidence:.2f}"
        )

        # Auto-detect and update doc type if it was UNKNOWN
        if doc.doc_type == "UNKNOWN" and ocr_result.doc_type_detected not in ("UNKNOWN", None):
            doc_repo.update_doc_type(doc_id, ocr_result.doc_type_detected)
            doc.doc_type = ocr_result.doc_type_detected

        # Match against application-declared fields
        app_fields = app_repo.get_fields(application_id)
        matcher = MatchingService()
        match_result = matcher.compare_document(
            app_fields, ocr_result.extracted_fields, doc_type=doc.doc_type
        )

        # Determine status
        if match_result.mismatched_fields:
            status = "MISMATCH"
        elif match_result.overall_score == 0.0 and not match_result.matched_fields:
            status = "INCOMPLETE"
        else:
            status = "VERIFIED"

        # Update document record
        doc_repo.update_document_verification(doc_id, status, match_result.mismatched_fields)
        doc_repo.update_match_scores(
            doc_id, match_result.field_scores,
            match_result.overall_score, match_result.mismatched_fields
        )

        # Post notification into WhatsApp conversation
        if citizen_ref:
            from app.models.db_models import ConversationSession
            session = (
                db.query(ConversationSession)
                .filter(
                    ConversationSession.citizen_ref == citizen_ref,
                    ConversationSession.channel == "WHATSAPP",
                )
                .order_by(ConversationSession.updated_at.desc())
                .first()
            )

            if session:
                lang = session.language or "en"

                if status == "INCOMPLETE":
                    notify_msgs = {
                        "en": (
                            f"📄 Your document has been received.\n"
                            f"⚠️ I couldn't extract text from it — please ensure the image is clear.\n"
                            f"OCR engine used: {ocr_result.provider}"
                        ),
                        "hi": (
                            f"📄 आपका दस्तावेज़ प्राप्त हो गया।\n"
                            f"⚠️ दस्तावेज़ से टेक्स्ट निकालना संभव नहीं हुआ। कृपया स्पष्ट छवि भेजें।"
                        ),
                        "mr": (
                            f"📄 तुमचे कागदपत्र मिळाले.\n"
                            f"⚠️ कागदपत्रातून मजकूर काढता आला नाही. स्पष्ट प्रतिमा पाठवा."
                        ),
                    }
                    msg = notify_msgs.get(lang, notify_msgs["en"])

                elif status == "VERIFIED":
                    msg = matcher._all_match_message(match_result, lang)

                else:
                    # MISMATCH — use Gemini-powered message generation
                    msg = matcher.generate_mismatch_message(
                        match_result, language=lang, use_gemini=True
                    )
                    # Append fields-not-found-in-doc notice
                    if match_result.fields_only_in_app:
                        fnd = ", ".join(
                            f.replace("_", " ").title()
                            for f in match_result.fields_only_in_app
                        )
                        suffixes = {
                            "en": f"\n\n❓ These fields were not found in your document: {fnd}",
                            "hi": f"\n\n❓ ये फ़ील्ड दस्तावेज़ में नहीं मिले: {fnd}",
                            "mr": f"\n\n❓ हे तपशील कागदपत्रात आढळले नाहीत: {fnd}",
                        }
                        msg += suffixes.get(lang, suffixes["en"])

                    # If auto-detecetd a doc type, prepend that info
                    if doc.doc_type and doc.doc_type != "UNKNOWN":
                        type_notice = {
                            "en": f"📋 I detected this as: **{doc.doc_type.replace('_', ' ').title()}**\n\n",
                            "hi": f"📋 मैंने इसे पहचाना: **{doc.doc_type.replace('_', ' ')}**\n\n",
                            "mr": f"📋 मी हे ओळखले: **{doc.doc_type.replace('_', ' ')}**\n\n",
                        }
                        msg = type_notice.get(lang, type_notice["en"]) + msg

                _save_message(session.id, "ASSISTANT", msg, db)
                logger.info(
                    f"WhatsApp: OCR notification posted for citizen {citizen_ref}, "
                    f"status={status}, mismatches={match_result.mismatched_fields}"
                )

    except Exception as e:
        logger.error(f"OCR background task error for doc {doc_id}: {e}", exc_info=True)
    finally:
        db.close()



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

