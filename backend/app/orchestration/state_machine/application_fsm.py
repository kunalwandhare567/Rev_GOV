"""
Phase 11 — Application Lifecycle FSM (14-state machine)
Controls valid state transitions for the entire certificate application lifecycle.

States:
  INITIATED → CONSENT_GIVEN → SERVICE_SELECTED → COLLECTING_DATA →
  ELIGIBILITY_CHECK → DOCUMENTS_REQUESTED → DOCUMENTS_UPLOADED →
  OCR_PROCESSING → PAYMENT_PENDING → PAYMENT_COMPLETED →
  SUBMITTED_FOR_VERIFICATION → UNDER_REVIEW → APPROVED / REJECTED →
  CERTIFICATE_READY
"""
import logging
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AppState(str, Enum):
    INITIATED                   = "INITIATED"
    CONSENT_GIVEN               = "CONSENT_GIVEN"
    SERVICE_SELECTED            = "SERVICE_SELECTED"
    COLLECTING_DATA             = "COLLECTING_DATA"
    ELIGIBILITY_CHECK           = "ELIGIBILITY_CHECK"
    DOCUMENTS_REQUESTED         = "DOCUMENTS_REQUESTED"
    DOCUMENTS_UPLOADED          = "DOCUMENTS_UPLOADED"
    OCR_PROCESSING              = "OCR_PROCESSING"
    PENDING_OFFICER_PRE_APPROVAL= "PENDING_OFFICER_PRE_APPROVAL"  # NEW: admin verifies before payment
    PAYMENT_PENDING             = "PAYMENT_PENDING"
    PAYMENT_COMPLETED           = "PAYMENT_COMPLETED"
    SUBMITTED_FOR_VERIFICATION  = "SUBMITTED_FOR_VERIFICATION"
    UNDER_REVIEW                = "UNDER_REVIEW"
    ESCALATED                   = "ESCALATED"
    APPROVED                    = "APPROVED"
    REJECTED                    = "REJECTED"
    CERTIFICATE_READY           = "CERTIFICATE_READY"


# Progress percentage per state (for UI progress bar)
STATE_PROGRESS: Dict[str, int] = {
    AppState.INITIATED:                    5,
    AppState.CONSENT_GIVEN:                10,
    AppState.SERVICE_SELECTED:             15,
    AppState.COLLECTING_DATA:              30,
    AppState.ELIGIBILITY_CHECK:            40,
    AppState.DOCUMENTS_REQUESTED:          45,
    AppState.DOCUMENTS_UPLOADED:           55,
    AppState.OCR_PROCESSING:               63,
    AppState.PENDING_OFFICER_PRE_APPROVAL: 70,  # NEW
    AppState.PAYMENT_PENDING:              75,
    AppState.PAYMENT_COMPLETED:            82,
    AppState.SUBMITTED_FOR_VERIFICATION:   88,
    AppState.UNDER_REVIEW:                 93,
    AppState.ESCALATED:                    93,
    AppState.APPROVED:                     100,
    AppState.REJECTED:                     100,
    AppState.CERTIFICATE_READY:            100,
}

# Valid transitions: from_state → [allowed to_states]
VALID_TRANSITIONS: Dict[str, List[str]] = {
    AppState.INITIATED:                    [AppState.CONSENT_GIVEN],
    AppState.CONSENT_GIVEN:                [AppState.SERVICE_SELECTED, AppState.INITIATED],
    AppState.SERVICE_SELECTED:             [AppState.COLLECTING_DATA],
    AppState.COLLECTING_DATA:              [AppState.ELIGIBILITY_CHECK, AppState.SERVICE_SELECTED],
    AppState.ELIGIBILITY_CHECK:            [AppState.DOCUMENTS_REQUESTED, AppState.REJECTED, AppState.COLLECTING_DATA],
    AppState.DOCUMENTS_REQUESTED:          [AppState.DOCUMENTS_UPLOADED],
    AppState.DOCUMENTS_UPLOADED:           [AppState.OCR_PROCESSING, AppState.DOCUMENTS_REQUESTED],
    AppState.OCR_PROCESSING:               [AppState.PENDING_OFFICER_PRE_APPROVAL, AppState.DOCUMENTS_REQUESTED],
    AppState.PENDING_OFFICER_PRE_APPROVAL: [AppState.PAYMENT_PENDING, AppState.REJECTED, AppState.DOCUMENTS_REQUESTED],
    AppState.PAYMENT_PENDING:              [AppState.PAYMENT_COMPLETED],
    AppState.PAYMENT_COMPLETED:            [AppState.SUBMITTED_FOR_VERIFICATION],
    AppState.SUBMITTED_FOR_VERIFICATION:   [AppState.UNDER_REVIEW],
    AppState.UNDER_REVIEW:                 [AppState.APPROVED, AppState.REJECTED, AppState.ESCALATED],
    AppState.ESCALATED:                    [AppState.UNDER_REVIEW, AppState.APPROVED, AppState.REJECTED],
    AppState.APPROVED:                     [AppState.CERTIFICATE_READY],
    AppState.REJECTED:                     [],   # Terminal
    AppState.CERTIFICATE_READY:            [],   # Terminal
}

