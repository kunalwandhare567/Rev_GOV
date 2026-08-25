"""
Pytest configuration and global test fixtures for Rev_GOV test suite.
Provides safe deterministic mock responses for external OpenRouter calls during conversational integration tests.
"""
import pytest
from unittest.mock import patch
from app.llm.openrouter_provider import OpenRouterProvider


@pytest.fixture(autouse=True)
def mock_openrouter_for_e2e(request):
    """
    For e2e and integration conversational tests, mock OpenRouterProvider._call
    so that tests execute deterministically without relying on active paid OpenRouter credits.
    Unit tests in test_ocr_normalization_and_session.py and test_llm_provider.py
    override or test raw behavior explicitly.
    """
    # If the test explicitly tests OpenRouter error handling or raw provider, do not override
    if "test_ocr_normalization_and_session" in request.node.nodeid or "test_llm_provider" in request.node.nodeid:
        yield
        return

    def mock_call(self, messages, temperature=0.3, max_tokens=100, timeout=45.0):
        # Extract user message
        user_content = ""
        for m in messages:
            if m.get("role") == "user":
                user_content = m.get("content", "")

        user_lower = user_content.lower()

        # Extract citizen utterance specifically from prompt
        utterance = ""
        if "Citizen Utterance:" in user_content:
            utterance = user_content.split("Citizen Utterance:")[1].split("\n")[0].strip()
        else:
            utterance = user_content.strip()

        utt_lower = utterance.lower()

        # Handle NLU extraction calls
        if "citizen utterance:" in user_lower or "nlu" in user_lower:
            intent = "UNKNOWN"
            service_type = None
            entities = {}

            if "income" in utt_lower or "aay" in utt_lower or "utpanna" in utt_lower:
                intent = "CERTIFICATE_REQUEST"
                service_type = "income_certificate"
            elif "caste" in utt_lower or "jati" in utt_lower:
                intent = "CERTIFICATE_REQUEST"
                service_type = "caste_certificate"
            elif "domicile" in utt_lower or "residence" in utt_lower:
                intent = "CERTIFICATE_REQUEST"
                service_type = "domicile_certificate"
            elif "status" in utt_lower or "track" in utt_lower or "app-" in utt_lower:
                intent = "STATUS_QUERY"
            elif utt_lower in ("yes", "y", "agree", "accept", "i agree", "ha", "haan", "ho", "1"):
                intent = "SLOT_ANSWER"
                entities["consent"] = "yes"
            elif utt_lower in ("hello", "hi", "hey", "namaste", "namaskar"):
                intent = "GREETING"
            else:
                intent = "SLOT_ANSWER"

            # Check entity extraction
            if "name is " in utt_lower:
                name_val = utterance.split("name is ")[-1].split("\n")[0].strip()
                entities["applicant_name"] = name_val
            elif "ramesh" in utt_lower:
                entities["applicant_name"] = "Ramesh Kumar"
            elif "kunal" in utt_lower:
                entities["applicant_name"] = "Kunal Wandhare"
            elif "viki" in utt_lower:
                entities["applicant_name"] = "Viki Bhausaheb Lokhande"
            elif "ananya" in utt_lower:
                entities["applicant_name"] = "Ananya Sharma"

            if "250000" in utt_lower or "2,50,000" in utt_lower:
                entities["annual_income"] = "250000"
            elif "120000" in utt_lower or "1,20,000" in utt_lower:
                entities["annual_income"] = "120000"
            elif "300000" in utt_lower or "3,00,000" in utt_lower:
                entities["annual_income"] = "300000"
            elif "50000" in utt_lower:
                entities["annual_income"] = "50000"

            return f'''{{
              "intent": "{intent}",
              "service_type": {f'"{service_type}"' if service_type else "null"},
              "entities": {str(entities).replace("'", '"')},
              "pii_detected": [],
              "literacy_level": "MEDIUM",
              "language": "en",
              "is_cross_question": false,
              "cross_question_target": null
            }}'''

        # Handle OCR normalization
        # Handle OCR normalization
        if "raw document ocr text" in user_lower:
            return '''{
              "normalized_fields": {
                "applicant_name": "Viki Bhausaheb Lokhande",
                "annual_income": "250000"
              },
              "confidence": {"applicant_name": 0.95},
              "corrections": []
            }'''

        return "How may I help you with your revenue certificate application today?"

    with patch.object(OpenRouterProvider, "_call", mock_call):
        yield
