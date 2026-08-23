"""
SQLAlchemy Database Models
Maps to enterprise_architecture.md Section 5.6.1 schema.
All PII stored encrypted; citizen_ref is tokenized, never raw identifier.
"""
import uuid
import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text,
    DateTime, JSON, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.datetime.utcnow()


# ─────────────────────────────────────────────
# USERS & AUTH
# ─────────────────────────────────────────────

class User(Base):
    """System users: officers, admins, auditors."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, default="CITIZEN")  # CITIZEN | OFFICER | ADMIN | AUDITOR
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ─────────────────────────────────────────────
# CITIZENS (tokenized — no raw PII in this row)
# ─────────────────────────────────────────────

class Citizen(Base):
    """
    Citizen registry. citizen_ref is a tokenized identifier.
    Raw PII (name, Aadhaar, phone) is stored ENCRYPTED in ApplicationData.
    """
    __tablename__ = "citizens"

    id = Column(String(36), primary_key=True, default=_uuid)
    citizen_ref = Column(String(64), unique=True, nullable=False, index=True)  # Token, not raw ID
    preferred_language = Column(String(8), default="en")
    preferred_channel = Column(String(32), default="WEB")
    literacy_level = Column(String(16), default="MEDIUM")  # LOW | MEDIUM | HIGH
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    applications = relationship("Application", back_populates="citizen")
    sessions = relationship("ConversationSession", back_populates="citizen")


# ─────────────────────────────────────────────
# SERVICE CATALOGUE (25+ services loaded from YAML)
# ─────────────────────────────────────────────

class Service(Base):
    """
    Registry of all certificate services.
    Spec details (slots, validation, eligibility) live in YAML files.
    This table is seeded from those YAML files.
    """
    __tablename__ = "services"

    id = Column(String(64), primary_key=True)  # e.g. "income_certificate"
    name_en = Column(String(128), nullable=False)
    name_hi = Column(String(256), nullable=True)
    name_ta = Column(String(256), nullable=True)
    name_te = Column(String(256), nullable=True)
    department = Column(String(128), default="Revenue Department")
    fee_amount = Column(Float, default=0.0)
    fee_currency = Column(String(8), default="INR")
    sla_days = Column(Integer, default=7)
    required_docs = Column(JSON, default=list)      # List of doc type strings
    waiver_conditions = Column(JSON, default=list)  # [{condition, waiver_percent}]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)


# ─────────────────────────────────────────────
# APPLICATIONS
# ─────────────────────────────────────────────

class Application(Base):
    """Core application record. No PII directly stored here."""
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=_uuid)
    application_number = Column(String(32), unique=True, nullable=False, index=True)
    citizen_ref = Column(String(64), ForeignKey("citizens.citizen_ref"), nullable=False, index=True)
    service_id = Column(String(64), ForeignKey("services.id"), nullable=False)
    status = Column(String(32), default="DRAFT")  # DRAFT|SUBMITTED|UNDER_REVIEW|APPROVED|REJECTED|ESCALATED
    channel_origin = Column(String(32), nullable=False)  # WHATSAPP|IVR|WEB|MOBILE
    language = Column(String(8), default="en")
    payment_status = Column(String(32), default="PENDING")  # PENDING|PAID|WAIVED|FAILED
    anomaly_score = Column(Float, default=0.0)
    consent_given = Column(Boolean, default=False)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    citizen = relationship("Citizen", back_populates="applications")
    service = relationship("Service")
    data_fields = relationship("ApplicationData", back_populates="application", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="application", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="application", cascade="all, delete-orphan")
    certificate = relationship("Certificate", back_populates="application", uselist=False)


class ApplicationData(Base):
    """
    Encrypted application form fields.
    classification: RESTRICTED | QUASI_IDENTIFIER | NON_SENSITIVE
    """
    __tablename__ = "application_data"

    id = Column(String(36), primary_key=True, default=_uuid)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    field_name = Column(String(128), nullable=False)
    field_value_encrypted = Column(Text, nullable=False)  # AES-256 encrypted, base64
    classification = Column(String(32), nullable=False)   # RESTRICTED | QUASI_IDENTIFIER | NON_SENSITIVE
    created_at = Column(DateTime, default=_now)

    application = relationship("Application", back_populates="data_fields")


# ─────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────

class Document(Base):
    """Document metadata. File stored on local filesystem (not cloud)."""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    doc_type = Column(String(64), nullable=False)  # IDENTITY_PROOF | INCOME_PROOF | etc.
    file_ref = Column(String(512), nullable=False)  # Local filesystem path (encrypted filename)
    extracted_fields = Column(JSON, default=dict)   # OCR output (stored locally, never sent to cloud)
    confidence_score = Column(Float, default=1.0)
    verification_status = Column(String(32), default="PENDING")  # PENDING|VERIFIED|MISMATCH|FAILED
    mismatch_fields = Column(JSON, default=list)   # Fields where OCR differs from declared data
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    application = relationship("Application", back_populates="documents")


# ─────────────────────────────────────────────
# PAYMENTS
# ─────────────────────────────────────────────

class Payment(Base):
    """Payment transaction records."""
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=_uuid)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    transaction_id = Column(String(128), unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(8), default="INR")
    method = Column(String(32), nullable=True)  # UPI | CARD | NETBANKING | CHALLAN
    status = Column(String(32), default="INITIATED")  # INITIATED|SUCCESS|FAILED|REFUNDED
    gateway = Column(String(64), nullable=True)
    gateway_ref = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=_now)

    application = relationship("Application", back_populates="payments")


# ─────────────────────────────────────────────
# CONVERSATION SESSIONS (Context Vault)
# ─────────────────────────────────────────────

class ConversationSession(Base):
    """
    Channel-agnostic conversation state (Context Vault).
    Keyed by citizen_ref, not channel-specific session ID.
    Enables seamless channel switching (WhatsApp → IVR → Web).
    """
    __tablename__ = "conversation_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    citizen_ref = Column(String(64), ForeignKey("citizens.citizen_ref"), nullable=False, index=True)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=True)
    current_node = Column(String(64), default="INIT")
    channel = Column(String(32), default="WEB")
    language = Column(String(8), default="en")
    literacy_level = Column(String(16), default="MEDIUM")
    filled_slots = Column(JSON, default=dict)
    missing_slots = Column(JSON, default=list)
    validation_errors = Column(JSON, default=list)
    correction_history = Column(JSON, default=list)
    document_refs = Column(JSON, default=list)
    payment_status = Column(String(32), default="PENDING")
    consent_given = Column(Boolean, default=False)
    anomaly_score = Column(Float, default=0.0)
    escalation_reason = Column(Text, nullable=True)
    channel_history = Column(JSON, default=list)  # List of channels used
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    citizen = relationship("Citizen", back_populates="sessions")


class ConversationMessage(Base):
    """Individual messages in a conversation session."""
    __tablename__ = "conversation_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("conversation_sessions.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # USER | ASSISTANT | SYSTEM
    content = Column(Text, nullable=False)
    language = Column(String(8), default="en")
    modality = Column(String(16), default="TEXT")  # TEXT | VOICE | DTMF
    audio_ref = Column(String(512), nullable=True)  # Local audio file ref
    classification = Column(String(32), default="NON_SENSITIVE")
    created_at = Column(DateTime, default=_now)


# ─────────────────────────────────────────────
# ESCALATIONS
# ─────────────────────────────────────────────

class Escalation(Base):
    """Human officer escalation tickets."""
    __tablename__ = "escalations"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(String(32), unique=True, nullable=False, index=True)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    priority = Column(String(16), default="MEDIUM")  # LOW | MEDIUM | HIGH | CRITICAL
    status = Column(String(32), default="OPEN")  # OPEN | ASSIGNED | RESOLVED | CLOSED
    assigned_officer_id = Column(String(36), nullable=True)
    officer_summary = Column(Text, nullable=True)  # RAG-generated handoff summary
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    application = relationship("Application", back_populates="escalations")


# ─────────────────────────────────────────────
# CERTIFICATES
# ─────────────────────────────────────────────

class Certificate(Base):
    """Issued certificate records."""
    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=_uuid)
    certificate_number = Column(String(32), unique=True, nullable=False, index=True)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, unique=True)
    file_ref = Column(String(512), nullable=False)  # Local filesystem path
    issue_date = Column(DateTime, default=_now)
    expiry_date = Column(DateTime, nullable=True)
    qr_data = Column(Text, nullable=True)  # QR code verification data
    created_at = Column(DateTime, default=_now)

    application = relationship("Application", back_populates="certificate")


# ─────────────────────────────────────────────
# AUDIT LOG (Immutable — append-only by convention)
# ─────────────────────────────────────────────

class AuditLog(Base):
    """
    Immutable audit trail (enterprise_architecture.md Section 5.6.1).
    Separate from operational logs.
    Every Data Guard decision, consent, payment, submission logged here.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False, index=True)  # DATA_GUARD|CONSENT|PAYMENT|SUBMISSION|AUTH
    actor = Column(String(128), nullable=False)    # Service name or user ID
    citizen_ref = Column(String(64), nullable=True, index=True)  # Tokenized, never raw PII
    application_id = Column(String(36), nullable=True, index=True)
    action = Column(Text, nullable=False)          # Verbose description
    outcome = Column(String(32), nullable=False)   # ALLOW | BLOCK | SUCCESS | FAILURE
    blocked_fields = Column(JSON, default=list)    # Fields blocked by Data Guard
    metadata_json = Column(JSON, default=dict)     # Event-specific details (NO PII values)
    payload_hash = Column(String(64), nullable=True)  # SHA-256 of blocked payload
    previous_hash = Column(String(64), nullable=True)  # Chain of custody
    created_at = Column(DateTime, default=_now)
    # NOTE: No update/delete operations on this table — enforced at repository layer
