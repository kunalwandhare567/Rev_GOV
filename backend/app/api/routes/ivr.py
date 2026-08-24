"""
IVR Phone Simulator Route
Handles voice call simulation for the IVR helpline UI.
POST /api/v1/ivr/start   → Start call, get greeting audio
POST /api/v1/ivr/input   → Process voice/DTMF input, get response audio
POST /api/v1/ivr/end     → End call session
GET  /api/v1/ivr/status  → Get current IVR session state
"""
import os
import uuid
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.services.citizen_resolver import CitizenResolver
from app.services.tts_service import TTSService
from app.services.stt_service import STTService
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.models.db_models import IVRSession
import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ivr", tags=["ivr"])

_tts = TTSService()
_stt = STTService()

IVR_GREETINGS = {
    "en": "Welcome to Revenue Government Platform! I am here to help you. For application status, press 1. For tracking ID, press 2. For payment status, press 3. To repeat, press 0.",
    "hi": "राजस्व सरकार प्लेटफ़ॉर्म में आपका स्वागत है! मैं आपकी सहायता के लिए यहाँ हूँ। आवेदन स्थिति के लिए 1 दबाएं। ट्रैकिंग ID के लिए 2 दबाएं। भुगतान स्थिति के लिए 3 दबाएं।",
    "mr": "रेव्हेन्यू गव्हर्नमेंट प्लॅटफॉर्ममध्ये आपले स्वागत आहे! अर्जाची स्थिती जाणण्यासाठी 1 दाबा. ट्रॅकिंग ID साठी 2 दाबा. पेमेंट स्थितीसाठी 3 दाबा.",
}

STATUS_LABEL = {
    "DRAFT": {"en": "Draft", "hi": "ड्राफ्ट", "mr": "मसुदा"},
    "INFORMATION_COLLECTION": {"en": "Collecting information", "hi": "जानकारी संग्रह", "mr": "माहिती संकलन"},
    "DOCUMENT_COLLECTION": {"en": "Collecting documents", "hi": "दस्तावेज़ संग्रह", "mr": "कागदपत्र संकलन"},
    "OCR_VALIDATION": {"en": "Validating documents", "hi": "दस्तावेज़ सत्यापन", "mr": "कागदपत्र सत्यापन"},
    "FINAL_REVIEW": {"en": "Ready for your review", "hi": "समीक्षा के लिए तैयार", "mr": "तुमच्या पुनरावलोकनासाठी तयार"},
    "SUBMITTED_FOR_VERIFICATION": {"en": "Submitted for government verification", "hi": "सरकारी सत्यापन के लिए जमा", "mr": "सरकारी सत्यापनासाठी सादर"},
    "UNDER_REVIEW": {"en": "Under government review", "hi": "सरकारी समीक्षा में", "mr": "सरकारी आढाव्याखाली"},
    "CLARIFICATION_REQUIRED": {"en": "Additional information required", "hi": "अतिरिक्त जानकारी आवश्यक", "mr": "अतिरिक्त माहिती आवश्यक"},
    "APPROVED": {"en": "Approved! Payment required", "hi": "स्वीकृत! भुगतान आवश्यक", "mr": "मंजूर! पेमेंट आवश्यक"},
    "PAYMENT_REQUIRED": {"en": "Payment required", "hi": "भुगतान आवश्यक", "mr": "पेमेंट आवश्यक"},
    "PAYMENT_COMPLETED": {"en": "Payment completed, processing final submission", "hi": "भुगतान पूर्ण", "mr": "पेमेंट पूर्ण"},
    "COMPLETED": {"en": "Completed! Certificate ready", "hi": "पूर्ण! प्रमाण पत्र तैयार", "mr": "पूर्ण! प्रमाणपत्र तयार"},
    "REJECTED": {"en": "Unfortunately rejected. Please contact the helpdesk.", "hi": "खेद है, अस्वीकृत", "mr": "खेद आहे, नाकारले"},
}


class IVRStartRequest(BaseModel):
    call_id: Optional[str] = None
    caller_phone: Optional[str] = None       # Citizen's phone number
    citizen_phone: Optional[str] = None
    language: str = "en"


class IVRInputRequest(BaseModel):
    call_id: Optional[str] = None
    session_id: Optional[str] = None
    input_type: str = "dtmf"  # dtmf | voice
    dtmf_key: Optional[str] = None  # "1", "2", "3", "0"
    voice_text: Optional[str] = None  # STT result
    language: str = "en"


