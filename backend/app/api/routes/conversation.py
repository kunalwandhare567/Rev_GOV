"""
Conversation API Routes
Main citizen interaction endpoint: handles chat messages, document upload,
channel switching, and status queries.
"""
import os
import shutil
import logging
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.orchestration.state_machine.orchestrator import ConversationOrchestrator
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.rules_engine.engine import ServiceSpecLoader

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversation", tags=["conversation"])


# ── Request/Response Models ──

class MessageRequest(BaseModel):
    citizen_identifier: str        # Raw identifier (phone, email, user ID) — tokenized internally
    text: str
    channel: str = "WEB"          # WHATSAPP | IVR | WEB | MOBILE
    language: str = "en"
    modality: str = "TEXT"        # TEXT | VOICE | DTMF
    session_hint: Optional[str] = None


class ChannelSwitchRequest(BaseModel):
    citizen_identifier: str
    new_channel: str
    language: str = "en"


class ResolveMismatchRequest(BaseModel):
    citizen_identifier: str
    field_name: str
    resolution: str  # "use_document" or "use_declared"


class AdminDocDecisionRequest(BaseModel):
    application_id: str
    decision: str          # "APPROVE" or "REJECT"
    reason: Optional[str] = None
    admin_identifier: str = "admin"


# ── Endpoints ──

