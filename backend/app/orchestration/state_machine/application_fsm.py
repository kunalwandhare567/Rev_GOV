"""
Phase 2 — Application Lifecycle FSM (v3.0 — Correct State Order)

CRITICAL FIX: Payment now correctly occurs AFTER government approval.
Old (wrong): OCR → payment → submit → review → approved
New (correct): OCR → validate → readiness → review → consent → submit → review → APPROVE → PAYMENT

States implemented per impl3.md §9-§10:
  INITIATED → CONSENT_GIVEN → SERVICE_SELECTED → INFORMATION_COLLECTION →
  DOCUMENT_COLLECTION → OCR_PROCESSING → VALIDATION_COMPLETED →
  READINESS_CHECK → (FIX_REQUIRED ↔ READINESS_CHECK) → READY_FOR_REVIEW →
  FINAL_REVIEW → CONSENT_CONFIRMED → SUBMITTED_FOR_VERIFICATION →
  UNDER_REVIEW → CLARIFICATION_REQUIRED / APPROVED / REJECTED →
  PAYMENT_REQUIRED → PAYMENT_COMPLETED →
  CERTIFICATE_GENERATION → CERTIFICATE_READY → COMPLETED

Officer persona removed. ESCALATED removed. PENDING_OFFICER_PRE_APPROVAL removed.
"""
import logging
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AppState(str, Enum):
    # ── Initiation ──
    INITIATED                   = "INITIATED"
    CONSENT_GIVEN               = "CONSENT_GIVEN"       # Citizen agreed to platform T&C
    SERVICE_SELECTED            = "SERVICE_SELECTED"

    # ── Data Collection ──
    INFORMATION_COLLECTION      = "INFORMATION_COLLECTION"   # Slot filling in progress
    DOCUMENT_COLLECTION         = "DOCUMENT_COLLECTION"      # Documents being uploaded

    # ── Validation ──
    OCR_PROCESSING              = "OCR_PROCESSING"           # OCR running
    VALIDATION_COMPLETED        = "VALIDATION_COMPLETED"     # OCR done, match calculated

    # ── Readiness ──
    READINESS_CHECK             = "READINESS_CHECK"          # Computing readiness score
    FIX_REQUIRED                = "FIX_REQUIRED"             # Score < 75, needs correction
    READY_FOR_REVIEW            = "READY_FOR_REVIEW"         # Score ≥ 75, ready to submit

    # ── Citizen Final Review ──
    FINAL_REVIEW                = "FINAL_REVIEW"             # Citizen opens 4-section web form
    CONSENT_CONFIRMED           = "CONSENT_CONFIRMED"        # Citizen checked consent checkbox

    # ── Government Submission & Review ──
    SUBMITTED_FOR_VERIFICATION  = "SUBMITTED_FOR_VERIFICATION"
    UNDER_REVIEW                = "UNDER_REVIEW"
    CLARIFICATION_REQUIRED      = "CLARIFICATION_REQUIRED"  # Admin requested more info

    # ── Decision ──
    APPROVED                    = "APPROVED"
    REJECTED                    = "REJECTED"

    # ── Payment (ONLY AFTER APPROVAL) ──
    PAYMENT_REQUIRED            = "PAYMENT_REQUIRED"        # ← triggered only by APPROVED
    PAYMENT_COMPLETED           = "PAYMENT_COMPLETED"

    # ── Certificate ──
    CERTIFICATE_GENERATION      = "CERTIFICATE_GENERATION"  # PDF being generated
    CERTIFICATE_READY           = "CERTIFICATE_READY"
    COMPLETED                   = "COMPLETED"               # Full terminal state