class IVREndRequest(BaseModel):
    call_id: Optional[str] = None
    session_id: Optional[str] = None


@router.post("/start")
async def start_call(request: IVRStartRequest, db: Session = Depends(get_db)):
    """
    Called when citizen presses the 'Call' button in IVR Simulator UI.
    Returns greeting audio URL and session info.
    """
    phone = request.caller_phone or request.citizen_phone or "9876543210"
    call_id = request.call_id or f"CALL-{str(uuid.uuid4())[:8].upper()}"

    # Resolve citizen by phone
    resolver = CitizenResolver(db)
    citizen = resolver.resolve(phone=phone)

    # Create IVR session
    import hashlib
    phone_hash = hashlib.sha256(phone.strip().encode()).hexdigest()

    session = IVRSession(
        call_id=call_id,
        citizen_ref=citizen.citizen_ref if citizen else None,
        caller_phone_hash=phone_hash,
        language=request.language,
        current_state="GREETING",
    )
    db.add(session)
    db.commit()

    # Get application if citizen found
    app_info = None
    if citizen:
        app_repo = ApplicationRepository(db)
        app = app_repo.get_active_for_citizen(citizen.citizen_ref)
        if app:
            status_label = STATUS_LABEL.get(app.status, {}).get(request.language, app.status)
            # Phase 14 fix: use service_id safely (no relationship attribute)
            service_name = (
                app.service_id.replace("_", " ").replace("certificate", "Certificate").title()
                if app.service_id else "Certificate"
            )
            app_info = {
                "tracking_id": app.tracking_id,
                "status": status_label,
                "service": service_name,
            }

    # Generate greeting
    if app_info:
        greeting_text = {
            "en": f"Welcome! I found your {app_info['service']} application. Tracking ID: {app_info['tracking_id']}. Current status: {app_info['status']}. {IVR_GREETINGS['en']}",
            "hi": f"नमस्ते! आपका {app_info['service']} आवेदन मिला। ट्रैकिंग ID: {app_info['tracking_id']}। स्थिति: {app_info['status']}। {IVR_GREETINGS['hi']}",
            "mr": f"नमस्कार! तुमचा {app_info['service']} अर्ज सापडला. ट्रॅकिंग ID: {app_info['tracking_id']}. स्थिती: {app_info['status']}. {IVR_GREETINGS['mr']}",
        }.get(request.language, IVR_GREETINGS["en"])
    else:
        greeting_text = IVR_GREETINGS.get(request.language, IVR_GREETINGS["en"])

    # Generate TTS audio
    audio_path = _tts.synthesize_for_ivr(
        greeting_text, request.language, output_dir="data/audio/ivr"
    )
    audio_url = f"/data/audio/ivr/{os.path.basename(audio_path)}" if audio_path else None

    # Log conversation
    session.conversation_log = [{"role": "SYSTEM", "text": greeting_text,
                                  "timestamp": datetime.datetime.utcnow().isoformat()}]
    session.current_state = "MAIN_MENU"
    db.commit()

    return {
        "call_id": call_id,
        "session_id": call_id,
        "greeting_text": greeting_text,
        "audio_url": audio_url,
        "next_expected": "DTMF",
        "current_state": "GREETING",
        "language": request.language,
    }


@router.post("/input")
async def receive_input(request: IVRInputRequest, db: Session = Depends(get_db)):
    """
    Process DTMF keypress or voice input from IVR helpline.
    Returns response audio and updated call state.
    """
    target_id = request.call_id or request.session_id
    session = db.query(IVRSession).filter(
        (IVRSession.call_id == target_id) | (IVRSession.id == target_id)
    ).first()
    if not session:
        return {"error": "Session not found", "status_code": 404}

    lang = request.language or session.language or "en"

    # Determine input
    if str(request.input_type).lower() == "dtmf" and request.dtmf_key:
        user_input = request.dtmf_key
    elif request.voice_text:
        user_input = request.voice_text
    else:
        user_input = "0"

    # Generate response based on DTMF/voice
    response_text = _process_ivr_input(user_input, session, lang, db)

    # TTS
    audio_path = _tts.synthesize_for_ivr(response_text, lang, output_dir="data/audio/ivr")
    audio_url = f"/data/audio/ivr/{os.path.basename(audio_path)}" if audio_path else None

    # Update conversation log
    logs = session.conversation_log or []
    logs.append({"role": "USER", "text": user_input,
                 "timestamp": datetime.datetime.utcnow().isoformat()})
    logs.append({"role": "SYSTEM", "text": response_text,
                 "timestamp": datetime.datetime.utcnow().isoformat()})
    session.conversation_log = logs
    db.commit()

    return {
        "response_text": response_text,
        "audio_url": audio_url,
        "state": session.current_state,
    }


