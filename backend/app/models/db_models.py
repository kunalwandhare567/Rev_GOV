"""
SQLAlchemy Database Models — Extended for Omnichannel Platform
Maps to enterprise_architecture.md Section 5.6.1 schema.
All PII stored encrypted; citizen_ref is tokenized, never raw identifier.

NEW in v2:
- ChannelIdentity: maps phone/email/WhatsApp hashes → citizen_ref
- ApplicationEvent: lifecycle events for cross-channel sync & notifications
- IVRSession: tracks active IVR call sessions
- Extended Application: tracking_id, current_step, progress_percent, last_channel
- Extended ApplicationData: field provenance (source, confirmed, version)
- Extended Document: upload_channel, field_match_scores, overall_match_score
"""
import uuid
import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text,
    DateTime, JSON, ForeignKey, UniqueConstraint, Enum as SAEnum
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
    """System users: officers, admins, auditors, citizens."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, default="CITIZEN")  # CITIZEN | OFFICER | ADMIN | AUDITOR
    citizen_ref = Column(String(64), ForeignKey("citizens.citizen_ref"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    citizen = relationship("Citizen", foreign_keys=[citizen_ref])


# ─────────────────────────────────────────────
# CHANNEL IDENTITY
# Maps external channel identifiers → citizen_ref
# ─────────────────────────────────────────────

class ChannelIdentity(Base):
    """
    Maps external channel identifiers (phone, email, WhatsApp number) to citizen_ref.
    All identifiers stored as SHA-256 hashes — never plaintext.
    """
    __tablename__ = "channel_identities"

    id = Column(String(36), primary_key=True, default=_uuid)
    citizen_ref = Column(String(64), ForeignKey("citizens.citizen_ref"), nullable=False, index=True)
    channel = Column(String(32), nullable=False)          # WHATSAPP | WEB | MOBILE | IVR | EMAIL
    identifier_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of phone/email
    identifier_type = Column(String(32), nullable=False)  # PHONE | WHATSAPP_NUMBER | EMAIL | DEVICE_ID
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

    citizen = relationship("Citizen", back_populates="channel_identities")

    __table_args__ = (UniqueConstraint("channel", "identifier_hash"),)


# ─────────────────────────────────────────────
# CITIZENS
# ─────────────────────────────────────────────

class Citizen(Base):
    """
    Citizen registry. citizen_ref is a tokenized identifier (e.g. CIT-001).
    Identity linkage via ChannelIdentity table (hashed identifiers).
    """
    __tablename__ = "citizens"

    id = Column(String(36), primary_key=True, default=_uuid)
    citizen_ref = Column(String(64), unique=True, nullable=False, index=True)  # e.g. CIT-001

    name = Column(String(128), nullable=True)
    phone = Column(String(32), nullable=True, index=True)
    email = Column(String(128), nullable=True, index=True)
    address = Column(Text, nullable=True)

    preferred_language = Column(String(8), default="en")
    preferred_channel = Column(String(32), default="WEB")
    literacy_level = Column(String(16), default="MEDIUM")  # LOW | MEDIUM | HIGH

    # OTP for phone linking
    otp_hash = Column(String(64), nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    applications = relationship("Application", back_populates="citizen")
    sessions = relationship("ConversationSession", back_populates="citizen")
    channel_identities = relationship("ChannelIdentity", back_populates="citizen")

    @property
    def citizen_id(self) -> str:
        return self.citizen_ref


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
    name_mr = Column(String(256), nullable=True)   # NEW: Marathi
    name_ta = Column(String(256), nullable=True)
    name_te = Column(String(256), nullable=True)
    department = Column(String(128), default="Revenue Department")
    fee_amount = Column(Float, default=0.0)
    fee_currency = Column(String(8), default="INR")
    sla_days = Column(Integer, default=7)
    required_docs = Column(JSON, default=list)       # List of doc type strings
    waiver_conditions = Column(JSON, default=list)   # [{condition, waiver_percent}]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)


# ─────────────────────────────────────────────
# APPLICATIONS
# ─────────────────────────────────────────────

class Application(Base):
    """
    Core application record. No PII directly stored here.

    Full 14-state lifecycle:
    DRAFT → INFORMATION_COLLECTION → DOCUMENT_COLLECTION → OCR_VALIDATION →
    FINAL_REVIEW → READY_FOR_VERIFICATION → SUBMITTED_FOR_VERIFICATION →
    UNDER_REVIEW → CLARIFICATION_REQUIRED → APPROVED → PAYMENT_REQUIRED →
    PAYMENT_COMPLETED → FINAL_SUBMISSION → COMPLETED | REJECTED
    """
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=_uuid)
    application_number = Column(String(32), unique=True, nullable=False, index=True)
    tracking_id = Column(String(32), unique=True, nullable=True, index=True)  # e.g. INC-2026-000001

    citizen_ref = Column(String(64), ForeignKey("citizens.citizen_ref"), nullable=False, index=True)
    service_id = Column(String(64), ForeignKey("services.id"), nullable=False)

    # Full lifecycle status
    status = Column(String(48), default="DRAFT")
    current_step = Column(String(64), default="INIT")     # Orchestrator step within status

    # Channel tracking
    channel_origin = Column(String(32), nullable=False, default="WEB")  # WHATSAPP|IVR|WEB|MOBILE
    last_channel = Column(String(32), nullable=True)       # Most recent channel used

    language = Column(String(8), default="en")

    # Progress (0-100)
    progress_percent = Column(Integer, default=0)

    # OCR & Validation summary (cached at application level)
    overall_match_score = Column(Float, nullable=True)
    validation_summary = Column(JSON, default=dict)
    # {"all_docs_uploaded": bool, "all_docs_validated": bool, "unresolved_mismatches": int}

    payment_status = Column(String(32), default="PENDING")  # PENDING|PAID|WAIVED|FAILED
    anomaly_score = Column(Float, default=0.0)
    consent_given = Column(Boolean, default=False)

    # Lifecycle timestamps
    submitted_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
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
    events = relationship("ApplicationEvent", back_populates="application", cascade="all, delete-orphan")


class ApplicationData(Base):
    """
    Encrypted application form fields.
    classification: RESTRICTED | QUASI_IDENTIFIER | NON_SENSITIVE

    Field provenance tracks where each value came from.
    """
    __tablename__ = "application_data"

    id = Column(String(36), primary_key=True, default=_uuid)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    field_name = Column(String(128), nullable=False)
    field_value_encrypted = Column(Text, nullable=False)   # AES-256 encrypted, base64
    classification = Column(String(32), nullable=False)    # RESTRICTED | QUASI_IDENTIFIER | NON_SENSITIVE

    # Field provenance
    source = Column(String(32), default="WEB")
    # WEB | MOBILE | WHATSAPP_TEXT | WHATSAPP_VOICE | PHONE_VOICE | OCR | OFFICER | SYSTEM
    confirmed = Column(Boolean, default=False)             # Citizen explicitly confirmed
    override_reason = Column(Text, nullable=True)          # Why OCR vs declared resolved
    version = Column(Integer, default=1)                   # Increments on each update

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    application = relationship("Application", back_populates="data_fields")


# ─────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────

class Document(Base):
    """
    Document metadata. File stored on local filesystem (not cloud).
    Includes field-level OCR match scoring against ApplicationData.
    """
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    doc_type = Column(String(64), nullable=False)          # AADHAAR_CARD | INCOME_PROOF | etc.
    file_ref = Column(String(512), nullable=False)         # Local filesystem path

    # Upload channel tracking
    upload_channel = Column(String(32), default="WEB")     # WHATSAPP | WEB | MOBILE | IVR
    upload_source_ref = Column(String(256), nullable=True) # WhatsApp media_id or upload ref

    # OCR results
    extracted_fields = Column(JSON, default=dict)          # Raw OCR output (locally processed)
    confidence_score = Column(Float, default=1.0)

    # Field-level match scoring against ApplicationData
    field_match_scores = Column(JSON, default=dict)
    # {"full_name": {"app_value": "...", "ocr_value": "...", "score": 87.0, "match": false},
    #  "dob": {"app_value": "...", "ocr_value": "...", "score": 100.0, "match": true}}

    overall_match_score = Column(Float, nullable=True)     # e.g. 93.0

    # Verification status
    verification_status = Column(String(32), default="PENDING")
    # PENDING | OCR_PROCESSING | VALIDATING | MATCHED | REVIEW_REQUIRED | VALIDATION_FAILED

    mismatch_fields = Column(JSON, default=list)           # List of field names with mismatch
    mismatch_resolutions = Column(JSON, default=dict)
    # {field_name: "USE_OCR" | "USE_APPLICATION" | "MANUAL"}

    ocr_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    application = relationship("Application", back_populates="documents")


# ─────────────────────────────────────────────
# APPLICATION EVENTS
# ─────────────────────────────────────────────

class ApplicationEvent(Base):
    """
    Application lifecycle events.
    Used for cross-channel synchronization and notification dispatch.
    Persisted so notifications can be retried if WhatsApp/push fails.
    """
    __tablename__ = "application_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    citizen_ref = Column(String(64), nullable=False, index=True)

    event_type = Column(String(64), nullable=False)
    # APPLICATION_CREATED | FIELD_UPDATED | DOCUMENT_UPLOADED | OCR_STARTED |
    # OCR_COMPLETED | VALIDATION_COMPLETED | MISMATCH_DETECTED | MISMATCH_RESOLVED |
    # READY_FOR_REVIEW | REVIEW_CONFIRMED | SUBMITTED_FOR_VERIFICATION |
    # VERIFICATION_STATUS_CHANGED | CLARIFICATION_REQUIRED | APPROVED |
    # PAYMENT_REQUIRED | PAYMENT_COMPLETED | FINAL_SUBMISSION | APPLICATION_COMPLETED

    source_channel = Column(String(32), nullable=False, default="SYSTEM")
    event_data = Column(JSON, default=dict)                # No PII values

    notification_sent = Column(Boolean, default=False)
    notification_channel = Column(String(32), nullable=True)
    notification_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_now)

    application = relationship("Application", back_populates="events")


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
    method = Column(String(32), nullable=True)  # UPI | CARD | NETBANKING | CHALLAN | SIMULATED
    status = Column(String(32), default="INITIATED")  # INITIATED|SUCCESS|FAILED|REFUNDED
    gateway = Column(String(64), nullable=True)
    gateway_ref = Column(String(256), nullable=True)

    # Receipt OCR (if citizen uploads payment screenshot)
    receipt_file_ref = Column(String(512), nullable=True)
    receipt_extracted_fields = Column(JSON, default=dict)
    receipt_validated = Column(Boolean, default=False)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

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
    channel_history = Column(JSON, default=list)   # [{channel, switched_at}]
    pending_question = Column(Text, nullable=True)  # Last AI question asked (for state resume)
    pending_field = Column(String(128), nullable=True)  # Field being collected currently
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    citizen = relationship("Citizen", back_populates="sessions")


class ConversationMessage(Base):
    """Individual messages in a conversation session."""
    __tablename__ = "conversation_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("conversation_sessions.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)   # USER | ASSISTANT | SYSTEM
    content = Column(Text, nullable=False)
    language = Column(String(8), default="en")
    modality = Column(String(16), default="TEXT")    # TEXT | VOICE | DTMF | DOCUMENT
    audio_ref = Column(String(512), nullable=True)   # Local audio file ref
    classification = Column(String(32), default="NON_SENSITIVE")
    created_at = Column(DateTime, default=_now)


# ─────────────────────────────────────────────
# IVR SESSIONS
# ─────────────────────────────────────────────

class IVRSession(Base):
    """Tracks active IVR call sessions (phone helpline simulator)."""
    __tablename__ = "ivr_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    call_id = Column(String(128), unique=True, nullable=False)
    citizen_ref = Column(String(64), nullable=True, index=True)   # Null until resolved
    caller_phone_hash = Column(String(64), nullable=False)
    application_id = Column(String(36), nullable=True)
    current_state = Column(String(64), default="GREETING")
    # GREETING | LANGUAGE_SELECT | IDENTIFY | MAIN_MENU | STATUS_CHECK |
    # TRACKING | PAYMENT_STATUS | CLARIFICATION | FAREWELL
    language = Column(String(8), default="en")
    call_duration_seconds = Column(Integer, default=0)
    resolution_type = Column(String(32), nullable=True)  # STATUS | TRACKING | PAYMENT | CLARIFICATION
    call_status = Column(String(32), default="ACTIVE")   # ACTIVE | COMPLETED | DROPPED
    conversation_log = Column(JSON, default=list)         # [{role, text, timestamp}]
    created_at = Column(DateTime, default=_now)
    ended_at = Column(DateTime, nullable=True)


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
    priority = Column(String(16), default="MEDIUM")   # LOW | MEDIUM | HIGH | CRITICAL
    status = Column(String(32), default="OPEN")        # OPEN | ASSIGNED | RESOLVED | CLOSED
    assigned_officer_id = Column(String(36), nullable=True)
    officer_summary = Column(Text, nullable=True)      # RAG-generated handoff summary
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
    file_ref = Column(String(512), nullable=False)    # Local filesystem path
    issue_date = Column(DateTime, default=_now)
    expiry_date = Column(DateTime, nullable=True)
    qr_data = Column(Text, nullable=True)             # QR code verification data
    created_at = Column(DateTime, default=_now)

    application = relationship("Application", back_populates="certificate")


# ─────────────────────────────────────────────
# AUDIT LOG (Immutable — append-only by convention)
# ─────────────────────────────────────────────

class AuditLog(Base):
    """
    Immutable audit trail (enterprise_architecture.md Section 5.6.1).
    Every Data Guard decision, consent, payment, submission logged here.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False, index=True)  # DATA_GUARD|CONSENT|PAYMENT|SUBMISSION|AUTH
    actor = Column(String(128), nullable=False)        # Service name or user ID
    citizen_ref = Column(String(64), nullable=True, index=True)   # Tokenized, never raw PII
    application_id = Column(String(36), nullable=True, index=True)
    action = Column(Text, nullable=False)              # Verbose description
    outcome = Column(String(32), nullable=False)       # ALLOW | BLOCK | SUCCESS | FAILURE
    blocked_fields = Column(JSON, default=list)
    metadata_json = Column(JSON, default=dict)         # Event-specific details (NO PII values)
    payload_hash = Column(String(64), nullable=True)
    previous_hash = Column(String(64), nullable=True)  # Chain of custody
    created_at = Column(DateTime, default=_now)
    # NOTE: No update/delete operations on this table
