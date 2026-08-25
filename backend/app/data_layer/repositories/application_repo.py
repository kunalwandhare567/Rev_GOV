"""
Application Repository
CRUD for applications, application data (encrypted), documents, payments.
Extended for omnichannel: tracking_id, field provenance, progress, cross-channel.
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


# Tracking ID prefix per service
SERVICE_TRACKING_PREFIXES = {
    "income_certificate": "INC",
    "caste_certificate": "CAS",
    "domicile_certificate": "DOM",
    "obc_ncl_certificate": "NCL",
    "age_certificate": "AGE",
    "birth_certificate": "BRT",
    "death_certificate": "DTH",
    "character_certificate": "CHR",
    "ration_card": "RAT",
    "land_record": "LND",
}

APPLICATION_PREFIXES = {
    "income_certificate": "IC",
    "caste_certificate": "CC",
    "obc_ncl_certificate": "OBC",
    "domicile_certificate": "DC",
}


def _gen_application_number(service_id: str) -> str:
    """Generate human-readable application number."""
    prefix = APPLICATION_PREFIXES.get(service_id, "APP")
    now = datetime.datetime.utcnow()
    uid = str(uuid.uuid4())[:6].upper()
    return f"APP-{prefix}-{now.year}-{uid}"


def _gen_tracking_id(service_id: str, db: Session) -> str:
    """Generate unique tracking ID: e.g. INC-2026-000001"""
    prefix = SERVICE_TRACKING_PREFIXES.get(service_id, "APP")
    year = datetime.datetime.utcnow().year
    # Count apps of this service this year for sequential numbering
    count = db.query(Application).filter(
        Application.service_id == service_id,
        Application.tracking_id.isnot(None),
    ).count()
    seq = count + 1
    return f"{prefix}-{year}-{seq:06d}"


class ApplicationRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        citizen_ref: str,
        service_id: str,
        channel_origin: str = "WEB",
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
        # Generate tracking ID immediately
        app.tracking_id = _gen_tracking_id(service_id, self.db)
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app

    def get_by_id(self, application_id: str) -> Optional[Application]:
        return self.db.query(Application).filter(Application.id == application_id).first()

    # alias for compatibility
    def get(self, application_id: str) -> Optional[Application]:
        return self.get_by_id(application_id)

    def get_by_number(self, application_number: str) -> Optional[Application]:
        return self.db.query(Application).filter(
            Application.application_number == application_number
        ).first()

    def get_by_tracking_id(self, tracking_id: str) -> Optional[Application]:
        return self.db.query(Application).filter(
            Application.tracking_id == tracking_id
        ).first()

    def get_by_citizen(self, citizen_ref: str, limit: int = 20) -> List[Application]:
        from app.data_layer.repositories.citizen_repo import CitizenRepository
        c_repo = CitizenRepository(self.db)
        c = c_repo.get_by_ref(citizen_ref) or c_repo.get_by_identifier(citizen_ref)
        refs = {citizen_ref}
        if c:
            refs.add(c.citizen_ref)
            if c.phone:
                refs.add(c.phone)
            if c.email:
                refs.add(c.email)

        return (
            self.db.query(Application)
            .filter(Application.citizen_ref.in_(refs))
            .order_by(Application.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_active_for_citizen(self, citizen_ref: str) -> Optional[Application]:
        """Get most recent non-terminal application for citizen (any service)."""
        terminal = {"COMPLETED", "REJECTED"}
        apps = self.get_by_citizen(citizen_ref)
        active = [a for a in apps if a.status not in terminal]
        return active[0] if active else None

    def get_active_by_citizen_service(
        self, citizen_ref: str, service_id: str
    ) -> Optional[Application]:
        """
        Phase 12 — Application Deduplication.
        Return the most recent non-terminal application for a specific citizen+service pair.
        Used by orchestrator to resume an existing application instead of creating a duplicate.
        """
        terminal = {"COMPLETED", "REJECTED"}
        app = (
            self.db.query(Application)
            .filter(
                and_(
                    Application.citizen_ref == citizen_ref,
                    Application.service_id == service_id,
                    Application.status.notin_(terminal),
                )
            )
            .order_by(Application.created_at.desc())
            .first()
        )
        return app

    def get_by_citizen_ref(
        self, citizen_ref: str, limit: int = 20
    ) -> List[Application]:
        """Alias for get_by_citizen — used by /applications/current endpoint."""
        return self.get_by_citizen(citizen_ref, limit=limit)

    def update_last_channel(self, application_id: str, channel: str) -> None:
        app = self.get_by_id(application_id)
        if app:
            app.last_channel = channel
            app.updated_at = datetime.datetime.utcnow()
            self.db.commit()

    def update_progress(self, application_id: str, progress_percent: int,
                        current_step: str = None) -> None:
        app = self.get_by_id(application_id)
        if app:
            app.progress_percent = min(100, max(0, progress_percent))
            if current_step:
                app.current_step = current_step
            app.updated_at = datetime.datetime.utcnow()
            self.db.commit()

    def update_validation_summary(self, application_id: str, summary: dict,
                                  overall_match_score: float = None) -> None:
        app = self.get_by_id(application_id)
        if app:
            app.validation_summary = summary
            if overall_match_score is not None:
                app.overall_match_score = overall_match_score
            app.updated_at = datetime.datetime.utcnow()
            self.db.commit()

    def update_status(self, application_id: str, status: str) -> Optional[Application]:
        app = self.get_by_id(application_id)
        if app:
            app.status = status
            now = datetime.datetime.utcnow()
            # Stamp submitted_at when entering any submission-related state
            if status in ("SUBMITTED", "SUBMITTED_FOR_VERIFICATION", "UNDER_REVIEW"):
                if not app.submitted_at:
                    app.submitted_at = now
            elif status in ("APPROVED", "REJECTED", "COMPLETED"):
                app.completed_at = now
            app.updated_at = now
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
        source: str = "WEB",
        confirmed: bool = False,
        override_reason: str = None,
    ) -> ApplicationData:
        """Save an application form field with encryption and field provenance."""
        if classification is None:
            classification = DataClassifier.classify_field(field_name)

        if isinstance(field_value, str):
            field_value = field_value.encode("utf-8", "replace").decode("utf-8")

        # Encrypt RESTRICTED and QUASI_IDENTIFIER fields
        if classification in ("RESTRICTED", "QUASI_IDENTIFIER"):
            encrypted_value = FieldEncryptor.encrypt(str(field_value))
        else:
            encrypted_value = str(field_value)  # NON_SENSITIVE stored plaintext

        # Upsert with version increment
        existing = self.db.query(ApplicationData).filter(
            and_(
                ApplicationData.application_id == application_id,
                ApplicationData.field_name == field_name,
            )
        ).first()

        if existing:
            existing.field_value_encrypted = encrypted_value
            existing.classification = classification
            existing.source = source
            existing.confirmed = confirmed
            existing.override_reason = override_reason
            existing.version = (existing.version or 1) + 1
            existing.updated_at = datetime.datetime.utcnow()
            self.db.commit()
            return existing

        data = ApplicationData(
            application_id=application_id,
            field_name=field_name,
            field_value_encrypted=encrypted_value,
            classification=classification,
            source=source,
            confirmed=confirmed,
            override_reason=override_reason,
            version=1,
        )
        self.db.add(data)
        self.db.commit()
        return data

    def get_fields_with_provenance(self, application_id: str) -> List[Dict]:
        """Get all fields including their source/provenance metadata."""
        fields = self.db.query(ApplicationData).filter(
            ApplicationData.application_id == application_id
        ).all()
        result = []
        for f in fields:
            try:
                if f.classification in ("RESTRICTED", "QUASI_IDENTIFIER"):
                    value = FieldEncryptor.decrypt(f.field_value_encrypted)
                else:
                    value = f.field_value_encrypted
            except Exception:
                value = "[ENCRYPTED]"
            result.append({
                "field_name": f.field_name,
                "value": value,
                "source": f.source,
                "confirmed": f.confirmed,
                "version": f.version,
                "classification": f.classification,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            })
        return result

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
        raw_ocr_text: Optional[str] = None,
        raw_extracted_fields: Optional[Dict] = None,
        normalized_fields: Optional[Dict] = None,
        normalization_status: Optional[str] = None,
        normalization_confidence: Optional[Dict] = None,
        overall_match_score: Optional[float] = None,
        matched_fields: Optional[List] = None,
        field_match_scores: Optional[Dict] = None,
        verification_status: Optional[str] = None,
    ) -> Document:
        """Create or update document record in SQLite (prevents duplicate document entries)."""
        doc = (
            self.db.query(Document)
            .filter(Document.application_id == application_id, Document.doc_type == doc_type)
            .first()
        )
        if not doc:
            doc = Document(
                application_id=application_id,
                doc_type=doc_type,
                file_ref=file_ref,
                extracted_fields=extracted_fields or {},
                confidence_score=confidence_score,
                verification_status=verification_status or "PENDING",
            )
            self.db.add(doc)
        else:
            doc.file_ref = file_ref
            doc.extracted_fields = extracted_fields or doc.extracted_fields or {}
            doc.confidence_score = confidence_score
            if verification_status:
                doc.verification_status = verification_status

        if raw_ocr_text is not None:
            doc.raw_ocr_text = raw_ocr_text
        if raw_extracted_fields is not None:
            doc.raw_extracted_fields = raw_extracted_fields
        if normalized_fields is not None:
            doc.normalized_fields = normalized_fields
        if normalization_status is not None:
            doc.normalization_status = normalization_status
        if normalization_confidence is not None:
            doc.normalization_confidence = normalization_confidence
        if overall_match_score is not None:
            doc.overall_match_score = overall_match_score
        if matched_fields is not None:
            doc.matched_fields = matched_fields
        if field_match_scores is not None:
            doc.field_match_scores = field_match_scores

        doc.updated_at = datetime.datetime.utcnow()
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def update_document_verification(
        self,
        doc_id: str,
        status: str,
        mismatch_fields: Optional[List] = None,
        matched_fields: Optional[List] = None,
        overall_match_score: Optional[float] = None,
        field_match_scores: Optional[Dict] = None,
    ) -> Optional[Document]:
        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.verification_status = status
            doc.mismatch_fields = mismatch_fields or []
            if matched_fields is not None:
                doc.matched_fields = matched_fields
            if overall_match_score is not None:
                doc.overall_match_score = overall_match_score
            if field_match_scores is not None:
                doc.field_match_scores = field_match_scores
            doc.updated_at = datetime.datetime.utcnow()
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
