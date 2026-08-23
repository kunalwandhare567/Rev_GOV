"""
Conversation API Routes
Main citizen interaction endpoint: handles chat messages, document upload,
channel switching, and status queries.
"""
import os
import shutil
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.orchestration.state_machine.orchestrator import ConversationOrchestrator
from app.data_layer.repositories.citizen_repo import CitizenRepository

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

    return {
        "status": "ok",
        "citizen_ref": citizen.citizen_ref,
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
    extracted_fields = _mock_ocr_extract(doc_type)

    orchestrator = ConversationOrchestrator(db)
    result = orchestrator.process_document_upload(
        citizen_ref=citizen.citizen_ref,
        doc_type=doc_type,
        file_ref=file_ref,
        extracted_fields=extracted_fields,
    )

    return {"status": "ok", "citizen_ref": citizen.citizen_ref, **result}


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

    return {
        "status": "active",
        "session_id": session.id,
        "citizen_ref": citizen.citizen_ref,
        "current_node": session.current_node,
        "channel": session.channel,
        "language": session.language,
        "filled_slots": session.filled_slots,
        "missing_slots": session.missing_slots,
        "payment_status": session.payment_status,
        "consent_given": session.consent_given,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
    }


def _mock_ocr_extract(doc_type: str) -> dict:
    """Mock OCR field extraction (replace with LayoutLMv3 in production)."""
    mocks = {
        "IDENTITY_PROOF": {"doc_type": "AADHAAR", "name": "Demo User", "dob": "01-01-1990"},
        "INCOME_PROOF": {"doc_type": "SALARY_SLIP", "annual_income": "150000", "employer": "Demo Corp"},
        "CASTE_PROOF": {"doc_type": "COMMUNITY_LETTER", "caste": "OBC"},
        "RESIDENCE_PROOF": {"doc_type": "VOTER_ID", "address": "123 Demo Street"},
    }
    return mocks.get(doc_type, {"doc_type": doc_type, "extracted": True})
