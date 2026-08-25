"""
Document Repository — manages documents and OCR results
"""
import datetime
from sqlalchemy.orm import Session
from app.models.db_models import Document


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, application_id: str, doc_type: str, file_ref: str,
               upload_channel: str = "WEB", upload_source_ref: str = None,
               raw_ocr_text: str = None, raw_extracted_fields: dict = None,
               normalized_fields: dict = None, normalization_status: str = None,
               normalization_confidence: dict = None) -> Document:
        doc = self.get_by_type(application_id, doc_type)
        if not doc:
            doc = Document(
                application_id=application_id,
                doc_type=doc_type,
                file_ref=file_ref,
                upload_channel=upload_channel,
                upload_source_ref=upload_source_ref,
                verification_status="PENDING",
            )
            self.db.add(doc)
        else:
            doc.file_ref = file_ref
            doc.upload_channel = upload_channel
            if upload_source_ref:
                doc.upload_source_ref = upload_source_ref

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

        doc.updated_at = datetime.datetime.utcnow()
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get(self, doc_id: str) -> Document | None:
        return self.db.query(Document).filter(Document.id == doc_id).first()

    def get_by_application(self, application_id: str) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(Document.application_id == application_id)
            .order_by(Document.created_at)
            .all()
        )

    def get_by_type(self, application_id: str, doc_type: str) -> Document | None:
        return (
            self.db.query(Document)
            .filter(
                Document.application_id == application_id,
                Document.doc_type == doc_type,
            )
            .first()
        )

    def update_status(self, doc_id: str, status: str) -> Document | None:
        doc = self.get(doc_id)
        if doc:
            doc.verification_status = status
            doc.updated_at = datetime.datetime.utcnow()
            self.db.commit()
        return doc

    def update_ocr_result(self, doc_id: str, extracted_fields: dict,
                          confidence_score: float, raw_ocr_text: str = None,
                          raw_extracted_fields: dict = None,
                          normalized_fields: dict = None,
                          normalization_status: str = None,
                          normalization_confidence: dict = None) -> Document | None:
        doc = self.get(doc_id)
        if doc:
            doc.extracted_fields = extracted_fields
            doc.confidence_score = confidence_score
            doc.verification_status = "VALIDATING"
            doc.ocr_completed_at = datetime.datetime.utcnow()
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
            doc.updated_at = datetime.datetime.utcnow()
            self.db.commit()
        return doc

    def update_match_scores(self, doc_id: str, field_match_scores: dict,
                            overall_match_score: float, mismatch_fields: list,
                            matched_fields: list = None,
                            verification_status: str = None) -> Document | None:
        doc = self.get(doc_id)
        if doc:
            doc.field_match_scores = field_match_scores
            doc.overall_match_score = overall_match_score
            doc.mismatch_fields = mismatch_fields
            if matched_fields is not None:
                doc.matched_fields = matched_fields
            doc.verification_status = verification_status or ("REVIEW_REQUIRED" if mismatch_fields else "VERIFIED")
            doc.updated_at = datetime.datetime.utcnow()
            self.db.commit()
        return doc

    def resolve_mismatch(self, doc_id: str, field: str, resolution: str) -> Document | None:
        """resolution: USE_OCR | USE_APPLICATION | MANUAL"""
        doc = self.get(doc_id)
        if doc:
            resolutions = doc.mismatch_resolutions or {}
            resolutions[field] = resolution
            doc.mismatch_resolutions = resolutions

            # Check if all mismatches resolved
            unresolved = [f for f in (doc.mismatch_fields or []) if f not in resolutions]
            if not unresolved:
                doc.verification_status = "MATCHED"

            doc.updated_at = datetime.datetime.utcnow()
            self.db.commit()
        return doc

    def all_mismatches_resolved(self, doc_id: str) -> bool:
        doc = self.get(doc_id)
        if not doc:
            return True
        unresolved = [f for f in (doc.mismatch_fields or []) if f not in (doc.mismatch_resolutions or {})]
        return len(unresolved) == 0

    def update_document_verification(
        self, doc_id: str, status: str, mismatch_fields: list
    ) -> Document | None:
        """Update verification status and mismatch fields after matching."""
        doc = self.get(doc_id)
        if doc:
            doc.verification_status = status
            doc.mismatch_fields = mismatch_fields or []
            doc.updated_at = datetime.datetime.utcnow()
            self.db.commit()
        return doc

    def update_doc_type(self, doc_id: str, doc_type: str) -> Document | None:
        """Update the detected document type (auto-detected by OCR)."""
        doc = self.get(doc_id)
        if doc:
            doc.doc_type = doc_type
            doc.updated_at = datetime.datetime.utcnow()
            self.db.commit()
        return doc
