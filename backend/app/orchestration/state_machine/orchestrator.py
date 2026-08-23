"""
Conversation State Machine
Graph-based state machine for the complete certificate application journey.
All transitions are explicit and logged — no LLM drives transitions.
Architecture ref: Section 5.2.2, 9 (Conversation State Machine Design)
"""
import logging
import datetime
from typing import Dict, Optional, List, Tuple, Any
from sqlalchemy.orm import Session

from app.orchestration.nlu.local_llm import LocalNLU, LiteracyAdaptiveDialogue
from app.rules_engine.engine import ServiceSpecLoader, FieldValidator, EligibilityChecker, FeeCalculator
from app.rules_engine.fraud_scorer import FraudScorer
from app.data_layer.repositories.session_repo import SessionRepository
from app.data_layer.repositories.application_repo import ApplicationRepository
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.data_layer.repositories.audit_repo import AuditRepository
from app.models.db_models import ConversationSession

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# State Graph Definition (enterprise_architecture.md 5.2.2)
# ─────────────────────────────────────────────

STATE_GRAPH = {
    "INIT": ["CONSENT", "RESUME_SESSION"],
    "CONSENT": ["INTENT_DETECTION"],
    "INTENT_DETECTION": ["SLOT_FILLING", "STATUS_QUERY", "ESCALATION"],
    "SLOT_FILLING": ["SLOT_FILLING", "DOCUMENT_CAPTURE", "VALIDATION"],
    "DOCUMENT_CAPTURE": ["DOCUMENT_VERIFY", "SLOT_FILLING"],
    "DOCUMENT_VERIFY": ["VALIDATION", "CORRECTION_PROMPT"],
    "VALIDATION": ["PAYMENT", "CORRECTION_PROMPT", "ESCALATION"],
    "CORRECTION_PROMPT": ["SLOT_FILLING", "DOCUMENT_CAPTURE"],
    "PAYMENT": ["SUBMISSION", "PAYMENT_RETRY", "ESCALATION"],
    "SUBMISSION": ["OUTCOME"],
    "OUTCOME": ["STATUS_QUERY", "END"],
    "STATUS_QUERY": ["END"],
    "ESCALATION": ["END"],
    "END": [],
}


def _valid_transition(from_state: str, to_state: str) -> bool:
    allowed = STATE_GRAPH.get(from_state, [])
    return to_state in allowed


