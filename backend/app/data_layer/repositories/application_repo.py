"""
Application Repository
CRUD for applications, application data (encrypted), documents, payments.
"""
import uuid
import datetime
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.db_models import (
    Application, ApplicationData, Document, Payment, Certificate
)
from app.data_layer.encryption import FieldEncryptor
from app.data_guard.guard import DataClassifier

logger = logging.getLogger(__name__)


def _gen_application_number(service_id: str) -> str:
    """Generate human-readable application number."""
    prefix_map = {
        "income_certificate": "IC",
        "caste_certificate": "CC",
        "obc_ncl_certificate": "OBC",
        "domicile_certificate": "DC",
    }
    prefix = prefix_map.get(service_id, "APP")
    now = datetime.datetime.utcnow()
    uid = str(uuid.uuid4())[:6].upper()
    return f"APP-{prefix}-{now.year}-{uid}"


class ApplicationRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        citizen_ref: str,
        service_id: str,
        channel_origin: str,
        language: str = "en",
    ) -> Application:
        """Create a new application in DRAFT status."""
        app = Application(
            application_number=_gen_application_number(service_id),
            citizen_ref=citizen_ref,
            service_id=service_id,
            status="DRAFT",
            channel_origin=channel_origin,
            language=language,
        )
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app

    def get_by_id(self, application_id: str) -> Optional[Application]:
        return self.db.query(Application).filter(Application.id == application_id).first()

    def get_by_number(self, application_number: str) -> Optional[Application]:
        return self.db.query(Application).filter(
            Application.application_number == application_number
        ).first()

    def get_by_citizen(self, citizen_ref: str, limit: int = 20) -> List[Application]:
        return (
            self.db.query(Application)
            .filter(Application.citizen_ref == citizen_ref)
            .order_by(Application.created_at.desc())
            .limit(limit)
            .all()
        )

    def update_status(self, application_id: str, status: str) -> Optional[Application]:
        app = self.get_by_id(application_id)
        if app:
            app.status = status
            if status == "SUBMITTED":
                app.submitted_at = datetime.datetime.utcnow()
            elif status in ("APPROVED", "REJECTED"):
                app.completed_at = datetime.datetime.utcnow()
            self.db.commit()
            self.db.refresh(app)
        return app

    def update_anomaly_score(self, application_id: str, score: float) -> None:
        app = self.get_by_id(application_id)
        if app:
            app.anomaly_score = score
            self.db.commit()

    def set_consent(self, application_id: str, consent: bool) -> None:
        app = self.get_by_id(application_id)
        if app:
            app.consent_given = consent
            self.db.commit()

    # ── Encrypted Field Storage ──

    def save_field(
        self,
        application_id: str,
        field_name: str,
        field_value: Any,
        classification: Optional[str] = None,
    ) -> ApplicationData:
        """Save an application form field with encryption for restricted data."""
        if classification is None:
            classification = DataClassifier.classify_field(field_name)

        # Encrypt RESTRICTED and QUASI_IDENTIFIER fields
        if classification in ("RESTRICTED", "QUASI_IDENTIFIER"):
            encrypted_value = FieldEncryptor.encrypt(str(field_value))
        else:
            encrypted_value = str(field_value)  # NON_SENSITIVE stored plaintext

        # Upsert: delete existing if present
        self.db.query(ApplicationData).filter(
            and_(
                ApplicationData.application_id == application_id,
                ApplicationData.field_name == field_name,
            )
        ).delete()

        data = ApplicationData(
            application_id=application_id,
            field_name=field_name,
            field_value_encrypted=encrypted_value,
            classification=classification,
        )
        self.db.add(data)
        self.db.commit()
        return data

    def get_fields(self, application_id: str, decrypt: bool = True) -> Dict[str, Any]:
        """Get all form fields for an application, decrypting where necessary."""
        fields = self.db.query(ApplicationData).filter(
            ApplicationData.application_id == application_id
        ).all()

        result = {}
        for f in fields:
            if decrypt and f.classification in ("RESTRICTED", "QUASI_IDENTIFIER"):
                try:
                    result[f.field_name] = FieldEncryptor.decrypt(f.field_value_encrypted)
                except Exception:
                    result[f.field_name] = "[ENCRYPTED]"
            else:
                result[f.field_name] = f.field_value_encrypted
        return result

    # ── Document Management ──

    def save_document(
        self,
        application_id: str,
        doc_type: str,
        file_ref: str,
        extracted_fields: Optional[Dict] = None,
        confidence_score: float = 1.0,
    ) -> Document:
        doc = Document(
            application_id=application_id,
            doc_type=doc_type,
            file_ref=file_ref,
            extracted_fields=extracted_fields or {},
            confidence_score=confidence_score,
            verification_status="PENDING",
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def update_document_verification(
        self, doc_id: str, status: str, mismatch_fields: Optional[List] = None
    ) -> Optional[Document]:
        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.verification_status = status
            doc.mismatch_fields = mismatch_fields or []
            self.db.commit()
        return doc

    # ── Payment Management ──

    def create_payment(
        self, application_id: str, amount: float, transaction_id: str, currency: str = "INR"
    ) -> Payment:
        payment = Payment(
            application_id=application_id,
            transaction_id=transaction_id,
            amount=amount,
            currency=currency,
            status="INITIATED",
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def update_payment_status(
        self, transaction_id: str, status: str, gateway_ref: Optional[str] = None
    ) -> Optional[Payment]:
        payment = self.db.query(Payment).filter(
            Payment.transaction_id == transaction_id
        ).first()
        if payment:
            payment.status = status
            payment.gateway_ref = gateway_ref
            self.db.commit()
            # Update parent application payment_status
            app = self.get_by_id(payment.application_id)
            if app:
                if status == "SUCCESS":
                    app.payment_status = "PAID"
                elif status == "FAILED":
                    app.payment_status = "FAILED"
                self.db.commit()
        return payment

    # ── Certificate Management ──

    def issue_certificate(self, application_id: str, file_ref: str, expiry_days: int = 365) -> Certificate:
        cert_number = f"CERT-{str(uuid.uuid4())[:8].upper()}"
        cert = Certificate(
            certificate_number=cert_number,
            application_id=application_id,
            file_ref=file_ref,
            expiry_date=datetime.datetime.utcnow() + datetime.timedelta(days=expiry_days),
        )
        self.db.add(cert)
        self.db.commit()
        self.db.refresh(cert)
        return cert

    # ── Dashboard Stats ──

    def get_submission_stats(self) -> Dict:
        """Application statistics for the dashboard."""
        today = datetime.datetime.utcnow().date()
        today_start = datetime.datetime(today.year, today.month, today.day)

        submitted_today = self.db.query(Application).filter(
            Application.submitted_at >= today_start
        ).count()

        by_status = {}
        for status in ["DRAFT", "SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED", "ESCALATED"]:
            by_status[status.lower()] = self.db.query(Application).filter(
                Application.status == status
            ).count()

        by_service = {}
        apps = self.db.query(Application.service_id).all()
        for (svc,) in apps:
            by_service[svc] = by_service.get(svc, 0) + 1

        return {
            "submitted_today": submitted_today,
            "by_status": by_status,
            "by_service": by_service,
        }

    def get_recent_applications(self, limit: int = 10) -> List[Dict]:
        apps = (
            self.db.query(Application)
            .order_by(Application.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": a.id,
                "application_number": a.application_number,
                "service_id": a.service_id,
                "status": a.status,
                "channel_origin": a.channel_origin,
                "language": a.language,
                "payment_status": a.payment_status,
                "anomaly_score": a.anomaly_score,
                "created_at": a.created_at.isoformat(),
            }
            for a in apps
        ]

    def count_recent_submissions(self, citizen_ref: str, hours: int) -> int:
        """Count recent submissions for fraud scoring."""
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
        return self.db.query(Application).filter(
            and_(
                Application.citizen_ref == citizen_ref,
                Application.submitted_at >= cutoff,
                Application.submitted_at.isnot(None),
            )
        ).count()
