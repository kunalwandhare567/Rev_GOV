"""
Payment API Route — Phase 11
POST /api/v1/payment/initiate
POST /api/v1/payment/verify-receipt
GET  /api/v1/payment/status/{application_id}
POST /api/v1/payment/simulate-success
"""
import os
import shutil
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.services.payment_service import PaymentService
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.orchestration.state_machine.application_fsm import AppState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payment", tags=["payment"])

UPLOAD_DIR = "data/receipts"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class PaymentInitRequest(BaseModel):
    application_id: str
    citizen_identifier: str
    amount: float = 50.0
    channel: str = "WEB"
    mode: str = "MOCK_AUTO"   # MOCK_AUTO | UPI_QR


@router.post("/initiate")
def initiate_payment(body: PaymentInitRequest, db: Session = Depends(get_db)):
    """Initiate payment for an application.

    PHASE 9 RULE: Payment is ONLY allowed after government APPROVAL.
    Applications not in PAYMENT_REQUIRED state will receive a 400 error.
    This prevents premature payment before verification.
    """
    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_id(body.application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # ── Phase 9 Guard: Payment ONLY after approval ──
    if app.status != AppState.PAYMENT_REQUIRED:
        status_msg = {
            AppState.INITIATED:                   "Application has not been started yet.",
            AppState.INFORMATION_COLLECTION:      "Application is still collecting information.",
            AppState.DOCUMENT_COLLECTION:         "Documents are still being uploaded.",
            AppState.UNDER_REVIEW:                "Application is under government review. Payment will be enabled after approval.",
            AppState.SUBMITTED_FOR_VERIFICATION:  "Application is submitted and awaiting government review.",
            AppState.APPROVED:                    "Application is approved. Payment link will be sent shortly.",
            AppState.PAYMENT_COMPLETED:           "Payment has already been completed.",
            AppState.REJECTED:                    "This application has been rejected. Payment not applicable.",
            AppState.COMPLETED:                   "Application is complete.",
        }.get(app.status, f"Payment not available in current state: {app.status}")

        raise HTTPException(
            status_code=400,
            detail=(
                f"Payment is only allowed after government approval. "
                f"Current status: {app.status}. {status_msg}"
            ),
        )

    if app.payment_status in ("PAID", "SUCCESS"):
        raise HTTPException(status_code=400, detail="Payment already completed")

    citizen_repo = CitizenRepository(db)
    citizen = citizen_repo.resolve_or_create(body.citizen_identifier)

    svc = PaymentService(db)
    result = svc.initiate_payment(
        application_id=body.application_id,
        amount=body.amount,
        citizen_ref=citizen.citizen_ref,
        channel=body.channel,
        mode=body.mode,
    )
    return result


@router.post("/verify-receipt")
async def verify_receipt(
    application_id: str = Form(...),
    citizen_identifier: str = Form(...),
    channel: str = Form("WEB"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload and OCR-verify a payment receipt screenshot."""
    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_id(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Save uploaded file
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    save_path = os.path.join(UPLOAD_DIR, f"receipt_{application_id}{ext}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    citizen_repo = CitizenRepository(db)
    citizen = citizen_repo.resolve_or_create(citizen_identifier)

    svc = PaymentService(db)
    result = svc.verify_receipt(
        application_id=application_id,
        citizen_ref=citizen.citizen_ref,
        file_path=save_path,
        channel=channel,
    )
    return result


@router.get("/status/{application_id}")
def payment_status(application_id: str, db: Session = Depends(get_db)):
    """Get payment status for an application."""
    svc = PaymentService(db)
    result = svc.get_payment_status(application_id)
    if result["status"] == "NOT_FOUND":
        raise HTTPException(status_code=404, detail="Application not found")
    return result


@router.post("/simulate-success/{application_id}")
def simulate_payment_success(application_id: str, db: Session = Depends(get_db)):
    """Dev tool: instantly mark payment as successful (demo/test mode only)."""
    app_repo = ApplicationRepository(db)
    app = app_repo.get_by_id(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    svc = PaymentService(db)
    result = svc._process_mock(
        application_id=application_id,
        citizen_ref=app.citizen_ref,
        amount=50.0,
        txn_id=f"SIM-{application_id[:8].upper()}",
        channel="WEB",
    )
    return {**result, "simulated": True}