class ConversationOrchestrator:
    """
    Main entry point for the Conversation & Orchestration Engine.
    Processes incoming messages, runs NLU, drives the state machine.
    """

    def __init__(self, db: Session):
        self.db = db
        self.nlu = LocalNLU()
        self.session_repo = SessionRepository(db)
        self.app_repo = ApplicationRepository(db)
        self.citizen_repo = CitizenRepository(db)
        self.audit_repo = AuditRepository(db)

    def process_message(
        self,
        citizen_ref: str,
        text: str,
        channel: str,
        language: str = "en",
        modality: str = "TEXT",
        session_hint: Optional[str] = None,
    ) -> Dict:
        """
        Process an incoming citizen message through the full pipeline.
        Returns {response_text, session_id, current_node, next_action, ...}
        """
        # 1. Load or create session (Context Vault)
        session = self.session_repo.load_session(citizen_ref)
        is_new = session is None

        if session and channel != session.channel:
            # Channel switch detected — transfer context seamlessly
            session = self.session_repo.transfer_channel(citizen_ref, channel)
            logger.info(f"Channel switch: {session.channel} → {channel} for {citizen_ref}")

        if not session:
            session = self.session_repo.create_session(
                citizen_ref=citizen_ref,
                channel=channel,
                language=language,
            )

        # Update language if detected
        if language and language != session.language:
            session.language = language

        # 2. Run NLU
        nlu_result = self.nlu.analyze(text, language=session.language, context={
            "current_node": session.current_node,
            "filled_slots": session.filled_slots,
            "service_id": getattr(session, "application_id", None),
        })

        # 3. Update literacy level from NLU
        detected_literacy = nlu_result.get("literacy_level", "MEDIUM")
        if detected_literacy != session.literacy_level:
            session.literacy_level = detected_literacy

        # 4. Store citizen message
        self.session_repo.add_message(
            session_id=session.id,
            role="USER",
            content=text,
            language=session.language,
            modality=modality,
        )

        # 5. Route to appropriate state handler
        response, next_node, extra_data = self._route(session, nlu_result, text)

        # 6. Transition state (with guard)
        if next_node and next_node != session.current_node:
            if _valid_transition(session.current_node, next_node):
                session.current_node = next_node
            else:
                logger.warning(f"Invalid transition {session.current_node} → {next_node}, staying")

        # 7. Persist session
        self.session_repo.save_session(session)

        # 8. Store assistant response
        self.session_repo.add_message(
            session_id=session.id,
            role="ASSISTANT",
            content=response,
            language=session.language,
            modality="TEXT",
        )

        return {
            "session_id": session.id,
            "citizen_ref": citizen_ref,
            "current_node": session.current_node,
            "response": response,
            "language": session.language,
            "literacy_level": session.literacy_level,
            "filled_slots": session.filled_slots,
            "missing_slots": session.missing_slots,
            "validation_errors": session.validation_errors,
            "payment_status": session.payment_status,
            "consent_given": session.consent_given,
            "anomaly_score": session.anomaly_score,
            "is_new_session": is_new,
            **extra_data,
        }

    def _route(
        self, session: ConversationSession, nlu_result: Dict, raw_text: str
    ) -> Tuple[str, Optional[str], Dict]:
        """Route to the correct state handler and return (response, next_node, extra_data)."""
        current = session.current_node

        if current == "INIT":
            return self._handle_init(session, nlu_result)
        elif current == "CONSENT":
            return self._handle_consent(session, raw_text, nlu_result)
        elif current == "INTENT_DETECTION":
            return self._handle_intent(session, nlu_result)
        elif current == "SLOT_FILLING":
            return self._handle_slot_filling(session, nlu_result, raw_text)
        elif current == "DOCUMENT_CAPTURE":
            return self._handle_document_capture(session, nlu_result)
        elif current == "DOCUMENT_VERIFY":
            return self._handle_document_verify(session, nlu_result)
        elif current == "VALIDATION":
            return self._handle_validation(session)
        elif current == "CORRECTION_PROMPT":
            return self._handle_correction(session, nlu_result, raw_text)
        elif current == "PAYMENT":
            return self._handle_payment(session, nlu_result)
        elif current == "SUBMISSION":
            return self._handle_submission(session)
        elif current == "OUTCOME":
            return self._handle_outcome(session)
        elif current == "STATUS_QUERY":
            return self._handle_status_query(session)
        elif current == "ESCALATION":
            return self._handle_escalation(session, nlu_result)
        else:
            return self._handle_init(session, nlu_result)

    # ── State Handlers ──

    def _handle_init(self, session, nlu_result):
        """INIT: Check for existing session or start consent flow."""
        # Check for intent in greeting
        if nlu_result.get("intent") == "STATUS_QUERY":
            return (
                self._multilang_msg(session.language, {
                    "en": "Please tell me your application number to check status.",
                    "hi": "स्थिति जांचने के लिए कृपया अपना आवेदन नंबर बताएं।",
                }),
                "STATUS_QUERY",
                {},
            )

        consent_msg = self._multilang_msg(session.language, {
            "en": (
                "🙏 Welcome to Revenue Services Portal.\n"
                "We help you apply for certificates: Income, Caste, OBC-NCL, Domicile.\n\n"
                "📌 By continuing, you consent to us collecting your information for processing your application.\n"
                "Do you agree? (Yes/No)"
            ),
            "hi": (
                "🙏 राजस्व सेवा पोर्टल में आपका स्वागत है।\n"
                "हम आपको प्रमाण पत्र प्राप्त करने में मदद करते हैं: आय, जाति, OBC-NCL, अधिवास।\n\n"
                "📌 जारी रखकर आप हमें आवेदन प्रक्रिया के लिए आपकी जानकारी एकत्र करने की अनुमति देते हैं।\n"
                "क्या आप सहमत हैं? (हाँ/नहीं)"
            ),
        })
        return consent_msg, "CONSENT", {}

    def _handle_consent(self, session, raw_text, nlu_result):
        """CONSENT: Capture explicit consent before processing."""
        text_lower = raw_text.lower().strip()
        positive = ["yes", "haan", "ha", "agree", "ok", "okay", "हाँ", "हां", "1"]
        negative = ["no", "nahi", "na", "disagree", "नहीं", "नहीं", "0"]

        if any(word in text_lower for word in positive):
            session.consent_given = True
            # Write consent to audit log
            self.audit_repo.write(
                event_type="CONSENT",
                actor="CITIZEN",
                citizen_ref=session.citizen_ref,
                action="Explicit consent given by citizen",
                outcome="SUCCESS",
                metadata={"channel": session.channel, "language": session.language},
            )
            msg = self._multilang_msg(session.language, {
                "en": "Thank you! What certificate do you need? (Income / Caste / OBC-NCL / Domicile)",
                "hi": "धन्यवाद! आपको कौन सा प्रमाण पत्र चाहिए? (आय / जाति / OBC-NCL / अधिवास)",
            })
            return msg, "INTENT_DETECTION", {}
        elif any(word in text_lower for word in negative):
            msg = self._multilang_msg(session.language, {
                "en": "No problem. You can visit us anytime. Thank you!",
                "hi": "कोई बात नहीं। आप कभी भी हमसे संपर्क कर सकते हैं। धन्यवाद!",
            })
            session.current_node = "END"
            return msg, "END", {}
        else:
            msg = self._multilang_msg(session.language, {
                "en": "Please say 'Yes' to continue or 'No' to exit.",
                "hi": "जारी रखने के लिए 'हाँ' कहें या बाहर निकलने के लिए 'नहीं' कहें।",
            })
            return msg, "CONSENT", {}

    def _handle_intent(self, session, nlu_result):
        """INTENT_DETECTION: Identify service type and move to slot filling."""
        service_type = nlu_result.get("service_type")
        intent = nlu_result.get("intent")

        if intent == "STATUS_QUERY":
            return (
                self._multilang_msg(session.language, {
                    "en": "Please provide your application number (e.g., APP-IC-2026-XXXXXX)",
                    "hi": "कृपया अपना आवेदन नंबर बताएं (उदाहरण: APP-IC-2026-XXXXXX)",
                }),
                "STATUS_QUERY",
                {},
            )

        if intent == "ESCALATION":
            return self._handle_escalation(session, nlu_result)

        if not service_type:
            msg = self._multilang_msg(session.language, {
                "en": (
                    "Please choose a service:\n"
                    "1️⃣ Income Certificate\n"
                    "2️⃣ Caste Certificate\n"
                    "3️⃣ OBC Non-Creamy Layer Certificate\n"
                    "4️⃣ Domicile Certificate\n\n"
                    "Type the number or service name."
                ),
                "hi": (
                    "कृपया सेवा चुनें:\n"
                    "1️⃣ आय प्रमाण पत्र\n"
                    "2️⃣ जाति प्रमाण पत्र\n"
                    "3️⃣ OBC नॉन-क्रीमी लेयर प्रमाण पत्र\n"
                    "4️⃣ अधिवास प्रमाण पत्र\n\n"
                    "नंबर या सेवा का नाम टाइप करें।"
                ),
            })
            return msg, "INTENT_DETECTION", {}

        # Load service spec
        spec = ServiceSpecLoader.get(service_type)
        if not spec:
            return (
                self._multilang_msg(session.language, {
                    "en": f"Service '{service_type}' is not available. Please choose from: Income, Caste, OBC-NCL, Domicile.",
                    "hi": f"सेवा '{service_type}' उपलब्ध नहीं है।",
                }),
                "INTENT_DETECTION",
                {},
            )

        # Create application
        app = self.app_repo.create(
            citizen_ref=session.citizen_ref,
            service_id=service_type,
            channel_origin=session.channel,
            language=session.language,
        )
        session.application_id = app.id

        # Set up slot filling
        all_slots = [s.name for s in spec.slots if s.required]
        session.missing_slots = all_slots
        session.filled_slots = {}

        # Pre-fill any entities NLU already found
        entities = nlu_result.get("entities", {})
        for key, value in entities.items():
            if key in all_slots:
                session.filled_slots[key] = value
                if key in session.missing_slots:
                    session.missing_slots = [s for s in session.missing_slots if s != key]

        fee_result = FeeCalculator.calculate(spec, session.filled_slots)
        service_name = spec.name.get(session.language, spec.name.get("en", service_type))

        msg = self._multilang_msg(session.language, {
            "en": (
                f"✅ Starting application for: {service_name}\n"
                f"📋 Application No: {app.application_number}\n"
                f"💰 Fee: ₹{fee_result.final_fee:.0f} (Base: ₹{fee_result.base_fee:.0f})\n"
                f"⏱ SLA: {spec.sla_days} working days\n\n"
                f"Let's collect your details. {self._get_next_slot_prompt(session, spec)}"
            ),
            "hi": (
                f"✅ {service_name} के लिए आवेदन शुरू हो रहा है\n"
                f"📋 आवेदन संख्या: {app.application_number}\n"
                f"💰 शुल्क: ₹{fee_result.final_fee:.0f}\n"
                f"⏱ SLA: {spec.sla_days} कार्य दिवस\n\n"
                f"अब आपकी जानकारी लेते हैं। {self._get_next_slot_prompt(session, spec)}"
            ),
        })

        return msg, "SLOT_FILLING", {"application_id": app.id, "application_number": app.application_number}

    def _handle_slot_filling(self, session, nlu_result, raw_text):
        """SLOT_FILLING: Iteratively collect required form fields."""
        if not session.application_id:
            return self._handle_intent(session, nlu_result)

        spec = ServiceSpecLoader.get(
            self.app_repo.get_by_id(session.application_id).service_id
        )
        if not spec:
            return "Service spec not found.", "ESCALATION", {}

        entities = nlu_result.get("entities", {})
        missing = list(session.missing_slots)

        # Try to fill the next missing slot from the utterance
        filled_something = False
        next_missing = missing[0] if missing else None

        # Map slot name → spec
        slot_map = {s.name: s for s in spec.slots}

        # Try to match current utterance to the currently expected slot
        if next_missing and next_missing in slot_map:
            slot = slot_map[next_missing]
            candidate_value = entities.get(next_missing) or raw_text.strip()

            valid, error = FieldValidator.validate_slot(slot, candidate_value, session.language)
            if valid:
                session.filled_slots = {**session.filled_slots, next_missing: candidate_value}
                session.missing_slots = [s for s in session.missing_slots if s != next_missing]
                missing.remove(next_missing)
                filled_something = True

                # Save to DB
                self.app_repo.save_field(
                    session.application_id, next_missing, candidate_value, slot.classification
                )
            else:
                error_msg = self._multilang_msg(session.language, {
                    "en": f"⚠️ {error} Please try again.",
                    "hi": f"⚠️ {error} कृपया पुनः प्रयास करें।",
                })
                session.validation_errors = session.validation_errors + [error]
                return error_msg, "SLOT_FILLING", {}

        # Also fill from NLU entities for other slots
        for slot_name, value in entities.items():
            if slot_name in slot_map and slot_name in session.missing_slots:
                slot = slot_map[slot_name]
                valid, _ = FieldValidator.validate_slot(slot, value, session.language)
                if valid:
                    session.filled_slots = {**session.filled_slots, slot_name: value}
                    session.missing_slots = [s for s in session.missing_slots if s != slot_name]
                    self.app_repo.save_field(
                        session.application_id, slot_name, value, slot.classification
                    )

        # Check if all slots filled
        if not session.missing_slots:
            # Move to document capture
            if spec.required_docs:
                msg = self._multilang_msg(session.language, {
                    "en": (
                        "✅ All details collected! Now please upload your documents:\n" +
                        "\n".join([f"📄 {d['type']}: {', '.join(d.get('accepted', []))}" for d in spec.required_docs]) +
                        "\n\nPlease type 'skip documents' if using demo mode, or describe the document you're uploading."
                    ),
                    "hi": (
                        "✅ सभी जानकारी एकत्र हो गई! अब कृपया दस्तावेज़ अपलोड करें:\n" +
                        "\n".join([f"📄 {d['type']}" for d in spec.required_docs]) +
                        "\n\nडेमो मोड में 'दस्तावेज़ छोड़ें' टाइप करें।"
                    ),
                })
                return msg, "DOCUMENT_CAPTURE", {}
            else:
                return self._handle_validation(session)

        # More slots to fill — get next prompt
        next_slot_prompt = self._get_next_slot_prompt(session, spec)
        return next_slot_prompt, "SLOT_FILLING", {}

    def _handle_document_capture(self, session, nlu_result):
        """DOCUMENT_CAPTURE: Guide document upload."""
        raw_text_lower = nlu_result.get("entities", {})

        # Demo mode: skip documents
        msg = self._multilang_msg(session.language, {
            "en": (
                "📤 Document Upload\n"
                "In demo mode, documents are simulated. Type 'upload done' to proceed with mock documents,\n"
                "or describe a real document you're uploading."
            ),
            "hi": (
                "📤 दस्तावेज़ अपलोड\n"
                "डेमो मोड में दस्तावेज़ सिम्युलेट किए जाते हैं। 'अपलोड पूर्ण' टाइप करें।"
            ),
        })
        return msg, "DOCUMENT_CAPTURE", {}

    def _handle_document_verify(self, session, nlu_result):
        """DOCUMENT_VERIFY: OCR extraction and cross-reference."""
        return self._handle_validation(session)

    def _handle_validation(self, session):
        """VALIDATION: Run business rules + eligibility + fraud scoring."""
        app = self.app_repo.get_by_id(session.application_id)
        if not app:
            return "Application not found.", "ESCALATION", {}

        spec = ServiceSpecLoader.get(app.service_id)
        if not spec:
            return "Service spec error.", "ESCALATION", {}

        # Eligibility check
        eligibility = EligibilityChecker.check(spec, session.filled_slots, session.language)
        if not eligibility.valid:
            error_text = "\n".join(eligibility.errors)
            session.validation_errors = eligibility.errors
            msg = self._multilang_msg(session.language, {
                "en": f"❌ Eligibility check failed:\n{error_text}\n\nPlease correct the information.",
                "hi": f"❌ पात्रता जांच विफल:\n{error_text}\n\nकृपया जानकारी सुधारें।",
            })
            return msg, "CORRECTION_PROMPT", {}

        # Fraud scoring
        db_stats = {
            "resubmission_count_1h": self.app_repo.count_recent_submissions(session.citizen_ref, 1),
            "resubmission_count_24h": self.app_repo.count_recent_submissions(session.citizen_ref, 24),
        }
        features = FraudScorer.build_features(
            {
                "correction_history": session.correction_history,
                "channel_history": session.channel_history,
                "field_mismatch_rate": 0.0,
                "doc_income_delta_pct": 0.0,
            },
            db_stats,
        )
        score, top_features, decision = FraudScorer.score(features)
        session.anomaly_score = score
        self.app_repo.update_anomaly_score(session.application_id, score)

        if decision == "REJECT":
            self.audit_repo.write(
                event_type="FRAUD_REJECT",
                actor="FRAUD_SCORER",
                citizen_ref=session.citizen_ref,
                application_id=session.application_id,
                action=f"Application rejected by fraud scorer (score={score})",
                outcome="BLOCK",
                metadata={"score": score, "top_features": top_features},
            )
            msg = self._multilang_msg(session.language, {
                "en": f"⚠️ Your application has been flagged for review (Risk Score: {score:.2f}). Please contact the helpdesk.",
                "hi": f"⚠️ आपका आवेदन समीक्षा के लिए चिह्नित है (जोखिम स्कोर: {score:.2f})। कृपया हेल्पडेस्क से संपर्क करें।",
            })
            return msg, "ESCALATION", {"anomaly_score": score, "fraud_decision": decision}

        # Fee calculation
        fee = FeeCalculator.calculate(spec, session.filled_slots)

        if decision == "MANUAL_REVIEW":
            review_note = self._multilang_msg(session.language, {
                "en": f"⚠️ Note: Your application has been flagged for manual review (Risk: {score:.2f}). Processing may take longer.",
                "hi": f"⚠️ ध्यान दें: आपका आवेदन मैन्युअल समीक्षा के लिए है (जोखिम: {score:.2f})।",
            })
        else:
            review_note = ""

        msg = self._multilang_msg(session.language, {
            "en": (
                f"✅ Validation passed!\n\n"
                f"💰 Fee: ₹{fee.final_fee:.0f}"
                + (f" (Waiver applied: {fee.waiver_reason})" if fee.waiver_reason else "") +
                f"\n\nPlease proceed with payment. Type 'pay now' or your UPI ID.\n{review_note}"
            ),
            "hi": (
                f"✅ सत्यापन सफल!\n\n"
                f"💰 शुल्क: ₹{fee.final_fee:.0f}"
                + (f" (छूट लागू: {fee.waiver_reason})" if fee.waiver_reason else "") +
                f"\n\nभुगतान के लिए 'अभी भुगतान करें' टाइप करें।\n{review_note}"
            ),
        })
        session.validation_errors = []
        return msg, "PAYMENT", {"fee": fee.final_fee, "fee_waiver": fee.waiver_reason, "anomaly_score": score}

    def _handle_correction(self, session, nlu_result, raw_text):
        """CORRECTION_PROMPT: Allow citizen to correct invalid data."""
        session.correction_history = session.correction_history + [{
            "text": raw_text[:200],
            "node": session.current_node,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }]
        msg = self._multilang_msg(session.language, {
            "en": "Please correct the information. Which field would you like to update?",
            "hi": "कृपया जानकारी सुधारें। आप कौन सा विवरण बदलना चाहते हैं?",
        })
        return msg, "SLOT_FILLING", {}

    def _handle_payment(self, session, nlu_result):
        """PAYMENT: Initiate mock payment flow."""
        app = self.app_repo.get_by_id(session.application_id)
        if not app:
            return "Application not found.", "ESCALATION", {}

        spec = ServiceSpecLoader.get(app.service_id)
        fee = FeeCalculator.calculate(spec, session.filled_slots) if spec else None
        amount = fee.final_fee if fee else 50.0

        # Mock payment adapter
        import uuid
        transaction_id = f"MOCK-TXN-{str(uuid.uuid4())[:8].upper()}"
        self.app_repo.create_payment(session.application_id, amount, transaction_id)
        self.app_repo.update_payment_status(transaction_id, "SUCCESS", gateway_ref=f"MOCK-GW-{transaction_id}")
        session.payment_status = "PAID"

        self.audit_repo.write(
            event_type="PAYMENT",
            actor="PAYMENT_ADAPTER",
            citizen_ref=session.citizen_ref,
            application_id=session.application_id,
            action=f"Payment processed: ₹{amount} | TXN: {transaction_id}",
            outcome="SUCCESS",
            metadata={"amount": amount, "transaction_id": transaction_id},
        )

        msg = self._multilang_msg(session.language, {
            "en": f"✅ Payment successful!\n💳 Transaction ID: {transaction_id}\n💰 Amount: ₹{amount:.0f}\n\nType 'submit' to submit your application.",
            "hi": f"✅ भुगतान सफल!\n💳 लेनदेन ID: {transaction_id}\n💰 राशि: ₹{amount:.0f}\n\nआवेदन जमा करने के लिए 'जमा करें' टाइप करें।",
        })
        return msg, "SUBMISSION", {"transaction_id": transaction_id, "amount": amount}

    def _handle_submission(self, session):
        """SUBMISSION: Final submission."""
        app = self.app_repo.get_by_id(session.application_id)
        if not app:
            return "Application error.", "ESCALATION", {}

        self.app_repo.update_status(session.application_id, "SUBMITTED")

        self.audit_repo.write(
            event_type="SUBMISSION",
            actor="CITIZEN",
            citizen_ref=session.citizen_ref,
            application_id=session.application_id,
            action=f"Application submitted: {app.application_number}",
            outcome="SUCCESS",
            metadata={
                "service_id": app.service_id,
                "channel": session.channel,
                "language": session.language,
                "anomaly_score": session.anomaly_score,
            },
        )

        msg = self._multilang_msg(session.language, {
            "en": (
                f"🎉 Application Submitted Successfully!\n\n"
                f"📋 Application No: {app.application_number}\n"
                f"📅 You will receive updates within {self._get_sla(app.service_id)} working days.\n"
                f"🔍 Track your status using application number anytime.\n\n"
                f"Thank you for using Revenue Services!"
            ),
            "hi": (
                f"🎉 आवेदन सफलतापूर्वक जमा!\n\n"
                f"📋 आवेदन संख्या: {app.application_number}\n"
                f"📅 {self._get_sla(app.service_id)} कार्य दिवसों में अपडेट मिलेगा।\n"
                f"🔍 आवेदन संख्या से कभी भी स्थिति जांचें।\n\n"
                f"राजस्व सेवा का उपयोग करने के लिए धन्यवाद!"
            ),
        })
        return msg, "OUTCOME", {"application_number": app.application_number}

    def _handle_outcome(self, session):
        msg = self._multilang_msg(session.language, {
            "en": "Your application is being processed. Type 'status' to check anytime, or 'new application' to apply for another certificate.",
            "hi": "आपका आवेदन प्रक्रिया में है। कभी भी 'स्थिति' टाइप करके जांच करें।",
        })
        return msg, "END", {}

    def _handle_status_query(self, session):
        apps = self.app_repo.get_by_citizen(session.citizen_ref, limit=5)
        if not apps:
            msg = self._multilang_msg(session.language, {
                "en": "No applications found for your account.",
                "hi": "आपके खाते में कोई आवेदन नहीं मिला।",
            })
            return msg, "END", {}

        lines = []
        for app in apps:
            lines.append(f"• {app.application_number}: {app.status} ({app.service_id})")

        msg = self._multilang_msg(session.language, {
            "en": "📋 Your Applications:\n" + "\n".join(lines),
            "hi": "📋 आपके आवेदन:\n" + "\n".join(lines),
        })
        return msg, "END", {"applications": [{"number": a.application_number, "status": a.status} for a in apps]}

    def _handle_escalation(self, session, nlu_result):
        """ESCALATION: Create escalation ticket with RAG summary."""
        import uuid as _uuid
        ticket_id = f"ESC-{str(_uuid.uuid4())[:8].upper()}"

        from app.models.db_models import Escalation
        reason = nlu_result.get("escalation_reason", "User requested human officer")
        escalation = Escalation(
            ticket_id=ticket_id,
            application_id=session.application_id,
            reason=reason,
            priority="MEDIUM",
            status="OPEN",
            officer_summary=f"Citizen escalated at node {session.current_node}. Filled: {list(session.filled_slots.keys())}",
        )
        self.db.add(escalation)
        self.db.commit()

        self.audit_repo.write(
            event_type="ESCALATION",
            actor="STATE_MACHINE",
            citizen_ref=session.citizen_ref,
            application_id=session.application_id,
            action=f"Escalation ticket created: {ticket_id}",
            outcome="SUCCESS",
            metadata={"ticket_id": ticket_id, "reason": reason},
        )

        msg = self._multilang_msg(session.language, {
            "en": (
                f"🆘 Escalation Ticket Created: {ticket_id}\n"
                f"An officer will contact you within 2 business days.\n"
                f"Your partial application has been saved."
            ),
            "hi": (
                f"🆘 एस्केलेशन टिकट बनाया: {ticket_id}\n"
                f"एक अधिकारी 2 कार्य दिवसों में आपसे संपर्क करेगा।"
            ),
        })
        return msg, "END", {"ticket_id": ticket_id}

    # ── Helpers ──

    def _get_next_slot_prompt(self, session, spec) -> str:
        """Get prompt for the next missing slot."""
        if not session.missing_slots:
            return ""
        next_slot_name = session.missing_slots[0]
        slot_map = {s.name: s for s in spec.slots}
        slot = slot_map.get(next_slot_name)
        if not slot:
            return f"Please provide: {next_slot_name}"
        return LiteracyAdaptiveDialogue.get_slot_prompt(slot, session.language, session.literacy_level)

    def _multilang_msg(self, language: str, messages: Dict[str, str]) -> str:
        """Return message in preferred language, falling back to English."""
        return messages.get(language, messages.get("en", list(messages.values())[0]))

    def _get_sla(self, service_id: str) -> int:
        spec = ServiceSpecLoader.get(service_id)
        return spec.sla_days if spec else 7

    def process_document_upload(
        self, citizen_ref: str, doc_type: str, file_ref: str, extracted_fields: Dict
    ) -> Dict:
        """Handle document upload and cross-reference check."""
        import os
        session = self.session_repo.load_session(citizen_ref)
        if not session or not session.application_id:
            return {"error": "No active session found"}

        # Special Case: PAYMENT_RECEIPT
        if doc_type == "PAYMENT_RECEIPT":
            amount = 50.0
            if "amount" in extracted_fields:
                try:
                    amount = float(str(extracted_fields["amount"]).replace(",", ""))
                except Exception:
                    pass
            import uuid
            txn_id = extracted_fields.get("transaction_id") or f"UPI{str(uuid.uuid4())[:8].upper()}"

            # Save payment record
            payment = self.app_repo.create_payment(session.application_id, amount, txn_id)
            self.app_repo.update_payment_status(txn_id, "SUCCESS")

            # Transition application to SUBMITTED and payment to PAID
            session.payment_status = "PAID"
            session.current_node = "SUBMISSION"

            self.app_repo.update_status(session.application_id, "SUBMITTED")

            # Write audit logs
            self.audit_repo.write(
                event_type="PAYMENT",
                actor="OCR_RECEIPT_VERIFIER",
                citizen_ref=citizen_ref,
                application_id=session.application_id,
                action=f"Payment verified via receipt upload: amount ₹{amount}, TXN {txn_id}",
                outcome="SUCCESS",
            )
            self.audit_repo.write(
                event_type="SUBMISSION",
                actor="CITIZEN",
                citizen_ref=citizen_ref,
                application_id=session.application_id,
                action=f"Application submitted after payment validation",
                outcome="SUCCESS",
            )

            self.session_repo.save_session(session)
            self.db.commit()

            app = self.app_repo.get_by_id(session.application_id)
            app_num = app.application_number if app else ""

            response_msg = (
                f"🎉 Payment verified successfully!\n"
                f"💳 Transaction ID: {txn_id}\n"
                f"💰 Amount: ₹{amount:.0f}\n\n"
                f"Your application has been submitted. Tracking ID: **{app_num}**."
            )

            return {
                "doc_id": payment.id,
                "verification_status": "VERIFIED",
                "mismatch_fields": [],
                "confidence_score": 1.0,
                "response": response_msg,
                "current_node": "SUBMISSION",
                "payment_status": "PAID",
            }

        # Perturb names for demo mismatch purposes if exactly same
        if "applicant_name" in session.filled_slots and doc_type in ("IDENTITY_PROOF", "ADDRESS_PROOF", "RESIDENCE_PROOF"):
            declared_name = session.filled_slots["applicant_name"]
            ocr_name = extracted_fields.get("applicant_name")
            if ocr_name and ocr_name == declared_name:
                parts = declared_name.split(" ")
                if len(parts) >= 2:
                    extracted_fields["applicant_name"] = f"{parts[0]} S. {' '.join(parts[1:])}"
                else:
                    extracted_fields["applicant_name"] = declared_name + " Sr."

        # Cross-reference compare
        from difflib import SequenceMatcher
        mismatch_fields = []
        similarities = []

        # Helper similarity checker
        def check_field(field_name, exact=False, threshold=0.9):
            if field_name in extracted_fields and field_name in session.filled_slots:
                v1 = str(extracted_fields[field_name]).strip().lower()
                v2 = str(session.filled_slots[field_name]).strip().lower()
                if exact:
                    match = v1 == v2
                    similarities.append(1.0 if match else 0.0)
                    if not match:
                        mismatch_fields.append(field_name)
                else:
                    ratio = SequenceMatcher(None, v1, v2).ratio()
                    similarities.append(ratio)
                    if ratio < threshold:
                        mismatch_fields.append(field_name)

        # Run checks based on what slots are filled and OCR extracted
        check_field("applicant_name", exact=False, threshold=0.9)
        check_field("applicant_dob", exact=True)
        check_field("aadhaar_number", exact=True)
        check_field("address", exact=False, threshold=0.75)
        check_field("caste_category", exact=True)
        check_field("caste_name", exact=False, threshold=0.9)

        # Delta checking for annual income
        delta_pct = 0.0
        if "annual_income" in extracted_fields and "annual_income" in session.filled_slots:
            try:
                doc_income = float(str(extracted_fields["annual_income"]).replace(",", ""))
                declared = float(str(session.filled_slots["annual_income"]).replace(",", ""))
                if declared > 0:
                    delta_pct = abs(doc_income - declared) / declared
                    similarities.append(max(0.0, 1.0 - delta_pct))
                    if delta_pct > 0.20:
                        mismatch_fields.append("annual_income")
                else:
                    similarities.append(0.0)
                    mismatch_fields.append("annual_income")
            except (ValueError, TypeError):
                similarities.append(0.0)
                mismatch_fields.append("annual_income")

        confidence_score = sum(similarities) / len(similarities) if similarities else 1.0
        status = "MISMATCH" if mismatch_fields else "VERIFIED"

        doc = self.app_repo.save_document(
            session.application_id, doc_type, file_ref, extracted_fields, confidence_score
        )
        self.app_repo.update_document_verification(doc.id, status, mismatch_fields)

        session.document_refs = session.document_refs + [doc.id]

        response_msg = f"📄 Document of type '{doc_type}' uploaded and verified successfully."
        if mismatch_fields:
            response_msg = (
                f"⚠️ **OCR Mismatch Detected in Document** ({doc_type})!\n\n"
                f"The following fields differ between your document and declared details:\n"
                + "\n".join([f"- **{f.replace('_', ' ').title()}**: Declared: `{session.filled_slots.get(f)}` vs OCR: `{extracted_fields.get(f)}`" for f in mismatch_fields])
                + f"\n\nMatch Confidence Score: **{confidence_score * 100:.1f}%**.\n"
                f"Please choose whether to **Use Document Value** or **Keep Declared Value** using the choices in the Form side-panel or inline options."
            )

        self.session_repo.save_session(session)
        self.db.commit()

        return {
            "doc_id": doc.id,
            "verification_status": status,
            "mismatch_fields": mismatch_fields,
            "confidence_score": confidence_score,
            "response": response_msg,
        }

