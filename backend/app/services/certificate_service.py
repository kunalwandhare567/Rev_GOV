"""
Certificate Generation Service
Generates official government certificates upon successful payment completion.
Integrates with SQLite database, Certificate model, and SSE event broadcast.
"""
import os
import uuid
import logging
import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.db_models import Application, Certificate, Citizen
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.rules_engine.engine import ServiceSpecLoader

logger = logging.getLogger(__name__)

CERT_DIR = "data/certificates"
os.makedirs(CERT_DIR, exist_ok=True)


class CertificateService:
    def __init__(self, db: Session):
        self.db = db
        self.app_repo = ApplicationRepository(db)

    def generate_and_store(
        self,
        application_id: str,
        citizen_ref: str,
    ) -> Dict[str, Any]:
        """
        Generate and persist official certificate.
        Transitions state to CERTIFICATE_READY -> COMPLETED.
        """
        app = self.app_repo.get_by_id(application_id)
        if not app:
            logger.error(f"Cannot generate certificate: Application {application_id} not found")
            return {"success": False, "error": "Application not found"}

        cert_number = f"CERT-{datetime.datetime.utcnow().year}-{str(uuid.uuid4())[:8].upper()}"
        file_path = os.path.join(CERT_DIR, f"{cert_number}.pdf")

        # Create a mock/stub certificate file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"%PDF-1.4\n% Government Certificate\nApplication: {app.application_number}\nTracking: {app.tracking_id}\nCitizen: {citizen_ref}\nCertificate Number: {cert_number}\nIssued At: {datetime.datetime.utcnow().isoformat()}\n")
        except Exception as e:
            logger.warning(f"Could not write certificate file: {e}")

        # Persist Certificate record
        cert = self.app_repo.issue_certificate(
            application_id=app.id,
            file_ref=file_path,
            expiry_days=180,
        )
        cert.certificate_number = cert_number
        self.db.commit()

        # Phase 13 / 16: Broadcast SSE
        try:
            from app.api.routes.stream import broadcast_status_change_sync, bus
            broadcast_status_change_sync(
                application_id=app.tracking_id or str(app.id),
                tracking_id=app.tracking_id or app.application_number,
                new_status="CERTIFICATE_READY",
                actor="SYSTEM",
                extra={
                    "certificate_number": cert_number,
                    "file_ref": f"/data/certificates/{cert_number}.pdf",
                },
            )
            if citizen_ref:
                bus.publish_sync(citizen_ref, {
                    "type": "status_change",
                    "tracking_id": app.tracking_id or app.application_number,
                    "new_status": "CERTIFICATE_READY",
                    "actor": "SYSTEM",
                    "certificate_number": cert_number,
                })
        except Exception as e:
            logger.warning(f"SSE broadcast error: {e}")

        return {
            "success": True,
            "certificate_number": cert_number,
            "file_ref": file_path,
            "application_id": str(app.id),
            "tracking_id": app.tracking_id,
        }