# ─────────────────────────────────────────────
# Progress percentage per state (for UI progress bar)
# ─────────────────────────────────────────────
STATE_PROGRESS: Dict[str, int] = {
    AppState.INITIATED:                     3,
    AppState.CONSENT_GIVEN:                 8,
    AppState.SERVICE_SELECTED:              12,
    AppState.INFORMATION_COLLECTION:        25,
    AppState.DOCUMENT_COLLECTION:           38,
    AppState.OCR_PROCESSING:               48,
    AppState.VALIDATION_COMPLETED:          55,
    AppState.READINESS_CHECK:              60,
    AppState.FIX_REQUIRED:                 57,
    AppState.READY_FOR_REVIEW:             65,
    AppState.FINAL_REVIEW:                 70,
    AppState.CONSENT_CONFIRMED:            73,
    AppState.SUBMITTED_FOR_VERIFICATION:   78,
    AppState.UNDER_REVIEW:                 83,
    AppState.CLARIFICATION_REQUIRED:       80,
    AppState.APPROVED:                     88,
    AppState.REJECTED:                     100,
    AppState.PAYMENT_REQUIRED:             90,
    AppState.PAYMENT_COMPLETED:            93,
    AppState.CERTIFICATE_GENERATION:       96,
    AppState.CERTIFICATE_READY:            99,
    AppState.COMPLETED:                    100,
}


# ─────────────────────────────────────────────
# Valid transitions: from_state → [allowed to_states]
# RULE: PAYMENT only reachable from APPROVED — never from any other state.
# ─────────────────────────────────────────────
VALID_TRANSITIONS: Dict[str, List[str]] = {
    AppState.INITIATED: [
        AppState.CONSENT_GIVEN,
    ],
    AppState.CONSENT_GIVEN: [
        AppState.SERVICE_SELECTED,
        AppState.INITIATED,         # Citizen revoked consent
    ],
    AppState.SERVICE_SELECTED: [
        AppState.INFORMATION_COLLECTION,
    ],
    AppState.INFORMATION_COLLECTION: [
        AppState.INFORMATION_COLLECTION,   # Self-loop: more slots to fill
        AppState.DOCUMENT_COLLECTION,      # All slots done
        AppState.SERVICE_SELECTED,         # Citizen changed service
    ],
    AppState.DOCUMENT_COLLECTION: [
        AppState.DOCUMENT_COLLECTION,      # More docs to upload
        AppState.OCR_PROCESSING,           # All docs uploaded
        AppState.INFORMATION_COLLECTION,   # Clarification required slots
    ],
    AppState.OCR_PROCESSING: [
        AppState.VALIDATION_COMPLETED,     # OCR succeeded
        AppState.DOCUMENT_COLLECTION,      # OCR failed — re-upload required
    ],
    AppState.VALIDATION_COMPLETED: [
        AppState.READINESS_CHECK,
    ],
    AppState.READINESS_CHECK: [
        AppState.READY_FOR_REVIEW,         # Score ≥ 75
        AppState.FIX_REQUIRED,             # Score < 75
    ],
    AppState.FIX_REQUIRED: [
        AppState.INFORMATION_COLLECTION,   # Fix missing fields
        AppState.DOCUMENT_COLLECTION,      # Fix documents
        AppState.READINESS_CHECK,          # Re-check after fix
    ],
    AppState.READY_FOR_REVIEW: [
        AppState.FINAL_REVIEW,             # Citizen opens 4-section form
        AppState.FIX_REQUIRED,             # Citizen wants to edit something
    ],
    AppState.FINAL_REVIEW: [
        AppState.CONSENT_CONFIRMED,        # Citizen checked consent
        AppState.FIX_REQUIRED,             # Citizen found issue in review
        AppState.INFORMATION_COLLECTION,   # Edit basic details
        AppState.DOCUMENT_COLLECTION,      # Edit documents
    ],
    AppState.CONSENT_CONFIRMED: [
        AppState.SUBMITTED_FOR_VERIFICATION,
    ],
    AppState.SUBMITTED_FOR_VERIFICATION: [
        AppState.UNDER_REVIEW,
    ],
    AppState.UNDER_REVIEW: [
        AppState.APPROVED,
        AppState.REJECTED,
        AppState.CLARIFICATION_REQUIRED,
    ],
    AppState.CLARIFICATION_REQUIRED: [
        AppState.INFORMATION_COLLECTION,   # Need more info from citizen
        AppState.DOCUMENT_COLLECTION,      # Need more documents
        AppState.SUBMITTED_FOR_VERIFICATION,  # Citizen resubmitted after clarification
    ],
    AppState.APPROVED: [
        AppState.PAYMENT_REQUIRED,         # ONLY path to payment — through approval
    ],
    AppState.REJECTED: [],                 # Terminal
    AppState.PAYMENT_REQUIRED: [
        AppState.PAYMENT_COMPLETED,
    ],
    AppState.PAYMENT_COMPLETED: [
        AppState.CERTIFICATE_GENERATION,
    ],
    AppState.CERTIFICATE_GENERATION: [
        AppState.CERTIFICATE_READY,
    ],
    AppState.CERTIFICATE_READY: [
        AppState.COMPLETED,
    ],
    AppState.COMPLETED: [],               # Terminal
}