# Human-readable transition labels for UI/audit
TRANSITION_LABELS: Dict[str, Dict[str, str]] = {
    "INITIATED→CONSENT_GIVEN":                          "Citizen gave consent",
    "CONSENT_GIVEN→SERVICE_SELECTED":                   "Service chosen",
    "SERVICE_SELECTED→COLLECTING_DATA":                 "Data collection started",
    "COLLECTING_DATA→ELIGIBILITY_CHECK":                "Submitted for eligibility check",
    "ELIGIBILITY_CHECK→DOCUMENTS_REQUESTED":            "Eligible — documents requested",
    "ELIGIBILITY_CHECK→REJECTED":                       "Ineligible — application rejected",
    "DOCUMENTS_REQUESTED→DOCUMENTS_UPLOADED":           "Documents uploaded",
    "DOCUMENTS_UPLOADED→OCR_PROCESSING":                "OCR processing started",
    "OCR_PROCESSING→PENDING_OFFICER_PRE_APPROVAL":      "OCR done — sent to Admin for pre-approval",
    "OCR_PROCESSING→DOCUMENTS_REQUESTED":               "OCR failed — re-upload required",
    "PENDING_OFFICER_PRE_APPROVAL→PAYMENT_PENDING":     "Admin approved documents — payment requested",
    "PENDING_OFFICER_PRE_APPROVAL→REJECTED":            "Admin rejected documents",
    "PENDING_OFFICER_PRE_APPROVAL→DOCUMENTS_REQUESTED": "Admin requested document re-upload",
    "PAYMENT_PENDING→PAYMENT_COMPLETED":                "Payment confirmed",
    "PAYMENT_COMPLETED→SUBMITTED_FOR_VERIFICATION":     "Submitted for officer review",
    "SUBMITTED_FOR_VERIFICATION→UNDER_REVIEW":          "Officer picked up application",
    "UNDER_REVIEW→APPROVED":                            "Officer approved",
    "UNDER_REVIEW→REJECTED":                            "Officer rejected",
    "UNDER_REVIEW→ESCALATED":                           "Escalated to senior officer",
    "ESCALATED→APPROVED":                               "Senior officer approved",
    "APPROVED→CERTIFICATE_READY":                       "Certificate generated",
}


class ApplicationFSM:
    """
    14-state Application Lifecycle FSM.
    Use transition() to move between states with validation.
    """

    def __init__(self, current_state: str = AppState.INITIATED):
        self.current_state = current_state

    @property
    def progress(self) -> int:
        return STATE_PROGRESS.get(self.current_state, 0)

    @property
    def is_terminal(self) -> bool:
        return self.current_state in (AppState.REJECTED, AppState.CERTIFICATE_READY)

    @property
    def is_complete(self) -> bool:
        return self.current_state == AppState.CERTIFICATE_READY

    def can_transition_to(self, new_state: str) -> bool:
        allowed = VALID_TRANSITIONS.get(self.current_state, [])
        return new_state in allowed

    def transition(self, new_state: str) -> Tuple[bool, str]:
        """
        Attempt state transition. Returns (success, message).
        """
        if new_state == self.current_state:
            return True, f"Already in state {new_state}"

        if not self.can_transition_to(new_state):
            allowed = VALID_TRANSITIONS.get(self.current_state, [])
            return False, (
                f"Invalid transition: {self.current_state} → {new_state}. "
                f"Allowed: {allowed}"
            )

        key = f"{self.current_state}→{new_state}"
        label = TRANSITION_LABELS.get(key, f"Moved to {new_state}")
        old = self.current_state
        self.current_state = new_state
        logger.info(f"FSM transition: {old} → {new_state} ({label})")
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
            "next_states": self.get_next_states(),
        }


# ── Citizen-facing messages per state (en/hi/mr) ─────────────────────────

