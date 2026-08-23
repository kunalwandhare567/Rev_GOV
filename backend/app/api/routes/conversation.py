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


# ── Endpoints ──

@router.post("/message")
def send_message(req: MessageRequest, db: Session = Depends(get_db)):
    """
    Main chat endpoint. Process a citizen's message through the conversation pipeline.
    Handles intent detection, slot filling, validation, payment, submission.
    """
    # Resolve citizen_ref (tokenized, never stores raw identifier)
    citizen_repo = CitizenRepository(db)
    citizen = citizen_repo.resolve_or_create(
        raw_identifier=req.citizen_identifier,
        preferred_language=req.language,
        preferred_channel=req.channel,
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
    citizen_repo = CitizenRepository(db)
    citizen = citizen_repo.resolve_or_create(raw_identifier=citizen_identifier, preferred_channel=channel)

    file_ref = "mock://document/no-file"

    if file:
        # Save to local filesystem (not cloud)
        os.makedirs(settings.STORAGE_PATH, exist_ok=True)
        file_path = os.path.join(settings.STORAGE_PATH, f"{citizen.citizen_ref}_{file.filename}")
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        file_ref = file_path

    # Mock OCR extraction (in production: call local LayoutLMv3)
    extracted_fields = _mock_ocr_extract(doc_type, file.filename if file else "")

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
def get_session(citizen_identifier: str, db: Session = Depends(get_db)):
    """Get current session state for a citizen."""
    citizen_repo = CitizenRepository(db)
    citizen = citizen_repo.resolve_or_create(citizen_identifier)

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


def _mock_ocr_extract(doc_type: str, filename: str = "") -> dict:
    """Mock OCR field extraction (dynamic based on filename or preset)."""
    # Parse dynamic variables from filename to ease testing
    # E.g. name_John Doe_dob_15-08-1995_income_500000.pdf
    fn_lower = filename.lower()
    extracted = {"doc_type": doc_type}

    if "name_" in filename:
        parts = filename.split("name_")[1].split("_")
        if parts: extracted["name"] = parts[0].replace(".pdf", "").replace(".png", "").replace(".jpg", "").strip()
    if "dob_" in filename:
        parts = filename.split("dob_")[1].split("_")
        if parts: extracted["dob"] = parts[0].replace(".pdf", "").replace(".png", "").replace(".jpg", "").strip()
    if "income_" in filename:
        parts = filename.split("income_")[1].split("_")
        if parts: extracted["annual_income"] = parts[0].replace(".pdf", "").replace(".png", "").replace(".jpg", "").strip()
    if "aadhaar_" in filename:
        parts = filename.split("aadhaar_")[1].split("_")
        if parts: extracted["aadhaar"] = parts[0].replace(".pdf", "").replace(".png", "").replace(".jpg", "").strip()
    if "address_" in filename:
        parts = filename.split("address_")[1].split("_")
        if parts: extracted["address"] = parts[0].replace(".pdf", "").replace(".png", "").replace(".jpg", "").replace("-", " ").strip()

    # Pre-sets if filename doesn't contain matching overrides
    mocks = {
        "IDENTITY_PROOF": {"name": "Demo User", "applicant_dob": "01-01-1990", "aadhaar_number": "123456789012"},
        "INCOME_PROOF": {"annual_income": "150000", "employer": "Demo Corp"},
        "CASTE_PROOF": {"caste_category": "OBC", "caste_name": "Kunbi"},
        "ADDRESS_PROOF": {"address": "123 Demo Street, Nagpur, Maharashtra"},
        "RESIDENCE_PROOF": {"address": "123 Demo Street, Nagpur, Maharashtra"},
        "PAYMENT_RECEIPT": {"transaction_id": f"UPI{str(os.urandom(6).hex()).upper()}", "amount": "50"},
    }

    # Merge mock defaults with filename overrides
    default_vals = mocks.get(doc_type, {})
    for k, v in default_vals.items():
        if k not in extracted:
            # Map standard slot names
            if k == "name": extracted["applicant_name"] = v
            elif k == "dob": extracted["applicant_dob"] = v
            elif k == "aadhaar": extracted["aadhaar_number"] = v
            else: extracted[k] = v

    # Make sure keys align with slots
    if "name" in extracted and "applicant_name" not in extracted:
        extracted["applicant_name"] = extracted.pop("name")
    if "dob" in extracted and "applicant_dob" not in extracted:
        extracted["applicant_dob"] = extracted.pop("dob")
    if "aadhaar" in extracted and "aadhaar_number" not in extracted:
        extracted["aadhaar_number"] = extracted.pop("aadhaar")

    return extracted

