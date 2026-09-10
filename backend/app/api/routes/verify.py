"""
Public Certificate Verification API Route
GET /api/v1/certificates/verify/{cert_number}
Public verification page endpoint for QR code scanning.
"""
import logging
import hashlib
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.db_models import Certificate, Application, Service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("/verify/{cert_number}")
def verify_certificate_public(cert_number: str, db: Session = Depends(get_db)):
    """Public verification endpoint for scanned QR codes on official certificates."""
    cert = db.query(Certificate).filter(Certificate.certificate_number == cert_number).first()
    if not cert:
        # Check if tracking_id or application_number was scanned instead
        app_obj = db.query(Application).filter(
            (Application.tracking_id == cert_number) | (Application.application_number == cert_number)
        ).first()
        if app_obj and app_obj.certificate:
            cert = app_obj.certificate

    if not cert:
        raise HTTPException(
            status_code=404,
            detail={
                "valid": False,
                "status": "NOT_FOUND",
                "message": f"No official government certificate found with identifier: '{cert_number}'",
            }
        )

    app = cert.application
    service_name = app.service.name_en if app and app.service else (app.service_id if app else "Government Revenue Certificate")
    citizen_ref = app.citizen_ref if app else "Verified Citizen"
    
    # Generate cryptographic verification seal hash
    raw_hash_str = f"{cert.certificate_number}:{app.id if app else cert.id}:{cert.issue_date.isoformat() if cert.issue_date else ''}"
    hash_stamp = hashlib.sha256(raw_hash_str.encode("utf-8")).hexdigest().upper()

    is_expired = cert.expiry_date and cert.expiry_date < datetime.datetime.utcnow()
    status = "EXPIRED" if is_expired else "VALID"

    return {
        "valid": not is_expired,
        "status": status,
        "certificate_number": cert.certificate_number,
        "application_number": app.application_number if app else "N/A",
        "tracking_id": app.tracking_id if app else "N/A",
        "service_name": service_name,
        "citizen_ref": citizen_ref,
        "issue_date": cert.issue_date.isoformat() if cert.issue_date else None,
        "expiry_date": cert.expiry_date.isoformat() if cert.expiry_date else None,
        "issuing_authority": "Revenue Department, Government of Maharashtra",
        "digital_stamp_hash": hash_stamp[:24],
        "full_hash": hash_stamp,
        "download_url": f"/data/certificates/{cert.certificate_number}.pdf",
    }
