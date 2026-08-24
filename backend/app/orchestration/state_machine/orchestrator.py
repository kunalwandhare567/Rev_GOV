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

from app.orchestration.nlu.local_llm import NLUService, LiteracyAdaptiveDialogue
from app.orchestration.nlu.intent_classifier import IntentClassifier, QAHandler  # Phase 5
from app.orchestration.nlu.field_corrector import FieldCorrector                  # Phase 5
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
    "DOCUMENT_CAPTURE": ["DOCUMENT_VERIFY", "SLOT_FILLING", "VALIDATION", "PAYMENT", "CORRECTION_PROMPT"],
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
        # Phase 3: LLM-powered NLU (replaces Ollama LocalNLU)
        self.nlu = NLUService()
        self.intent_clf = IntentClassifier()   # Phase 5: richer intent + slot classifier
        self.qa_handler = QAHandler()          # Phase 5: FAQ answers
        self.field_corrector = FieldCorrector()# Phase 5: field value auto-correction
        self.session_repo = SessionRepository(db)
        self.app_repo = ApplicationRepository(db)
        self.citizen_repo = CitizenRepository(db)
        self.audit_repo = AuditRepository(db)
        # Phase 5: NextQuestionEngine for dynamic slot ordering
        from app.services.next_question_engine import NextQuestionEngine
        self.next_q_engine = NextQuestionEngine()
        # Phase 4+6: RAG service for knowledge-grounded answers
        from app.services.rag_service import RAGService
        self.rag = RAGService()

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

        # 2. Run NLU (NLUService — LLM-powered, no Ollama)
        nlu_result = self.nlu.analyze(text, language=session.language, context={
            "current_node": session.current_node,
            "filled_slots": session.filled_slots,
            "service_id": getattr(session, "application_id", None),
        })

        # Phase 5: Enrich with IntentClassifier (richer keyword scoring)
        clf_result = self.intent_clf.classify(
            text, language=session.language,
            conversation_state=session.current_node,
        )
        # Merge: prefer IntentClassifier if confidence > 0.5, else use LocalNLU
        if clf_result.get("confidence", 0) > 0.5:
            nlu_result["intent"] = clf_result["intent"]
            nlu_result["service_type"] = self._normalize_service_id(
                clf_result.get("service_type") or nlu_result.get("service_type"), text
            )
            # Merge entities
            nlu_result.setdefault("entities", {}).update(clf_result.get("entities", {}))

        # Phase 5: Check FAQ if ASK_HELP intent
        if nlu_result.get("intent") == "ASK_HELP":
            faq_answer = self.qa_handler.answer(text, session.language)
            if faq_answer:
                nlu_result["faq_answer"] = faq_answer

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

    @staticmethod
    def _normalize_service_id(service_raw: Optional[str], text: str = "") -> Optional[str]:
        """Maps LLM service type variants to valid system service IDs."""
        if service_raw:
            clean = str(service_raw).strip().lower().replace(" ", "_").replace("-", "_")
            alias_map = {
                "income_certificate": "income_certificate",
                "income": "income_certificate",
                "get_income": "income_certificate",
                "income_proof": "income_certificate",
                "finance": "income_certificate",

                "caste_certificate": "caste_certificate",
                "caste": "caste_certificate",
                "get_caste": "caste_certificate",

                "domicile_certificate": "domicile_certificate",
                "domicile": "domicile_certificate",
                "get_domicile": "domicile_certificate",
                "residence_certificate": "domicile_certificate",

                "obc_ncl_certificate": "obc_ncl_certificate",
                "obc": "obc_ncl_certificate",
                "obc_ncl": "obc_ncl_certificate",
            }
            if clean in alias_map:
                return alias_map[clean]

            for valid_id in ["income_certificate", "caste_certificate", "domicile_certificate", "obc_ncl_certificate"]:
                if valid_id in clean or clean in valid_id:
                    return valid_id

        # Text keyword fallback for generic LLM values (e.g. "Government_Services", "FINANCE")
        t = (text or "").lower()
        if any(k in t for k in ["income", "आय", "उत्पन्न"]):
            return "income_certificate"
        if any(k in t for k in ["caste", "जाति", "जाती"]):
            return "caste_certificate"
        if any(k in t for k in ["domicile", "residence", "अधिवास", "रहवासी"]):
            return "domicile_certificate"
        if any(k in t for k in ["obc", "ncl", "non creamy", "नॉन क्रीमी"]):
            return "obc_ncl_certificate"
        return None

    def _handle_intent(self, session, nlu_result):
        """INTENT_DETECTION: Identify service type and move to slot filling."""
        raw_service = nlu_result.get("service_type")
        raw_text = nlu_result.get("raw_text", "")
        service_type = self._normalize_service_id(raw_service, raw_text)
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

        # ── Phase 12: Application Deduplication ──
        # If citizen already has an active application for this service
        # (started via WhatsApp, Web, or IVR), resume it instead of creating a new one.
        existing_app = self.app_repo.get_active_by_citizen_service(
            citizen_ref=session.citizen_ref,
            service_id=service_type,
        )
        if existing_app:
            session.application_id = existing_app.id
            # Restore filled slots from DB
            session.filled_slots = self.app_repo.get_fields(existing_app.id) or {}
            all_slots = [s.name for s in spec.slots if s.required]
            session.missing_slots = [s for s in all_slots if s not in session.filled_slots]
            service_name = spec.name.get(session.language, spec.name.get("en", service_type)) \
                if isinstance(spec.name, dict) else str(spec.name)

            resume_msg = self._multilang_msg(session.language, {
                "en": (
                    f"📋 Welcome back! You already have an application in progress:\n"
                    f"Application No: **{existing_app.application_number}**\n"
                    f"Status: {existing_app.status}\n"
                    f"Fields filled: {len(session.filled_slots)}/{len(all_slots)}\n\n"
                    f"Resuming your {service_name} application. "
                    + (self._get_next_slot_prompt(session, spec) if session.missing_slots else "All fields are filled. Type 'next' to proceed to documents.")
                ),
                "hi": (
                    f"📋 वापस स्वागत है! आपका पहले से एक आवेदन चल रहा है:\n"
                    f"आवेदन संख्या: **{existing_app.application_number}**\n"
                    f"स्थिति: {existing_app.status}\n\n"
                    f"{service_name} आवेदन फिर से शुरू हो रहा है। "
                    + (self._get_next_slot_prompt(session, spec) if session.missing_slots else "सभी विवरण भर गए हैं। अगले चरण के लिए 'आगे' टाइप करें।")
                ),
            })
            return resume_msg, "SLOT_FILLING", {
                "application_id": existing_app.id,
                "application_number": existing_app.application_number,
                "resumed": True,
            }

        # Create NEW application
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
        """SLOT_FILLING: Iteratively collect required form fields.

        Phase 5: Uses NextQuestionEngine for dynamic slot ordering (not hardcoded list).
        Phase 6: Cross-question detection — if citizen asks a digression,
                 handle it via RAG+LLM and return to the same pending slot.
        """
        if not session.application_id:
            return self._handle_intent(session, nlu_result)

        db_app = self.app_repo.get_by_id(session.application_id)
        if not db_app:
            return "Application not found.", "ESCALATION", {}

        spec = ServiceSpecLoader.get(db_app.service_id)
        if not spec:
            return "Service spec not found.", "ESCALATION", {}

        # ── Phase 6: Cross-question detection ──
        if nlu_result.get("is_cross_question") or self._is_cross_question(raw_text):
            return self._handle_cross_question(
                session, raw_text, nlu_result, spec
            )

        entities = nlu_result.get("entities", {})

        # ── Phase 5: Get next slot via NextQuestionEngine ──
        # This respects YAML order, OCR-prefilled fields, and validation errors.
        ocr_fields = getattr(session, "ocr_fields", {}) or {}
        validation_errors = {e: "invalid" for e in (session.validation_errors or [])}

        nq_result = self.next_q_engine.get_next_slot(
            service_id=db_app.service_id,
            filled_slots=session.filled_slots or {},
            ocr_fields=ocr_fields,
            validation_errors=validation_errors,
        )

        slot_map = {s.name: s for s in spec.slots}
        next_missing = nq_result.slot_name  # None if all filled

        # Try to fill the next missing slot from the utterance
        filled_something = False

        if next_missing and next_missing in slot_map:
            slot = slot_map[next_missing]
            candidate_value = entities.get(next_missing) or raw_text.strip()

            # ── Auto-correct field value before validation ──
            corrected_value, was_corrected, correction_note = self.field_corrector.correct(
                next_missing, candidate_value, session.language
            )
            if was_corrected:
                logger.info(f"FieldCorrector [{next_missing}]: {candidate_value!r} -> {corrected_value!r} ({correction_note})")
                candidate_value = corrected_value

            valid, error = FieldValidator.validate_slot(slot, candidate_value, session.language)
            if valid:
                session.filled_slots = {**session.filled_slots, next_missing: candidate_value}
                if next_missing in (session.missing_slots or []):
                    session.missing_slots = [s for s in session.missing_slots if s != next_missing]
                filled_something = True

                # Save to DB
                self.app_repo.save_field(
                    session.application_id, next_missing, candidate_value, slot.classification
                )
            else:
                error_msg = self._multilang_msg(session.language, {
                    "en": f"\u26a0\ufe0f {error} Please try again.",
                    "hi": f"\u26a0\ufe0f {error} \u0915\u0943\u092a\u092f\u093e \u092a\u0941\u0928\u0903 \u092a\u094d\u0930\u092f\u093e\u0938 \u0915\u0930\u0947\u0902\u0964",
                })
                session.validation_errors = (session.validation_errors or []) + [error]
                return error_msg, "SLOT_FILLING", {"field": next_missing, "error": error}

        # Also fill from NLU entities for other slots
        for slot_name, value in entities.items():
            if slot_name in slot_map and slot_name not in (session.filled_slots or {}):
                sl = slot_map[slot_name]
                valid, _ = FieldValidator.validate_slot(sl, value, session.language)
                if valid:
                    session.filled_slots = {**session.filled_slots, slot_name: value}
                    if slot_name in (session.missing_slots or []):
                        session.missing_slots = [s for s in session.missing_slots if s != slot_name]
                    self.app_repo.save_field(
                        session.application_id, slot_name, value, sl.classification
                    )

        # Re-compute after filling
        nq_result = self.next_q_engine.get_next_slot(
            service_id=db_app.service_id,
            filled_slots=session.filled_slots or {},
            ocr_fields=ocr_fields,
        )

        if not nq_result.has_next:
            # All slots filled — move to document capture
            if spec.required_docs:
                doc_list = []
                for d in spec.required_docs:
                    if isinstance(d, dict):
                        doc_list.append(f"\ud83d\udcc4 {d.get('type', d)}: {', '.join(d.get('accepted', []))}")
                    else:
                        doc_list.append(f"\ud83d\udcc4 {d}")

                msg = self._multilang_msg(session.language, {
                    "en": (
                        "\u2705 All details collected! Now please upload your documents:\n" +
                        "\n".join(doc_list) +
                        "\n\nUse the attachment button or describe the document you're uploading."
                    ),
                    "hi": (
                        "\u2705 \u0938\u092d\u0940 \u091c\u093e\u0928\u0915\u093e\u0930\u0940 \u090f\u0915\u0924\u094d\u0930 \u0939\u094b \u0917\u0908! \u0905\u092c \u0915\u0943\u092a\u092f\u093e \u0926\u0938\u094d\u0924\u093e\u0935\u0947\u091c\u093c \u0905\u092a\u0932\u094b\u0921 \u0915\u0930\u0947\u0902:\n" +
                        "\n".join([f"\ud83d\udcc4 {d.get('type', d) if isinstance(d, dict) else d}" for d in spec.required_docs])
                    ),
                })
                return msg, "DOCUMENT_CAPTURE", {
                    "completion_pct": nq_result.completion_percentage,
                    "filled_count": nq_result.filled_count,
                }
            else:
                return self._handle_validation(session)

        # More slots — generate next question via LLM (Phase 5)
        next_slot_prompt = self._get_next_slot_prompt_llm(
            session, spec, nq_result
        )
        progress_note = f" ({nq_result.filled_count}/{nq_result.total_required} fields)"

        return (
            f"{next_slot_prompt}{progress_note}",
            "SLOT_FILLING",
            {
                "next_slot": nq_result.slot_name,
                "completion_pct": nq_result.completion_percentage,
                "filled_count": nq_result.filled_count,
                "total_required": nq_result.total_required,
            },
        )

    def _handle_document_capture(self, session, nlu_result):
        """DOCUMENT_CAPTURE: Guide document upload, then route to Admin pre-approval."""
        app = self.app_repo.get_by_id(session.application_id) if session.application_id else None
        if not app:
            return "Application not found.", "ESCALATION", {}

        spec = ServiceSpecLoader.get(app.service_id)
        required_doc_types = [d["type"] for d in (spec.required_docs if spec else [])]

        # Check uploaded document types
        uploaded_doc_types = [d.doc_type for d in (app.documents or []) if d.verification_status != "REJECTED"]
        missing_doc_types = [dt for dt in required_doc_types if dt not in uploaded_doc_types]

        raw_text = (nlu_result.get("raw_text") or "").lower().strip()

        # Auto-advance if all docs uploaded or user explicitly asks to proceed
        advance_keywords = ["done", "skip", "next", "proceed", "continue", "what next", "finish", "review", "upload done", "now what"]
        should_advance = (not missing_doc_types) or any(w in raw_text for w in advance_keywords)

        if should_advance:
            # Transition app FSM to PENDING_OFFICER_PRE_APPROVAL
            try:
                from app.orchestration.state_machine.application_fsm import AppState
                self.app_repo.update_status(session.application_id, AppState.PENDING_OFFICER_PRE_APPROVAL)
            except Exception as e:
                logger.warning(f"Could not update app status to PENDING_OFFICER_PRE_APPROVAL: {e}")

            msg = self._multilang_msg(session.language, {
                "en": (
                    "✅ All documents uploaded and scanned!\n\n"
                    "📋 Your application has been sent to the Admin for document pre-verification.\n"
                    "You will receive a notification here once the Admin reviews and approves your documents.\n\n"
                    "⏳ Please wait — no payment is required until Admin approval."
                ),
                "hi": (
                    "✅ सभी दस्तावेज़ अपलोड और स्कैन हो गए!\n\n"
                    "📋 आपका आवेदन Admin को पूर्व-सत्यापन के लिए भेज दिया गया है।\n"
                    "Admin के अनुमोदन के बाद आपको यहाँ सूचना मिलेगी।\n\n"
                    "⏳ कृपया प्रतीक्षा करें — Admin की स्वीकृति तक कोई भुगतान आवश्यक नहीं है।"
                ),
                "mr": (
                    "✅ सर्व कागदपत्रे अपलोड आणि स्कॅन झाली!\n\n"
                    "📋 तुमचा अर्ज Admin कडे पूर्व-पडताळणीसाठी पाठवला आहे.\n"
                    "Admin मंजुरीनंतर तुम्हाला येथे सूचना मिळेल.\n\n"
                    "⏳ कृपया प्रतीक्षा करा — Admin मंजुरीपर्यंत कोणतेही शुल्क लागत नाही."
                ),
            })
            return msg, "DOCUMENT_CAPTURE", {}

        # Still missing documents — prompt user specifically
        missing_str = ", ".join([dt.replace("_", " ").title() for dt in missing_doc_types])
        msg = self._multilang_msg(session.language, {
            "en": (
                f"📄 Document Upload Progress ({len(uploaded_doc_types)}/{len(required_doc_types)} uploaded)\n"
                f"Still required: *{missing_str}*\n\n"
                "Please upload the required document using the 📎 attachment button."
            ),
            "hi": (
                f"📄 दस्तावेज़ अपलोड प्रगति ({len(uploaded_doc_types)}/{len(required_doc_types)})\n"
                f"आवश्यक: *{missing_str}*\n\n"
                "कृपया संलग्नक बटन से दस्तावेज़ अपलोड करें।"
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

    def _handle_cross_question(self, session, raw_text: str, nlu_result: dict, spec) -> tuple:
        """
        Phase 6 — Cross-Question Handler.

        When a citizen asks a digression (e.g., "why do you need my father's name?"),
        we:
          1. Retrieve relevant knowledge from the RAG knowledge base.
          2. Ask LLM to answer using ONLY retrieved context (no hallucination).
          3. After answering, prompt the citizen to return to the PENDING slot.

        The pending slot is preserved throughout the digression.
        """
        from app.llm.llm_service import LLMService
        llm = LLMService()

        # Identify what slot was being asked about
        db_app = self.app_repo.get_by_id(session.application_id) if session.application_id else None
        service_id = db_app.service_id if db_app else None

        # Get the current pending slot from NextQuestionEngine
        ocr_fields = getattr(session, "ocr_fields", {}) or {}
        nq_result = self.next_q_engine.get_next_slot(
            service_id=service_id or "",
            filled_slots=session.filled_slots or {},
            ocr_fields=ocr_fields,
        )
        pending_field = nq_result.slot_name  # The slot we were about to ask

        # Retrieve knowledge chunks for this question
        chunks = self.rag.retrieve(
            question=raw_text,
            service_id=service_id,
            max_chunks=4,
        )

        if chunks:
            # RAG-grounded answer via LLM
            try:
                answer = llm.answer_rag(
                    question=raw_text,
                    knowledge_chunks=chunks,
                    language=session.language,
                )
            except Exception as e:
                logger.warning(f"RAG LLM answer failed: {e}")
                answer = self._multilang_msg(session.language, {
                    "en": "I don't have specific information on that, but your local Seva Kendra can help.",
                    "hi": "इस बारे में मुझे विशेष जानकारी नहीं है, लेकिन आपका स्थानीय सेवा केंद्र सहायता कर सकता है।",
                    "mr": "याबद्दल माझ्याकडे विशिष्ट माहिती नाही, पण स्थानिक सेवा केंद्र मदत करू शकते.",
                })
        else:
            # No relevant knowledge found
            answer = self._multilang_msg(session.language, {
                "en": "I don't have specific information on that. Please contact your nearest Seva Kendra.",
                "hi": "इस बारे में मुझे जानकारी नहीं है। कृपया निकटतम सेवा केंद्र से संपर्क करें।",
                "mr": "याबद्दल माझ्याकडे माहिती नाही. कृपया जवळच्या सेवा केंद्राशी संपर्क करा.",
            })

        # Pivot back to pending slot
        if pending_field:
            db_app_for_spec = self.app_repo.get_by_id(session.application_id) if session.application_id else None
            spec_for_pending = ServiceSpecLoader.get(db_app_for_spec.service_id) if db_app_for_spec else spec
            slot_map = {s.name: s for s in spec_for_pending.slots} if spec_for_pending else {}
            slot = slot_map.get(pending_field)

            if slot:
                pending_prompt = LiteracyAdaptiveDialogue.get_slot_prompt(
                    slot, session.language, session.literacy_level or "MEDIUM"
                )
            else:
                pending_prompt = f"Please provide your {pending_field.replace('_', ' ')}:"

            pivot_suffix = self._multilang_msg(session.language, {
                "en": f"\n\nNow, back to your application — {pending_prompt}",
                "hi": f"\n\nअब, आपके आवेदन पर वापस आते हैं — {pending_prompt}",
                "mr": f"\n\nआता, तुमच्या अर्जावर परत येऊ — {pending_prompt}",
            })
            full_response = answer + pivot_suffix
        else:
            full_response = answer

        return full_response, "SLOT_FILLING", {
            "cross_question": True,
            "pending_field": pending_field,
        }

    def _get_next_slot_prompt_llm(self, session, spec, nq_result) -> str:
        """
        Phase 5: Generate the next slot question via LLM (dynamic, natural language).
        Falls back to YAML static prompt if LLM fails.
        """
        if not nq_result.slot_name or not nq_result.slot_spec:
            return self._get_next_slot_prompt(session, spec)

        try:
            from app.llm.llm_service import LLMService
            llm = LLMService()
            service_name = spec.name.get(session.language, spec.name.get("en", spec.id)) \
                if isinstance(spec.name, dict) else str(spec.name)
            return llm.generate_slot_prompt(
                slot_name=nq_result.slot_name,
                slot_spec=nq_result.slot_spec,
                language=session.language,
                context={
                    "service_name": service_name,
                    "filled_count": nq_result.filled_count,
                    "total_required": nq_result.total_required,
                },
            )
        except Exception as e:
            logger.warning(f"LLM slot prompt failed, using YAML fallback: {e}")
            return self._get_next_slot_prompt(session, spec)

    def _get_next_slot_prompt(self, session, spec) -> str:
        """Get static YAML prompt for the next missing slot (fallback)."""
        if not session.missing_slots:
            return ""
        # Phase 5: Try NextQuestionEngine first
        ocr_fields = getattr(session, "ocr_fields", {}) or {}
        db_app = self.app_repo.get_by_id(session.application_id) if session.application_id else None
        if db_app:
            nq = self.next_q_engine.get_next_slot(
                service_id=db_app.service_id,
                filled_slots=session.filled_slots or {},
                ocr_fields=ocr_fields,
            )
            if nq.has_next:
                slot_map = {s.name: s for s in spec.slots}
                slot = slot_map.get(nq.slot_name)
                if slot:
                    return LiteracyAdaptiveDialogue.get_slot_prompt(
                        slot, session.language, session.literacy_level or "MEDIUM"
                    )
        # Fallback: old hardcoded order
        next_slot_name = session.missing_slots[0]
        slot_map = {s.name: s for s in spec.slots}
        slot = slot_map.get(next_slot_name)
        if not slot:
            return f"Please provide: {next_slot_name}"
        return LiteracyAdaptiveDialogue.get_slot_prompt(slot, session.language, session.literacy_level or "MEDIUM")

    def _multilang_msg(self, language: str, messages: Dict[str, str]) -> str:
        """Return message in preferred language, falling back to English."""
        return messages.get(language, messages.get("en", list(messages.values())[0]))

    def _get_sla(self, service_id: str) -> int:
        spec = ServiceSpecLoader.get(service_id)
        return spec.sla_days if spec else 7

    def process_document_upload(
        self, citizen_ref: str, doc_type: str, file_ref: str, extracted_fields: Dict
    ) -> Dict:
        """
        Handle document upload, run OCR cross-reference matching,
        generate a structured mismatch report, store it as a chat message
        so the citizen sees it immediately, and return a full ValidationReport.
        """
        session = self.session_repo.load_session(citizen_ref)
        if not session or not session.application_id:
            return {"error": "No active session found"}

        # ── Special Case: PAYMENT_RECEIPT ─────────────────────────────────
        if doc_type == "PAYMENT_RECEIPT":
            amount = 50.0
            if "amount" in extracted_fields:
                try:
                    amount = float(str(extracted_fields["amount"]).replace(",", ""))
                except Exception:
                    pass
            import uuid
            txn_id = extracted_fields.get("transaction_id") or f"UPI{str(uuid.uuid4())[:8].upper()}"

            payment = self.app_repo.create_payment(session.application_id, amount, txn_id)
            self.app_repo.update_payment_status(txn_id, "SUCCESS")
            session.payment_status = "PAID"
            session.current_node = "SUBMISSION"
            self.app_repo.update_status(session.application_id, "SUBMITTED")

            self.audit_repo.write(
                event_type="PAYMENT", actor="OCR_RECEIPT_VERIFIER",
                citizen_ref=citizen_ref, application_id=session.application_id,
                action=f"Payment verified via receipt upload: ₹{amount}, TXN {txn_id}",
                outcome="SUCCESS",
            )
            self.audit_repo.write(
                event_type="SUBMISSION", actor="CITIZEN",
                citizen_ref=citizen_ref, application_id=session.application_id,
                action="Application submitted after payment validation", outcome="SUCCESS",
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

            # Store as chat message so citizen sees it immediately
            self.session_repo.add_message(
                session_id=session.id, role="ASSISTANT", content=response_msg,
                language=session.language, modality="TEXT",
            )

            return {
                "doc_id": payment.id,
                "verification_status": "VERIFIED",
                "mismatch_fields": [],
                "matched_fields": [],
                "fields_not_in_doc": [],
                "confidence_score": 1.0,
                "response": response_msg,
                "current_node": "SUBMISSION",
                "payment_status": "PAID",
            }

        # ── Step A: Structured Log & Auto-prefill slots from OCR ─────────────
        logger.info(
            f"[OCR_DOCUMENT_PROCESSING] Citizen={citizen_ref}, ApplicationId={session.application_id}, "
            f"DocType={doc_type}, ExtractedFields={list(extracted_fields.keys())}"
        )

        prefilled_count = 0
        if extracted_fields and session.application_id:
            db_app = self.app_repo.get_by_id(session.application_id)
            if db_app:
                spec = ServiceSpecLoader.get(db_app.service_id)
                slot_map = {s.name: s for s in spec.slots} if spec and spec.slots else {}
                ocr_fields = getattr(session, "ocr_fields", {}) or {}

                for field_name, val in extracted_fields.items():
                    if val is not None and str(val).strip():
                        val_str = str(val).strip()
                        ocr_fields[field_name] = val_str
                        if field_name in slot_map and field_name not in (session.filled_slots or {}):
                            sl = slot_map[field_name]
                            valid, _ = FieldValidator.validate_slot(sl, val_str, session.language)
                            if valid:
                                session.filled_slots = {**session.filled_slots, field_name: val_str}
                                if field_name in (session.missing_slots or []):
                                    session.missing_slots = [s for s in session.missing_slots if s != field_name]
                                self.app_repo.save_field(
                                    session.application_id, field_name, val_str, sl.classification, source="OCR"
                                )
                                prefilled_count += 1

                session.ocr_fields = ocr_fields

        logger.info(
            f"[OCR_SLOT_PREFILL] Auto-prefilled {prefilled_count} missing application slots from OCR document proof."
        )

        # ── Cross-reference: compare declared chat slots vs OCR fields ─────
        from app.services.matching_service import MatchingService
        matcher = MatchingService()

        # Pass doc_type so priority fields for that document type are considered
        match_res = matcher.compare_document(
            session.filled_slots, extracted_fields, doc_type=doc_type
        )

        mismatch_fields = match_res.mismatched_fields
        fields_not_in_doc = match_res.fields_only_in_app   # Declared but not in OCR
        confidence_score = (match_res.overall_score / 100.0) if match_res.overall_score is not None else 1.0

        # Determine verification status
        if mismatch_fields:
            status = "MISMATCH"
        elif match_res.overall_score == 0.0 and not match_res.matched_fields:
            status = "INCOMPLETE"   # OCR returned nothing useful
        else:
            status = "VERIFIED"

        # Save document record
        doc = self.app_repo.save_document(
            session.application_id, doc_type, file_ref, extracted_fields, confidence_score
        )
        self.app_repo.update_document_verification(doc.id, status, mismatch_fields)
        session.document_refs = session.document_refs + [doc.id]

        # ── Generate response message ──────────────────────────────────────
        if status == "VERIFIED":
            response_msg = matcher._all_match_message(match_res, session.language)

        elif status == "INCOMPLETE":
            msgs = {
                "en": (
                    f"📄 Document ({doc_type}) uploaded.\n"
                    f"⚠️ No text could be extracted from this document. "
                    f"Please ensure the image is clear and Tesseract OCR is installed "
                    f"at C:\\Program Files\\Tesseract-OCR\\tesseract.exe."
                ),
                "hi": (
                    f"📄 आपका दस्तावेज़ ({doc_type}) अपलोड हो गया।\n"
                    f"⚠️ दस्तावेज़ से कोई भी फ़ील्ड निकाला नहीं जा सका। "
                    f"Tesseract OCR इंस्टॉल होना आवश्यक है।"
                ),
                "mr": (
                    f"📄 तुमचे कागदपत्र ({doc_type}) अपलोड झाले.\n"
                    f"⚠️ कागदपत्रातून कोणताही तपशील काढता आला नाही."
                ),
            }
            response_msg = msgs.get(session.language, msgs["en"])

        else:
            # MISMATCH — use MatchingService (tries Gemini, then structured template)
            response_msg = matcher.generate_mismatch_message(
                match_res, language=session.language, use_gemini=True
            )

        # ── State transition & Next Process Connection ──────────────────────
        if status == "MISMATCH":
            if _valid_transition(session.current_node, "CORRECTION_PROMPT"):
                session.current_node = "CORRECTION_PROMPT"
                logger.info(f"[OCR_STATE_CONNECT] Mismatch detected. Transitioned state to CORRECTION_PROMPT")
        elif status == "VERIFIED":
            if session.current_node in ("DOCUMENT_CAPTURE", "DOCUMENT_VERIFY"):
                db_app = self.app_repo.get_by_id(session.application_id)
                if db_app:
                    spec = ServiceSpecLoader.get(db_app.service_id)
                    req_docs = [d["type"] if isinstance(d, dict) else d for d in (spec.required_docs if spec else [])]
                    uploaded_docs = [d.doc_type for d in (db_app.documents or []) if d.verification_status != "REJECTED"]
                    if all(rd in uploaded_docs for rd in req_docs):
                        from app.orchestration.state_machine.application_fsm import AppState
                        self.app_repo.update_status(session.application_id, AppState.PENDING_OFFICER_PRE_APPROVAL)
                        logger.info(f"[OCR_STATE_CONNECT] All proof documents verified for App {session.application_id}. Transitioned status to PENDING_OFFICER_PRE_APPROVAL")

        # ── Store as chat message — CRITICAL: citizen must see this in chat ─
        self.session_repo.add_message(
            session_id=session.id,
            role="ASSISTANT",
            content=response_msg,
            language=session.language,
            modality="TEXT",
        )

        # ── Audit log ──────────────────────────────────────────────────────
        self.audit_repo.write(
            event_type="DOCUMENT_VERIFIED",
            actor="OCR_ENGINE",
            citizen_ref=citizen_ref,
            application_id=session.application_id,
            action=(
                f"Document {doc_type} processed. Status={status}. "
                f"Matched={len(match_res.matched_fields)}, "
                f"Mismatched={len(mismatch_fields)}, "
                f"NotInDoc={len(fields_not_in_doc)}, "
                f"Score={match_res.overall_score:.1f}%"
            ),
            outcome=status,
            metadata={
                "doc_id": doc.id,
                "doc_type": doc_type,
                "matched_fields": match_res.matched_fields,
                "mismatch_fields": mismatch_fields,
                "fields_not_in_doc": fields_not_in_doc,
                "overall_score": match_res.overall_score,
            },
        )

        self.session_repo.save_session(session)
        self.db.commit()

        # Build full validation report for frontend
        report = matcher.build_validation_report(match_res)

        return {
            "doc_id": doc.id,
            "verification_status": status,
            "mismatch_fields": mismatch_fields,
            "matched_fields": match_res.matched_fields,
            "fields_not_in_doc": fields_not_in_doc,
            "fields_in_doc_only": match_res.fields_only_in_doc,
            "confidence_score": confidence_score,
            "overall_score": match_res.overall_score,
            "field_scores": match_res.field_scores,
            "can_auto_resolve": report.can_auto_resolve,
            "verdict": report.verdict,
            "summary": report.summary,
            "response": response_msg,
            "current_node": session.current_node,
        }

    def _is_cross_question(self, text: str) -> bool:
        """Check if input is a cross-question/digression rather than a slot answer."""
        text_lower = text.strip().lower()
        question_words = ["why", "what", "how", "where", "when", "can i", "is it", "का", "क्यों", "क्या", "कैसे"]
        is_q = any(w in text_lower for w in question_words) or text_lower.endswith("?")
        return is_q and len(text_lower.split()) > 2

    def _handle_cross_question(self, session, raw_text, nlu_result, spec):
        """Answer citizen digression using RAG/LLM, then resume pending slot."""
        rag_answer = self.rag.answer_question(raw_text, session.language)
        next_prompt = self._get_next_slot_prompt(session, spec)
        combined_response = f"{rag_answer}\n\n{next_prompt}"
        return combined_response, "SLOT_FILLING", {"cross_question_handled": True}