# ─────────────────────────────────────────────
# Human-readable transition labels
# ─────────────────────────────────────────────
TRANSITION_LABELS: Dict[str, str] = {
    "INITIATED→CONSENT_GIVEN":                              "Citizen agreed to platform terms",
    "CONSENT_GIVEN→SERVICE_SELECTED":                       "Service selected",
    "SERVICE_SELECTED→INFORMATION_COLLECTION":              "Data collection started",
    "INFORMATION_COLLECTION→DOCUMENT_COLLECTION":           "All fields collected — documents requested",
    "INFORMATION_COLLECTION→INFORMATION_COLLECTION":        "Collecting next field",
    "DOCUMENT_COLLECTION→OCR_PROCESSING":                   "Documents uploaded — OCR started",
    "OCR_PROCESSING→VALIDATION_COMPLETED":                  "OCR completed — validation done",
    "OCR_PROCESSING→DOCUMENT_COLLECTION":                   "OCR failed — document re-upload required",
    "VALIDATION_COMPLETED→READINESS_CHECK":                 "Computing readiness score",
    "READINESS_CHECK→READY_FOR_REVIEW":                     "Readiness ≥75 — ready to submit",
    "READINESS_CHECK→FIX_REQUIRED":                         "Readiness <75 — corrections needed",
    "FIX_REQUIRED→INFORMATION_COLLECTION":                  "Citizen correcting field information",
    "FIX_REQUIRED→DOCUMENT_COLLECTION":                     "Citizen re-uploading documents",
    "FIX_REQUIRED→READINESS_CHECK":                         "Re-checking readiness after fix",
    "READY_FOR_REVIEW→FINAL_REVIEW":                        "Citizen opened final review",
    "FINAL_REVIEW→CONSENT_CONFIRMED":                       "Citizen confirmed consent",
    "FINAL_REVIEW→FIX_REQUIRED":                            "Citizen requested edit during review",
    "CONSENT_CONFIRMED→SUBMITTED_FOR_VERIFICATION":         "Application submitted for government verification",
    "SUBMITTED_FOR_VERIFICATION→UNDER_REVIEW":              "Government received application",
    "UNDER_REVIEW→APPROVED":                                "Government approved application",
    "UNDER_REVIEW→REJECTED":                                "Government rejected application",
    "UNDER_REVIEW→CLARIFICATION_REQUIRED":                  "Government requested clarification",
    "CLARIFICATION_REQUIRED→INFORMATION_COLLECTION":        "Citizen providing additional information",
    "CLARIFICATION_REQUIRED→DOCUMENT_COLLECTION":           "Citizen uploading additional documents",
    "CLARIFICATION_REQUIRED→SUBMITTED_FOR_VERIFICATION":    "Resubmitted after clarification",
    "APPROVED→PAYMENT_REQUIRED":                            "Application approved — payment required",  # ← correct
    "PAYMENT_REQUIRED→PAYMENT_COMPLETED":                   "Payment received",
    "PAYMENT_COMPLETED→CERTIFICATE_GENERATION":             "Certificate being generated",
    "CERTIFICATE_GENERATION→CERTIFICATE_READY":             "Certificate ready for download",
    "CERTIFICATE_READY→COMPLETED":                          "Application completed",
    "UNDER_REVIEW→ESCALATED":                               "INVALID — use CLARIFICATION_REQUIRED instead",
}