CITIZEN_MESSAGES: Dict[str, Dict[str, str]] = {
    AppState.INITIATED: {
        "en": "Welcome! Your application has been started.",
        "hi": "स्वागत है! आपका आवेदन शुरू हो गया है।",
        "mr": "स्वागत आहे! तुमचा अर्ज सुरू झाला आहे।",
    },
    AppState.CONSENT_GIVEN: {
        "en": "Thank you for your consent. Please select a service.",
        "hi": "आपकी सहमति के लिए धन्यवाद। कृपया सेवा चुनें।",
        "mr": "तुमच्या संमतीबद्दल धन्यवाद. कृपया सेवा निवडा.",
    },
    AppState.COLLECTING_DATA: {
        "en": "Please provide the required information.",
        "hi": "कृपया आवश्यक जानकारी प्रदान करें।",
        "mr": "कृपया आवश्यक माहिती द्या.",
    },
    AppState.ELIGIBILITY_CHECK: {
        "en": "Checking your eligibility...",
        "hi": "आपकी पात्रता जाँची जा रही है...",
        "mr": "तुमची पात्रता तपासली जात आहे...",
    },
    AppState.DOCUMENTS_REQUESTED: {
        "en": "Please upload the required documents.",
        "hi": "कृपया आवश्यक दस्तावेज़ अपलोड करें।",
        "mr": "कृपया आवश्यक कागदपत्रे अपलोड करा.",
    },
    AppState.OCR_PROCESSING: {
        "en": "📄 We are verifying your documents. Please wait...",
        "hi": "📄 हम आपके दस्तावेज़ सत्यापित कर रहे हैं। कृपया प्रतीक्षा करें...",
        "mr": "📄 आम्ही तुमचे दस्तावेज सत्यापित करत आहोत. कृपया प्रतीक्षा करा...",
    },
    AppState.PENDING_OFFICER_PRE_APPROVAL: {
        "en": "📋 Your documents have been scanned and sent to the Admin for pre-verification. You will receive a notification once the Admin approves. Please wait.",
        "hi": "📋 आपके दस्तावेज़ स्कैन हो गए हैं और व्यवस्थापक (Admin) को पूर्व-सत्यापन के लिए भेजे गए हैं। Admin के अनुमोदन के बाद आपको सूचना मिलेगी।",
        "mr": "📋 तुमचे दस्तावेज स्कॅन झाले आहेत आणि प्रशासकाकडे (Admin) पूर्व-पडताळणीसाठी पाठवले आहेत. Admin मंजुरीनंतर तुम्हाला सूचना मिळेल.",
    },
    AppState.PAYMENT_PENDING: {
        "en": "✅ Admin has approved your documents! Type 'next' or 'pay now' to complete your ₹50 payment.",
        "hi": "✅ Admin ने आपके दस्तावेज़ स्वीकृत कर दिए हैं! ₹50 भुगतान के लिए 'next' या 'pay now' टाइप करें।",
        "mr": "✅ Admin ने तुमची कागदपत्रे मंजूर केली आहेत! ₹50 भरण्यासाठी 'next' किंवा 'pay now' टाइप करा.",
    },

    AppState.PAYMENT_COMPLETED: {
        "en": "✅ Payment received! Submitting your application...",
        "hi": "✅ भुगतान प्राप्त हुआ! आपका आवेदन जमा हो रहा है...",
        "mr": "✅ पेमेंट मिळाले! तुमचा अर्ज सादर केला जात आहे...",
    },
    AppState.SUBMITTED_FOR_VERIFICATION: {
        "en": "📋 Application submitted! Tracking ID: {tracking_id}",
        "hi": "📋 आवेदन जमा हो गया! ट्रैकिंग आईडी: {tracking_id}",
        "mr": "📋 अर्ज सादर झाला! ट्रॅकिंग आयडी: {tracking_id}",
    },
    AppState.UNDER_REVIEW: {
        "en": "👁️ Your application is under review by an officer.",
        "hi": "👁️ आपका आवेदन एक अधिकारी द्वारा समीक्षाधीन है।",
        "mr": "👁️ तुमचा अर्ज अधिकाऱ्याकडून तपासला जात आहे.",
    },
    AppState.APPROVED: {
        "en": "🎉 Congratulations! Your application has been APPROVED.",
        "hi": "🎉 बधाई हो! आपका आवेदन स्वीकृत हो गया है।",
        "mr": "🎉 अभिनंदन! तुमचा अर्ज मंजूर झाला आहे.",
    },
    AppState.REJECTED: {
        "en": "❌ Sorry, your application has been rejected. Reason: {reason}",
        "hi": "❌ खेद है, आपका आवेदन अस्वीकृत कर दिया गया है। कारण: {reason}",
        "mr": "❌ दुर्दैवाने, तुमचा अर्ज नाकारला गेला. कारण: {reason}",
    },
    AppState.CERTIFICATE_READY: {
        "en": "📜 Your certificate is ready! Download from the portal.",
        "hi": "📜 आपका प्रमाण पत्र तैयार है! पोर्टल से डाउनलोड करें।",
        "mr": "📜 तुमचे प्रमाणपत्र तयार आहे! पोर्टलवरून डाउनलोड करा.",
    },
}


def get_fsm_for_app(app) -> ApplicationFSM:
    """Create an FSM instance from an existing Application ORM object."""
    return ApplicationFSM(current_state=app.status or AppState.INITIATED)