@router.post("/admin-doc-decision")
def admin_doc_decision(req: AdminDocDecisionRequest, db: Session = Depends(get_db)):
    """
    Admin pre-payment document decision endpoint.
    Called from the Admin Portal when reviewing documents in PENDING_OFFICER_PRE_APPROVAL state.
    - APPROVE → transitions app to PAYMENT_PENDING, notifies citizen to pay
    - REJECT  → transitions app to DOCUMENTS_REQUESTED, notifies citizen to re-upload
    """
    from app.data_layer.repositories.application_repo import ApplicationRepository
    from app.orchestration.state_machine.application_fsm import AppState, ApplicationFSM
    from app.data_layer.repositories.session_repo import SessionRepository
    from app.data_layer.repositories.audit_repo import AuditRepository

    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_id(req.application_id) or app_repo.get_by_number(req.application_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application '{req.application_id}' not found")

    decision = req.decision.upper()

    if decision == "APPROVE":
        new_status = AppState.PAYMENT_REQUIRED if hasattr(AppState, "PAYMENT_REQUIRED") else "PAYMENT_REQUIRED"
        app_repo.update_status(app.application_number, new_status)

        # Prepare citizen notification
        citizen_msg = (
            "✅ Document verification approved by Admin!\n\n"
            "💳 You can now proceed with your ₹50 payment.\n"
            "Type 'next' or 'pay now' in the chat to complete payment."
        )
        outcome = "APPROVED"

    elif decision == "REJECT":
        new_status = AppState.DOCUMENT_COLLECTION if hasattr(AppState, "DOCUMENT_COLLECTION") else "DOCUMENT_COLLECTION"
        app_repo.update_status(app.application_number, new_status)

        reason_text = req.reason or "Documents did not meet verification requirements"
        citizen_msg = (
            f"❌ Your documents were rejected by Admin.\n"
            f"Reason: {reason_text}\n\n"
            "Please re-upload corrected documents using the 📎 attachment button."
        )
        outcome = "REJECTED"
    else:
        raise HTTPException(status_code=400, detail="Decision must be 'APPROVE' or 'REJECT'")

    # Write audit log
    try:
        audit_repo = AuditRepository(db)
        audit_repo.write(
            event_type="ADMIN_DOC_DECISION",
            actor=req.admin_identifier,
            citizen_ref=app.citizen_ref,
            application_id=req.application_id,
            action=f"Admin {decision} documents for pre-payment verification",
            outcome=outcome,
            metadata={"reason": req.reason, "new_status": str(app.status)},
        )
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")

    # Store notification as a chat message (citizen sees it on next chat open)
    try:
        session_repo = SessionRepository(db)
        session = session_repo.load_session(app.citizen_ref)
        if session:
            if decision == "APPROVE":
                session.current_node = "PAYMENT"
                session.payment_status = "PENDING"
            elif decision == "REJECT":
                session.current_node = "DOCUMENT_UPLOAD"
            session_repo.save_session(session)
            session_repo.add_message(session.id, "ASSISTANT", citizen_msg)
            logger.info(f"Admin decision notification saved to citizen session {session.id}")
    except Exception as e:
        logger.warning(f"Could not store citizen notification: {e}", exc_info=True)

    return {
        "success": True,
        "application_id": req.application_id,
        "new_status": new_status,
        "citizen_notification": citizen_msg,
    }


from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from jose import jwt, JWTError

def _resolve_citizen_from_req(request: Request, raw_identifier: str, db: Session, language: str = "en", channel: str = "WEB"):
    """
    Resolves citizen using Bearer JWT token if available.
    Does NOT trust citizen_identifier supplied by frontend if token is provided.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            citizen_ref = payload.get("citizen_ref")
            if citizen_ref:
                citizen_repo = CitizenRepository(db)
                citizen = citizen_repo.get_by_ref(citizen_ref)
                if citizen:
                    return citizen
        except JWTError:
            pass

    citizen_repo = CitizenRepository(db)
    return citizen_repo.resolve_or_create(
        raw_identifier=raw_identifier,
        preferred_language=language,
        preferred_channel=channel,
    )


@router.post("/message")
def send_message(req: MessageRequest, request: Request, db: Session = Depends(get_db)):
    """
    Main chat endpoint. Process a citizen's message through the conversation pipeline.
    Handles intent detection, slot filling, validation, payment, submission.
    """
    # Authenticated token takes precedence over frontend body parameter
    citizen = _resolve_citizen_from_req(
        request,
        raw_identifier=req.citizen_identifier,
        db=db,
        language=req.language,
        channel=req.channel,
    )

    # Process through state machine
    orchestrator = ConversationOrchestrator(db)
    result = orchestrator.process_message(
        citizen_ref=citizen.citizen_ref,
        text=req.text,
        channel=req.channel,
        language=req.language,
        modality=req.modality,
        session_hint=req.session_hint,
    )

    # Fetch synced application info if linked
    app_num = None
    service_id = None
    documents = []
    anomaly_score = result.get("anomaly_score", 0.0)
    payment_status = result.get("payment_status", "PENDING")

    session = orchestrator.session_repo.load_session(citizen.citizen_ref)
    if session and session.application_id:
        from app.data_layer.repositories.application_repo import ApplicationRepository
        app_repo = ApplicationRepository(db)
        app = app_repo.get_by_id(session.application_id)
        if app:
            app_num = app.application_number
            service_id = app.service_id
            anomaly_score = app.anomaly_score
            payment_status = app.payment_status
            documents = [
                {
                    "id": d.id,
                    "doc_type": d.doc_type,
                    "filename": os.path.basename(d.file_ref) if d.file_ref else "",
                    "file_ref": f"/data/uploads/{os.path.basename(d.file_ref)}" if d.file_ref and not d.file_ref.startswith("mock") else d.file_ref,
                    "is_verified": d.verification_status == "VERIFIED",
                    "verification_status": d.verification_status,
                    "mismatch_fields": d.mismatch_fields,
                    "extracted_fields": d.extracted_fields,
                    "confidence_score": d.confidence_score,
                }
                for d in (app.documents or [])
            ]

    return {
        "status": "ok",
        "citizen_ref": citizen.citizen_ref,
        "application_number": app_num,
        "service_type": service_id,
        "documents": documents,
        "anomaly_score": anomaly_score,
        "payment_status": payment_status,
        **result,
    }


@router.post("/document-upload")
async def upload_document(
    request: Request,
    citizen_identifier: str = Form(...),
    doc_type: str = Form(...),
    channel: str = Form(default="WEB"),
    file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    """
    Handle document upload. Performs local mock OCR extraction.
    Actual file stored locally (not cloud). Cross-reference performed locally.
    """
    citizen = _resolve_citizen_from_req(request, raw_identifier=citizen_identifier, db=db, channel=channel)

    file_ref = "mock://document/no-file"

    if file:
        # Save to local filesystem (not cloud)
        os.makedirs(settings.STORAGE_PATH, exist_ok=True)
        file_path = os.path.join(settings.STORAGE_PATH, f"{citizen.citizen_ref}_{file.filename}")
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        file_ref = file_path

    # Run real OCR Service (PyMuPDF for PDFs, Tesseract for images, Gemini Vision first)
    from app.services.ocr_service import OCRService
    ocr_svc = OCRService()
    ocr_res = ocr_svc.run_ocr(file_ref, doc_type)
    extracted_fields = ocr_res.extracted_fields
    ocr_provider = ocr_res.provider
    ocr_confidence = ocr_res.confidence

    # Only fall back to mock if OCR returned NOTHING AT ALL (provider='mock' or empty)
    # We must NOT overwrite Gemini/Tesseract results with mock data — that would make
    # declared values identical to 'document' values and prevent mismatch detection.
    if not extracted_fields or ocr_res.provider == "mock":
        app_fields = {}
        orchestrator_temp = ConversationOrchestrator(db)
        session_temp = orchestrator_temp.session_repo.load_session(citizen.citizen_ref)
        if session_temp and session_temp.application_id:
            from app.data_layer.repositories.application_repo import ApplicationRepository
            app_fields = ApplicationRepository(db).get_fields(session_temp.application_id)
        extracted_fields = _mock_ocr_extract(doc_type, file.filename if file else "", app_fields)
        logger.warning(
            f"OCR returned no fields (provider={ocr_provider}). "
            f"Using filename-based mock for {doc_type}. "
            f"This means mismatch detection is operating on limited data."
        )

    logger.info(
        f"OCR completed: provider={ocr_provider}, confidence={ocr_confidence:.2f}, "
        f"fields={list(extracted_fields.keys())}"
    )

    orchestrator = ConversationOrchestrator(db)
    result = orchestrator.process_document_upload(
        citizen_ref=citizen.citizen_ref,
        doc_type=doc_type,
        file_ref=file_ref,
        extracted_fields=extracted_fields,
    )



    # Return synced application documents and info
    app_num = None
    service_id = None
    documents = []
    payment_status = "PENDING"
    session = orchestrator.session_repo.load_session(citizen.citizen_ref)
    if session and session.application_id:
        from app.data_layer.repositories.application_repo import ApplicationRepository
        app_repo = ApplicationRepository(db)
        app = app_repo.get_by_id(session.application_id)
        if app:
            app_num = app.application_number
            service_id = app.service_id
            payment_status = app.payment_status
            documents = [
                {
                    "id": d.id,
                    "doc_type": d.doc_type,
                    "filename": os.path.basename(d.file_ref) if d.file_ref else "",
                    "file_ref": f"/data/uploads/{os.path.basename(d.file_ref)}" if d.file_ref and not d.file_ref.startswith("mock") else d.file_ref,
                    "is_verified": d.verification_status == "VERIFIED",
                    "verification_status": d.verification_status,
                    "mismatch_fields": d.mismatch_fields,
                    "extracted_fields": d.extracted_fields,
                    "confidence_score": d.confidence_score,
                }
                for d in (app.documents or [])
            ]

    return {
        "status": "ok",
        "citizen_ref": citizen.citizen_ref,
        "application_number": app_num,
        "service_type": service_id,
        "documents": documents,
        "payment_status": payment_status,
        "ocr_provider": ocr_provider,
        "ocr_confidence": ocr_confidence,
        "ocr_fields_extracted": list(extracted_fields.keys()),
        **result
    }


@router.post("/resolve-mismatch")
def resolve_mismatch(req: ResolveMismatchRequest, db: Session = Depends(get_db)):
    """Resolve an OCR mismatch by either using document value or keeping declared value."""
    citizen_repo = CitizenRepository(db)
    citizen = citizen_repo.resolve_or_create(req.citizen_identifier)

    from app.data_layer.repositories.session_repo import SessionRepository
    from app.data_layer.repositories.application_repo import ApplicationRepository

    session_repo = SessionRepository(db)
    session = session_repo.load_session(citizen.citizen_ref)
    if not session or not session.application_id:
        raise HTTPException(status_code=400, detail="No active application session found.")

    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_id(session.application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")

    updated = False
    for doc in app.documents:
        if doc.verification_status == "MISMATCH" and req.field_name in doc.mismatch_fields:
            mismatch_list = [f for f in doc.mismatch_fields if f != req.field_name]
            doc.mismatch_fields = mismatch_list

            if req.resolution == "use_document":
                val = doc.extracted_fields.get(req.field_name)
                if val is not None:
                    # Update session slot
                    session.filled_slots = {**session.filled_slots, req.field_name: val}
                    session.missing_slots = [s for s in session.missing_slots if s != req.field_name]

                    # Save field in DB
                    spec = ServiceSpecLoader.get(app.service_id)
                    classification = "NON_SENSITIVE"
                    if spec:
                        slot_spec = next((s for s in spec.slots if s.name == req.field_name), None)
                        if slot_spec:
                            classification = slot_spec.classification
                    app_repo.save_field(app.id, req.field_name, val, classification)

            if not mismatch_list:
                doc.verification_status = "VERIFIED"
            db.add(doc)
            updated = True

    if updated:
        session_repo.save_session(session)
        db.commit()

    # Re-evaluate validation if no mismatches remain and all slots filled
    orchestrator = ConversationOrchestrator(db)
    has_mismatches = any(d.verification_status == "MISMATCH" for d in app.documents)

    spec = ServiceSpecLoader.get(app.service_id)
    all_docs_uploaded = True
    if spec and spec.required_docs:
        uploaded_types = [d.doc_type for d in app.documents]
        for rd in spec.required_docs:
            if rd["type"] not in uploaded_types:
                all_docs_uploaded = False

    response_msg = f"Resolved mismatch for '{req.field_name}' by choosing {req.resolution}."
    next_node = session.current_node
    extra = {}

    if not session.missing_slots and all_docs_uploaded and not has_mismatches:
        response_msg, next_node, extra = orchestrator._handle_validation(session)
        if next_node and next_node != session.current_node:
            session.current_node = next_node
            session_repo.save_session(session)
            db.commit()

    # Get fresh documents status
    documents = [
        {
            "id": d.id,
            "doc_type": d.doc_type,
            "filename": os.path.basename(d.file_ref) if d.file_ref else "",
            "file_ref": f"/data/uploads/{os.path.basename(d.file_ref)}" if d.file_ref and not d.file_ref.startswith("mock") else d.file_ref,
            "is_verified": d.verification_status == "VERIFIED",
            "verification_status": d.verification_status,
            "mismatch_fields": d.mismatch_fields,
            "extracted_fields": d.extracted_fields,
            "confidence_score": d.confidence_score,
        }
        for d in (app.documents or [])
    ]

    return {
        "status": "ok",
        "citizen_ref": citizen.citizen_ref,
        "session_id": session.id,
        "current_node": session.current_node,
        "response": response_msg,
        "filled_slots": session.filled_slots,
        "missing_slots": session.missing_slots,
        "payment_status": session.payment_status,
        "consent_given": session.consent_given,
        "anomaly_score": session.anomaly_score,
        "application_number": app.application_number,
        "service_type": app.service_id,
        "documents": documents,
        **extra,
    }


@router.post("/voice-message")
async def voice_message(
    citizen_identifier: str = Form(...),
    channel: str = Form(default="WEB"),
    language: str = Form(default="en"),
    session_hint: Optional[str] = Form(default=None),
    transcript: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    """
    Handle voice messages. Saves wav and triggers STT/NLU state machine, generating TTS audio.
    """
    citizen_repo = CitizenRepository(db)
    citizen = citizen_repo.resolve_or_create(
        raw_identifier=citizen_identifier,
        preferred_language=language,
        preferred_channel=channel,
    )

    user_text = transcript if transcript else "Hello"

    if file:
        os.makedirs(settings.AUDIO_PATH, exist_ok=True)
        filename = f"{citizen.citizen_ref}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}.wav"
        filepath = os.path.join(settings.AUDIO_PATH, filename)
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)

    # Process via orchestrator
    orchestrator = ConversationOrchestrator(db)
    result = orchestrator.process_message(
        citizen_ref=citizen.citizen_ref,
        text=user_text,
        channel=channel,
        language=language,
        modality="VOICE",
        session_hint=session_hint,
    )

    # Generate tiny valid mock wav file for TTS
    tts_filename = f"tts_{citizen.citizen_ref}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}.wav"
    tts_path = os.path.join(settings.AUDIO_PATH, tts_filename)

    import wave
    import struct
    try:
        with wave.open(tts_path, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(8000)
            for _ in range(800):
                value = int(32767 * 0.1)
                data = struct.pack('<h', value)
                wav_file.writeframesraw(data)
    except Exception as e:
        logger.error(f"Failed to generate mock TTS: {e}")

    tts_url = f"/data/audio/{tts_filename}"

    # Return synced details
    app_num = None
    service_id = None
    documents = []
    payment_status = "PENDING"
    anomaly_score = result.get("anomaly_score", 0.0)

    session = orchestrator.session_repo.load_session(citizen.citizen_ref)
    if session and session.application_id:
        from app.data_layer.repositories.application_repo import ApplicationRepository
        app_repo = ApplicationRepository(db)
        app = app_repo.get_by_id(session.application_id)
        if app:
            app_num = app.application_number
            service_id = app.service_id
            payment_status = app.payment_status
            anomaly_score = app.anomaly_score
            documents = [
                {
                    "id": d.id,
                    "doc_type": d.doc_type,
                    "filename": os.path.basename(d.file_ref) if d.file_ref else "",
                    "file_ref": f"/data/uploads/{os.path.basename(d.file_ref)}" if d.file_ref and not d.file_ref.startswith("mock") else d.file_ref,
                    "is_verified": d.verification_status == "VERIFIED",
                    "verification_status": d.verification_status,
                    "mismatch_fields": d.mismatch_fields,
                    "extracted_fields": d.extracted_fields,
                    "confidence_score": d.confidence_score,
                }
                for d in (app.documents or [])
            ]

    return {
        "status": "ok",
        "citizen_ref": citizen.citizen_ref,
        "transcript": user_text,
        "response": result.get("response", ""),
        "audio_url": tts_url,
        "application_number": app_num,
        "service_type": service_id,
        "documents": documents,
        "payment_status": payment_status,
        "anomaly_score": anomaly_score,
        **{k: v for k, v in result.items() if k not in ("status", "citizen_ref", "response", "payment_status", "anomaly_score")},
    }


@router.post("/channel-switch")
def switch_channel(req: ChannelSwitchRequest, db: Session = Depends(get_db)):
    """
    Handle omnichannel switch: citizen moves from WhatsApp to IVR, or IVR to Web.
    Context is preserved — session continues from where it left off.
    """
    citizen_repo = CitizenRepository(db)
    citizen = citizen_repo.resolve_or_create(req.citizen_identifier, preferred_channel=req.new_channel)

    from app.data_layer.repositories.session_repo import SessionRepository
    session_repo = SessionRepository(db)
    session = session_repo.transfer_channel(citizen.citizen_ref, req.new_channel)

    if not session:
        return {
            "status": "no_active_session",
            "message": "No active session found. Starting fresh.",
            "citizen_ref": citizen.citizen_ref,
        }

    return {
        "status": "channel_transferred",
        "citizen_ref": citizen.citizen_ref,
        "current_node": session.current_node,
        "channel": req.new_channel,
        "filled_slots": session.filled_slots,
        "missing_slots": session.missing_slots,
        "message": f"Welcome back! Continuing your {session.current_node} application from {req.new_channel}.",
    }


@router.get("/session/{citizen_identifier}")
def get_session(citizen_identifier: str, request: Request, db: Session = Depends(get_db)):
    """Get current session state for a citizen."""
    citizen = _resolve_citizen_from_req(request, raw_identifier=citizen_identifier, db=db)

    from app.data_layer.repositories.session_repo import SessionRepository
    session = SessionRepository(db).load_session(citizen.citizen_ref)

    if not session:
        return {"status": "no_session", "citizen_ref": citizen.citizen_ref}

    app_num = None
    service_id = None
    documents = []
    anomaly_score = session.anomaly_score
    payment_status = session.payment_status

    if session.application_id:
        from app.data_layer.repositories.application_repo import ApplicationRepository
        app_repo = ApplicationRepository(db)
        app = app_repo.get_by_id(session.application_id)
        if app:
            app_num = app.application_number
            service_id = app.service_id
            anomaly_score = app.anomaly_score
            payment_status = app.payment_status
            documents = [
                {
                    "id": d.id,
                    "doc_type": d.doc_type,
                    "filename": os.path.basename(d.file_ref) if d.file_ref else "",
                    "file_ref": f"/data/uploads/{os.path.basename(d.file_ref)}" if d.file_ref and not d.file_ref.startswith("mock") else d.file_ref,
                    "is_verified": d.verification_status == "VERIFIED",
                    "verification_status": d.verification_status,
                    "mismatch_fields": d.mismatch_fields,
                    "extracted_fields": d.extracted_fields,
                    "confidence_score": d.confidence_score,
                }
                for d in (app.documents or [])
            ]

    return {
        "status": "active",
        "session_id": session.id,
        "citizen_ref": citizen.citizen_ref,
        "current_node": session.current_node,
        "channel": session.channel,
        "language": session.language,
        "filled_slots": session.filled_slots,
        "missing_slots": session.missing_slots,
        "payment_status": payment_status,
        "consent_given": session.consent_given,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        "application_number": app_num,
        "service_type": service_id,
        "documents": documents,
        "anomaly_score": anomaly_score,
    }


def _mock_ocr_extract(doc_type: str, filename: str = "", app_fields: dict = None) -> dict:
    """Dynamic fallback OCR field extraction (parses filename, application fields, or preset)."""
    fn_lower = filename.lower()
    extracted = {"doc_type": doc_type}

    # 1. Filename explicit overrides (e.g. name_John_dob_15-08-1995.pdf)
    if "name_" in filename:
        parts = filename.split("name_")[1].split("_")
        if parts: extracted["applicant_name"] = parts[0].replace(".pdf", "").replace(".png", "").replace(".jpg", "").strip()
    if "dob_" in filename:
        parts = filename.split("dob_")[1].split("_")
        if parts: extracted["applicant_dob"] = parts[0].replace(".pdf", "").replace(".png", "").replace(".jpg", "").strip()
    if "income_" in filename:
        parts = filename.split("income_")[1].split("_")
        if parts: extracted["annual_income"] = parts[0].replace(".pdf", "").replace(".png", "").replace(".jpg", "").strip()
    if "aadhaar_" in filename:
        parts = filename.split("aadhaar_")[1].split("_")
        if parts: extracted["aadhaar_number"] = parts[0].replace(".pdf", "").replace(".png", "").replace(".jpg", "").strip()

    # 3. If 'mismatch' or 'fake' in filename -> explicit mismatch test data
    if "mismatch" in fn_lower or "fake" in fn_lower or "test_mismatch" in fn_lower:
        extracted.setdefault("applicant_name", "Demo Mismatch User")
        extracted.setdefault("applicant_dob", "01-01-1990")
        extracted.setdefault("aadhaar_number", "123456789012")
        extracted.setdefault("address", "Fake Mismatch Address 99")
        return extracted


    # 4. Default fallback presets if still missing
    mocks = {
        "IDENTITY_PROOF": {"applicant_name": "Demo User", "applicant_dob": "01-01-1990", "aadhaar_number": "123456789012"},
        "INCOME_PROOF": {"annual_income": "150000", "employer": "Demo Corp"},
        "CASTE_PROOF": {"caste_category": "OBC", "caste_name": "Kunbi"},
        "ADDRESS_PROOF": {"address": "123 Demo Street, Nagpur, Maharashtra"},
        "PAYMENT_RECEIPT": {"transaction_id": f"UPI{str(os.urandom(6).hex()).upper()}", "amount": "50"},
    }

    default_vals = mocks.get(doc_type, {})
    for k, v in default_vals.items():
        if k not in extracted:
            extracted[k] = v

    return extracted