# ─────────────────────────────────────────────
# States where citizen cannot modify application
# ─────────────────────────────────────────────
LOCKED_STATES = {
    AppState.SUBMITTED_FOR_VERIFICATION,
    AppState.UNDER_REVIEW,
    AppState.CLARIFICATION_REQUIRED,
    AppState.APPROVED,
    AppState.PAYMENT_REQUIRED,
    AppState.PAYMENT_COMPLETED,
    AppState.CERTIFICATE_GENERATION,
    AppState.CERTIFICATE_READY,
    AppState.COMPLETED,
    AppState.REJECTED,
}


class ApplicationFSM:
    """
    Application Lifecycle FSM v3.0.
    Correct state order: payment ONLY occurs AFTER government approval.
    Officer persona removed.
    """

    def __init__(self, current_state: str = AppState.INITIATED):
        self.current_state = current_state

    @property
    def progress(self) -> int:
        return STATE_PROGRESS.get(self.current_state, 0)

    @property
    def is_terminal(self) -> bool:
        return self.current_state in (AppState.REJECTED, AppState.COMPLETED)

    @property
    def is_complete(self) -> bool:
        return self.current_state == AppState.COMPLETED

    @property
    def is_locked(self) -> bool:
        """True when citizen can no longer edit application data."""
        return self.current_state in LOCKED_STATES

    def can_transition_to(self, new_state: str) -> bool:
        allowed = VALID_TRANSITIONS.get(self.current_state, [])
        return new_state in allowed

    def transition(self, new_state: str) -> Tuple[bool, str]:
        """
        Attempt state transition. Returns (success, message).
        Logs every transition for full audit trail.
        """
        if new_state == self.current_state:
            return True, f"Already in state {new_state}"

        if not self.can_transition_to(new_state):
            allowed = VALID_TRANSITIONS.get(self.current_state, [])
            msg = (
                f"Invalid transition: {self.current_state} → {new_state}. "
                f"Allowed from this state: {[s.value for s in allowed]}"
            )
            logger.warning(f"FSM REJECTED: {msg}")
            return False, msg

        key = f"{self.current_state}→{new_state}"
        label = TRANSITION_LABELS.get(key, f"Moved to {new_state}")
        old = self.current_state
        self.current_state = new_state
        logger.info(f"FSM: {old} -> {new_state} | {label}")
        return True, label

    def get_next_states(self) -> List[str]:
        return VALID_TRANSITIONS.get(self.current_state, [])

    def get_citizen_message(self, language: str = "en") -> str:
        """Return a citizen-facing status message for the current state."""
        messages = CITIZEN_MESSAGES.get(self.current_state, {})
        return messages.get(language, messages.get("en", self.current_state))

    def to_dict(self) -> dict:
        return {
            "state": self.current_state,
            "progress": self.progress,
            "is_terminal": self.is_terminal,
            "is_locked": self.is_locked,
            "next_states": [s.value if hasattr(s, "value") else s for s in self.get_next_states()],
        }