@router.post("/end")
async def end_call(
    request: Optional[IVREndRequest] = None,
    call_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """End IVR session."""
    target_id = (request.call_id if request else None) or (request.session_id if request else None) or call_id
    if target_id:
        session = db.query(IVRSession).filter(
            (IVRSession.call_id == target_id) | (IVRSession.id == target_id)
        ).first()
        if session:
            session.call_status = "COMPLETED"
            session.ended_at = datetime.datetime.utcnow()
            db.commit()
    return {"message": "Call ended. Thank you for using Revenue Gov Platform."}


def _process_ivr_input(user_input: str, session: IVRSession, lang: str,
                        db: Session) -> str:
    """Generate IVR response based on citizen input."""
    app_info = None
    if session.citizen_ref:
        app_repo = ApplicationRepository(db)
        app = app_repo.get_active_for_citizen(session.citizen_ref)
        if app:
            status_label = STATUS_LABEL.get(app.status, {}).get(lang, app.status)
            # Phase 14 fix: use service_id safely
            service_name = (
                app.service_id.replace("_", " ").replace("certificate", "Certificate").title()
                if app.service_id else "Certificate"
            )
            app_info = {
                "tracking_id": app.tracking_id,
                "status": status_label,
                "service": service_name,
            }

    key = user_input.strip()

    if key == "1" or "status" in user_input.lower():
        if app_info:
            return {
                "en": f"Your {app_info['service']} application status is: {app_info['status']}. Tracking ID: {app_info['tracking_id']}.",
                "hi": f"आपके {app_info['service']} आवेदन की स्थिति है: {app_info['status']}। ट्रैकिंग ID: {app_info['tracking_id']}।",
                "mr": f"तुमच्या {app_info['service']} अर्जाची स्थिती आहे: {app_info['status']}. ट्रॅकिंग ID: {app_info['tracking_id']}.",
            }.get(lang, "Status not available.")
        return {"en": "No active application found for your phone number.",
                "hi": "कोई सक्रिय आवेदन नहीं मिला।",
                "mr": "कोणताही सक्रिय अर्ज सापडला नाही."}.get(lang, "Not found.")

    elif key == "2" or "tracking" in user_input.lower():
        if app_info:
            return {
                "en": f"Your tracking ID is {app_info['tracking_id']}.",
                "hi": f"आपकी ट्रैकिंग ID है: {app_info['tracking_id']}।",
                "mr": f"तुमची ट्रॅकिंग ID आहे: {app_info['tracking_id']}.",
            }.get(lang, "")
        return {"en": "No application found.", "hi": "कोई आवेदन नहीं।", "mr": "अर्ज नाही."}.get(lang, "")

    elif key == "3" or "payment" in user_input.lower():
        if app_info:
            return {
                "en": f"Payment status for your {app_info['service']} application: {app_info['status']}.",
                "hi": f"भुगतान स्थिति: {app_info['status']}।",
                "mr": f"पेमेंट स्थिती: {app_info['status']}.",
            }.get(lang, "")
        return {"en": "No payment information found.", "hi": "भुगतान जानकारी नहीं।", "mr": "पेमेंट माहिती नाही."}.get(lang, "")

    elif key == "0":
        return IVR_GREETINGS.get(lang, IVR_GREETINGS["en"])

    else:
        return {"en": "I did not understand. Press 1 for status, 2 for tracking ID, 3 for payment, 0 to repeat.",
                "hi": "मैं समझ नहीं पाया। स्थिति के लिए 1, ट्रैकिंग के लिए 2, भुगतान के लिए 3, दोहराने के लिए 0 दबाएं।",
                "mr": "मला समजले नाही. स्थितीसाठी 1, ट्रॅकिंगसाठी 2, पेमेंटसाठी 3, पुन्हा ऐकण्यासाठी 0 दाबा."
               }.get(lang, "")