# ─────────────────────────────────────────────
# Citizen-facing messages per state (en/hi/mr)
# ─────────────────────────────────────────────
CITIZEN_MESSAGES: Dict[str, Dict[str, str]] = {
    AppState.INITIATED: {
        "en": "Welcome to the Government Revenue Services Portal! I'm here to help you apply for certificates.",
        "hi": "सरकारी राजस्व सेवा पोर्टल पर स्वागत है! मैं आपके प्रमाण पत्र आवेदन में सहायता करूँगा।",
        "mr": "शासकीय महसूल सेवा पोर्टलवर स्वागत आहे! मी तुम्हाला प्रमाणपत्र अर्जात मदत करीन.",
    },
    AppState.CONSENT_GIVEN: {
        "en": "Thank you! Please tell me which certificate you need.",
        "hi": "धन्यवाद! कृपया बताएं आपको कौन-सा प्रमाण पत्र चाहिए।",
        "mr": "धन्यवाद! कृपया सांगा तुम्हाला कोणते प्रमाणपत्र हवे आहे.",
    },
    AppState.SERVICE_SELECTED: {
        "en": "Great! Let's start collecting the required details for your application.",
        "hi": "बढ़िया! आपके आवेदन की आवश्यक जानकारी एकत्र करते हैं।",
        "mr": "छान! तुमच्या अर्जासाठी आवश्यक माहिती गोळा करूया.",
    },
    AppState.INFORMATION_COLLECTION: {
        "en": "Please provide the required information.",
        "hi": "कृपया आवश्यक जानकारी प्रदान करें।",
        "mr": "कृपया आवश्यक माहिती द्या.",
    },
    AppState.DOCUMENT_COLLECTION: {
        "en": "Please upload the required documents.",
        "hi": "कृपया आवश्यक दस्तावेज़ अपलोड करें।",
        "mr": "कृपया आवश्यक कागदपत्रे अपलोड करा.",
    },
    AppState.OCR_PROCESSING: {
        "en": "📄 Verifying your documents with OCR. Please wait a moment...",
        "hi": "📄 OCR द्वारा दस्तावेज़ सत्यापित किए जा रहे हैं। कृपया प्रतीक्षा करें...",
        "mr": "📄 OCR द्वारे कागदपत्रे सत्यापित होत आहेत. कृपया प्रतीक्षा करा...",
    },
    AppState.VALIDATION_COMPLETED: {
        "en": "✅ Document verification complete!",
        "hi": "✅ दस्तावेज़ सत्यापन पूर्ण!",
        "mr": "✅ कागदपत्र सत्यापन पूर्ण!",
    },
    AppState.READINESS_CHECK: {
        "en": "⏳ Calculating your application readiness score...",
        "hi": "⏳ आपके आवेदन की तैयारी का स्कोर गणना की जा रही है...",
        "mr": "⏳ तुमच्या अर्जाचा तयारी स्कोर मोजला जात आहे...",
    },
    AppState.FIX_REQUIRED: {
        "en": "⚠️ Some issues need to be corrected before submitting.",
        "hi": "⚠️ जमा करने से पहले कुछ समस्याओं को ठीक करने की आवश्यकता है।",
        "mr": "⚠️ सबमिट करण्यापूर्वी काही समस्या दुरुस्त करणे आवश्यक आहे.",
    },
    AppState.READY_FOR_REVIEW: {
        "en": "🎯 Your application is ready! Please open the portal to do a final review before submitting.",
        "hi": "🎯 आपका आवेदन तैयार है! जमा करने से पहले पोर्टल पर अंतिम समीक्षा करें।",
        "mr": "🎯 तुमचा अर्ज तयार आहे! सबमिट करण्यापूर्वी पोर्टलवर अंतिम आढावा घ्या.",
    },
    AppState.FINAL_REVIEW: {
        "en": "📋 Please review all your information and confirm. Check the consent box when ready.",
        "hi": "📋 कृपया अपनी सभी जानकारी की समीक्षा करें। तैयार होने पर सहमति चेक करें।",
        "mr": "📋 कृपया सर्व माहितीचा आढावा घ्या. तयार असल्यावर संमती चेक करा.",
    },
    AppState.CONSENT_CONFIRMED: {
        "en": "✅ Consent confirmed! Submitting your application to the government...",
        "hi": "✅ सहमति पुष्टि! आपका आवेदन सरकार को जमा किया जा रहा है...",
        "mr": "✅ संमती पुष्टी! तुमचा अर्ज शासनाकडे सादर केला जात आहे...",
    },
    AppState.SUBMITTED_FOR_VERIFICATION: {
        "en": "📋 Application submitted! Tracking ID: {tracking_id}. You will be notified once reviewed.",
        "hi": "📋 आवेदन जमा! ट्रैकिंग ID: {tracking_id}। समीक्षा के बाद आपको सूचित किया जाएगा।",
        "mr": "📋 अर्ज सादर! ट्रॅकिंग ID: {tracking_id}. तपासणीनंतर तुम्हाला कळवले जाईल.",
    },
    AppState.UNDER_REVIEW: {
        "en": "👁️ Your application is under government review. We'll notify you when there's an update.",
        "hi": "👁️ आपका आवेदन सरकारी समीक्षाधीन है। अपडेट होने पर आपको सूचित किया जाएगा।",
        "mr": "👁️ तुमचा अर्ज शासकीय तपासणीत आहे. अद्यतन झाल्यावर तुम्हाला कळवले जाईल.",
    },
    AppState.CLARIFICATION_REQUIRED: {
        "en": "📝 The government has requested additional information. Please provide the details asked.",
        "hi": "📝 सरकार ने अतिरिक्त जानकारी मांगी है। कृपया मांगी गई जानकारी प्रदान करें।",
        "mr": "📝 शासनाने अतिरिक्त माहिती मागितली आहे. कृपया मागितलेली माहिती द्या.",
    },
    AppState.APPROVED: {
        "en": "🎉 Congratulations! Your application has been APPROVED by the government!",
        "hi": "🎉 बधाई हो! सरकार ने आपका आवेदन स्वीकृत कर दिया है!",
        "mr": "🎉 अभिनंदन! शासनाने तुमचा अर्ज मंजूर केला आहे!",
    },
    AppState.PAYMENT_REQUIRED: {
        "en": "💳 Your application is approved! Please pay ₹{fee_amount} to receive your certificate.",
        "hi": "💳 आपका आवेदन स्वीकृत है! प्रमाण पत्र के लिए ₹{fee_amount} का भुगतान करें।",
        "mr": "💳 तुमचा अर्ज मंजूर आहे! प्रमाणपत्रासाठी ₹{fee_amount} भरा.",
    },
    AppState.PAYMENT_COMPLETED: {
        "en": "✅ Payment received! Generating your certificate...",
        "hi": "✅ भुगतान प्राप्त! आपका प्रमाण पत्र तैयार हो रहा है...",
        "mr": "✅ पेमेंट मिळाले! तुमचे प्रमाणपत्र तयार होत आहे...",
    },
    AppState.CERTIFICATE_GENERATION: {
        "en": "⚙️ Your certificate is being generated. This takes about 30 seconds...",
        "hi": "⚙️ आपका प्रमाण पत्र तैयार हो रहा है। इसमें लगभग 30 सेकंड लगेंगे...",
        "mr": "⚙️ तुमचे प्रमाणपत्र तयार होत आहे. सुमारे 30 सेकंद लागतील...",
    },
    AppState.CERTIFICATE_READY: {
        "en": "📜 Your certificate is ready! Download it from the portal.",
        "hi": "📜 आपका प्रमाण पत्र तैयार है! पोर्टल से डाउनलोड करें।",
        "mr": "📜 तुमचे प्रमाणपत्र तयार आहे! पोर्टलवरून डाउनलोड करा.",
    },
    AppState.COMPLETED: {
        "en": "🏁 Application complete. Your certificate has been delivered. Thank you!",
        "hi": "🏁 आवेदन पूर्ण। आपका प्रमाण पत्र वितरित कर दिया गया है। धन्यवाद!",
        "mr": "🏁 अर्ज पूर्ण. तुमचे प्रमाणपत्र वितरित केले गेले आहे. धन्यवाद!",
    },
    AppState.REJECTED: {
        "en": "❌ Your application was rejected. Reason: {reason}. You may reapply after 30 days.",
        "hi": "❌ आपका आवेदन अस्वीकृत हुआ। कारण: {reason}। आप 30 दिनों बाद पुनः आवेदन कर सकते हैं।",
        "mr": "❌ तुमचा अर्ज नाकारला गेला. कारण: {reason}. 30 दिवसांनंतर पुन्हा अर्ज करता येईल.",
    },
}


def get_fsm_for_app(app) -> ApplicationFSM:
    """Create an FSM instance from an existing Application ORM object."""
    return ApplicationFSM(current_state=app.status or AppState.INITIATED)
