Absolutely. Below is a **single master prompt** you can directly paste into **Antigravity**.

I have written it specifically around your current `Revenue_Gov_Platform` repository, the POC flow we discussed, and the gaps identified above.

The most important instruction is: **do not rebuild the project from scratch**. Antigravity should inspect the existing implementation and modify/integrate it.

---

# MASTER PROMPT FOR ANTIGRAVITY

```text
You are working on my existing GitHub repository:

Repository:
Revenue_Gov_Platform

Repository URL:
https://github.com/kunalwandhare567/Revenue_Gov_Platform

IMPORTANT:
Do NOT rebuild the project from scratch.
Do NOT remove existing working functionality unnecessarily.
First inspect the complete repository, understand the current architecture, identify reusable modules, and then modify/integrate the existing implementation.

============================================================
1. PROJECT OBJECTIVE
============================================================

The project is a:

"Multilingual AI-Powered Citizen Revenue Services Platform"

The goal is to provide a single AI-driven citizen experience through:

1. Web
2. WhatsApp
3. Voice / IVR
4. Mobile/responsive interface

The citizen should be able to apply for government revenue certificates through natural-language conversation.

Initial POC services:

1. Income Certificate
2. Caste Certificate
3. Domicile Certificate
4. OBC Non-Creamy Layer (NCL) Certificate

The platform must support:

- multilingual conversation
- text conversation
- voice input
- document upload
- OCR
- document validation
- application field auto-fill
- eligibility checking
- document-field matching
- readiness scoring
- final review
- citizen consent
- government verification simulation
- payment after government approval
- payment receipt upload
- certificate completion
- tracking ID
- status tracking
- omnichannel continuity

============================================================
2. VERY IMPORTANT LLM REQUIREMENT
============================================================

REMOVE OLLAMA COMPLETELY FROM THE CHATBOT CONVERSATION FLOW.

DO NOT USE:

- Ollama
- phi3:mini
- local LLM
- local LLM fallback
- keyword-only chatbot fallback
- mock LLM fallback for normal conversation

The conversational AI must use ONLY an external API provider.

Supported providers:

OPTION 1:
OpenRouter

OPTION 2:
Groq

OPTION 3:
Gemini

The system should support all three providers as configuration options, but ONLY ONE provider should be active at runtime.

There must be NO automatic fallback from one provider to another.

Example:

If:

LLM_PROVIDER=gemini

then use Gemini only.

If Gemini fails:

DO NOT switch to Groq.
DO NOT switch to OpenRouter.
DO NOT switch to Ollama.
DO NOT use phi3:mini.
DO NOT use keyword fallback as the conversational AI.

Instead return a proper controlled error message:

"AI service is temporarily unavailable. Please try again."

For POC development, the configured provider must be explicit.

============================================================
3. LLM CONFIGURATION
============================================================

Replace current Ollama/local configuration.

Current configuration contains things such as:

LLM_PROVIDER=local
OLLAMA_BASE_URL
OLLAMA_MODEL=phi3:mini

REMOVE these from active application logic.

Create configuration similar to:

LLM_PROVIDER=gemini

Supported values:

gemini
openrouter
groq

Configuration:

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=

# OpenRouter
OPENROUTER_API_KEY=
OPENROUTER_MODEL=

# Groq
GROQ_API_KEY=
GROQ_MODEL=

Only the selected provider should be initialized.

Create a provider abstraction:

backend/app/llm/

    __init__.py
    base.py
    provider_factory.py
    gemini_provider.py
    openrouter_provider.py
    groq_provider.py
    llm_service.py

Expected architecture:

Conversation
      |
      v
LLMService
      |
      v
ProviderFactory
      |
      +---- GeminiProvider
      |
      +---- OpenRouterProvider
      |
      +---- GroqProvider

No Ollama provider.

No fallback provider.

============================================================
4. LLM RESPONSIBILITIES
============================================================

The LLM must not simply classify keywords.

It must support:

1. Intent detection
2. Service detection
3. Entity extraction
4. Natural language understanding
5. Multilingual conversation
6. Cross-question understanding
7. Application-context questions
8. Document-related questions
9. Status questions
10. Next-question generation
11. Explanation generation
12. Error clarification
13. Resume conversation
14. Human-friendly responses

Examples:

Citizen:
"I want an income certificate"

AI:
"Sure. I can help you apply for an Income Certificate."

Citizen:
"Why do you need my father's name?"

AI:
"Your father's name is required as part of the applicant's personal and family details for this application."

Then resume:

AI:
"What is your father's full name?"

This is called CROSS-QUESTION HANDLING.

Implement it.

============================================================
5. CROSS-QUESTION HANDLING
============================================================

Implement conversation state such as:

pending_question
pending_field
pending_intent
pending_service
conversation_context

Example:

{
    "pending_field": "father_name",
    "pending_question": "What is your father's full name?",
    "service": "income_certificate"
}

If citizen asks:

"Why do you need this?"

The LLM should recognize that this is a cross-question about the pending field.

Answer the question.

Then resume the pending question.

Do NOT lose application state.

============================================================
6. RAG / KNOWLEDGE SYSTEM
============================================================

Add a lightweight RAG/knowledge layer.

The current YAML service specifications are the deterministic source for:

- fields
- validation
- eligibility
- documents
- fees
- SLA
- service configuration

Do NOT replace the existing YAML rules engine.

Instead add a knowledge layer for conversational questions.

Suggested structure:

backend/knowledge/

    services/
        income_certificate/
            overview.md
            eligibility.md
            documents.md
            process.md
            faq.md

        caste_certificate/
            overview.md
            eligibility.md
            documents.md
            process.md
            faq.md

        domicile_certificate/
            overview.md
            eligibility.md
            documents.md
            process.md
            faq.md

        obc_ncl_certificate/
            overview.md
            eligibility.md
            documents.md
            process.md
            faq.md

Create:

backend/app/services/rag_service.py

The RAG system should retrieve relevant knowledge for questions such as:

"What documents are required?"

"Why do I need an income proof?"

"What happens after I submit?"

"How long does verification take?"

"Can I upload Aadhaar?"

"What is the next step?"

IMPORTANT:

The LLM must NOT invent government requirements.

For deterministic eligibility:
Rules Engine is authoritative.

For government requirements:
Knowledge Base/YAML is authoritative.

LLM only explains the authoritative result.

============================================================
7. SINGLE SOURCE OF TRUTH
============================================================

This is a critical architecture requirement.

There must be ONE application record.

Do NOT maintain independent application state for:

- WhatsApp
- Web
- Mobile
- IVR

All channels must operate on the same:

citizen_id
application_id
tracking_id

Architecture:

WhatsApp
    |
Web
    |
Mobile
    |
IVR
    |
    v
Channel Adapter
    |
    v
Application Service
    |
    v
Database

If the citizen enters information on WhatsApp:

annual_income = 300000

then Web must immediately show:

Annual Income: ₹3,00,000

If the citizen edits DOB on Web:

WhatsApp must know the updated DOB.

============================================================
8. CITIZEN IDENTITY
============================================================

Use the existing citizen resolver.

Create a unified citizen model:

Citizen
    |
    + citizen_id
    + phone
    + whatsapp_number
    + email
    + applications[]

Every channel should resolve the citizen to the same citizen_id.

Example:

WhatsApp:
+91XXXXXXXXXX

        |
        v

CITIZEN-1001

        |
        +---- Application INC-2026-0001
        +---- Application CASTE-2026-0002

============================================================
9. APPLICATION LIFECYCLE
============================================================

IMPORTANT:

Correct the current state machine.

The current flow incorrectly places payment before government verification.

The target POC requires:

Citizen completes application
        |
        v
Documents validated
        |
        v
Readiness check
        |
        v
Final review
        |
        v
Citizen consent
        |
        v
Government verification
        |
        v
Government APPROVED
        |
        v
Payment required
        |
        v
Payment completed
        |
        v
Receipt verified
        |
        v
Certificate generated
        |
        v
Completed

Implement the following states:

INITIATED

CONSENT_GIVEN

SERVICE_SELECTED

INFORMATION_COLLECTION

DOCUMENT_COLLECTION

OCR_PROCESSING

VALIDATION_COMPLETED

READINESS_CHECK

FIX_REQUIRED

READY_FOR_REVIEW

FINAL_REVIEW

CONSENT_CONFIRMED

SUBMITTED_FOR_VERIFICATION

UNDER_REVIEW

CLARIFICATION_REQUIRED

APPROVED

PAYMENT_REQUIRED

PAYMENT_COMPLETED

CERTIFICATE_GENERATION

CERTIFICATE_READY

COMPLETED

REJECTED

Do NOT place payment before government verification.

============================================================
10. FSM TRANSITION
============================================================

Expected transition:

INITIATED
    ↓
SERVICE_SELECTED
    ↓
INFORMATION_COLLECTION
    ↓
DOCUMENT_COLLECTION
    ↓
OCR_PROCESSING
    ↓
VALIDATION_COMPLETED
    ↓
READINESS_CHECK
    ↓
FIX_REQUIRED
    ↓
READINESS_CHECK
    ↓
READY_FOR_REVIEW
    ↓
FINAL_REVIEW
    ↓
CONSENT_CONFIRMED
    ↓
SUBMITTED_FOR_VERIFICATION
    ↓
UNDER_REVIEW
    ↓
APPROVED
    ↓
PAYMENT_REQUIRED
    ↓
PAYMENT_COMPLETED
    ↓
CERTIFICATE_GENERATION
    ↓
CERTIFICATE_READY
    ↓
COMPLETED

Clarification path:

UNDER_REVIEW
    ↓
CLARIFICATION_REQUIRED
    ↓
INFORMATION_COLLECTION / DOCUMENT_COLLECTION
    ↓
READINESS_CHECK
    ↓
FINAL_REVIEW
    ↓
SUBMITTED_FOR_VERIFICATION

============================================================
11. INCOME CERTIFICATE POC
============================================================

Use Income Certificate as the PRIMARY end-to-end POC.

Do not attempt to make all four certificates equally sophisticated initially.

The Income Certificate journey must be fully working.

The other certificates should use the same architecture and YAML-driven approach.

============================================================
12. IMPROVE INCOME CERTIFICATE YAML
============================================================

Use the existing:

backend/seed/service_specs/income_certificate.yaml

Do not remove the existing fields.

Extend it with required POC fields such as:

applicant_name
applicant_dob
father_name
mother_name
gender
mobile_number
email
address
district
taluka
village
occupation
annual_income
family_member_count
earning_family_members
annual_family_income
purpose

Only include fields that are appropriate to the configured service.

Every field should support:

name
type
required
classification
validation
prompt

Prompts should support multilingual behavior.

============================================================
13. DYNAMIC QUESTION ENGINE
============================================================

Do NOT hard-code the entire conversation.

Create:

NextQuestionEngine

It should determine:

1. Required fields
2. Already known fields
3. OCR extracted fields
4. User-provided fields
5. Valid fields
6. Invalid fields
7. Missing fields

Then calculate:

next_missing_field

The chatbot should ask only for information that is still required.

Example:

If citizen already gave:

Name
DOB
Address
Annual income

do NOT ask them again.

If Aadhaar OCR already extracted:

Name
DOB
Address

use those values after validation.

============================================================
14. DOCUMENT FLOW
============================================================

Implement:

Citizen uploads document
        ↓
Document stored
        ↓
OCR
        ↓
Extract fields
        ↓
Normalize fields
        ↓
Compare with application
        ↓
Generate match score
        ↓
Identify mismatch
        ↓
Explain mismatch
        ↓
Ask citizen for correction
        ↓
Update application
        ↓
Recalculate score

Example:

Application:
Name = Kunal Wandhare

Aadhaar:
Name = Kunal W.

System:

Name mismatch detected.

AI:
"The name on the uploaded document appears as 'Kunal W.', while your application contains 'Kunal Wandhare'. Would you like to keep the application name or update it?"

Citizen:
"Keep application name."

System records resolution.

============================================================
15. DOCUMENT MATCH SCORE
============================================================

Create a deterministic document matching score.

Example:

Name = 95
DOB = 100
Address = 90
Other relevant fields = 100

Overall:

document_match_score

Do NOT let the LLM randomly generate the score.

The score must be calculated by deterministic code.

============================================================
16. APPLICATION READINESS SCORE
============================================================

Create a separate:

ReadinessEngine

Do NOT confuse:

Document Match Score

with

Application Readiness Score.

Readiness should consider:

Required fields complete
Documents uploaded
OCR completed
OCR validation
Document match
Eligibility
Cross-field consistency
Required corrections
Consent readiness

Example:

Fields complete:       100
Documents:             100
OCR validation:        95
Eligibility:           100
Consistency:            90

Final:

Readiness Score = 96/100

UI:

Application Readiness
96/100
Ready to Submit

If issues exist:

Application Readiness
87/100
Needs Minor Fix

============================================================
17. EVIDENCE GRAPH
============================================================

Implement a lightweight evidence graph concept.

Example:

Applicant
    |
    +---- Declared Name
    |
    +---- Declared DOB
    |
    +---- Declared Income
    |
    +---- Aadhaar
    |       |
    |       +---- Name
    |       +---- DOB
    |
    +---- Income Proof
            |
            +---- Income

The graph should help explain:

Which document supports which field.

Which fields conflict.

Which fields are verified.

Which fields are missing evidence.

This can initially be represented as structured JSON rather than a complex graph database.

============================================================
18. WEB APPLICATION FORM
============================================================

Modify the existing ApplicationReview UI.

The current UI has tabs such as:

Overview
Application Fields
Documents
Timeline

Keep useful existing functionality, but create the citizen-facing POC experience with FOUR major sections.

SECTION 1:
Basic / Application Details

SECTION 2:
Personal & Family Details

SECTION 3:
Documents & Validation

SECTION 4:
Final Review

UI:

------------------------------------------------
Income Certificate
Progress: 85%
------------------------------------------------

[1 Details] [2 Personal] [3 Documents] [4 Review]

Each section should auto-populate from the central application.

============================================================
19. SECTION 1
============================================================

Show:

Service
Applicant Name
DOB
Mobile
Email
Address
Purpose

Fields should be editable.

Changes must update the central application.

============================================================
20. SECTION 2
============================================================

Show:

Father Name
Mother Name
Occupation
Annual Income
Family Members
Earning Family Members
Family Income
Other required service fields

============================================================
21. SECTION 3
============================================================

Show:

Required documents

For each document:

Document name
Upload status
OCR status
Extracted fields
Match score
Mismatch
Resolution

Example:

Aadhaar
✓ Uploaded
✓ OCR Complete
Match Score: 96%

Income Proof
✓ Uploaded
⚠ Income mismatch

Allow:

Upload
Replace
View
Resolve mismatch

============================================================
22. SECTION 4
============================================================

Show:

Application Summary

Personal Details
Family Details
Income Details
Documents
Eligibility
Document Match
Readiness

Example:

----------------------------------
APPLICATION READINESS
96 / 100
READY TO SUBMIT
----------------------------------

✓ Required information complete
✓ Documents uploaded
✓ OCR validated
✓ Eligibility passed
✓ Document consistency passed

Then:

[ ] I confirm that the information provided is correct.

[Submit for Government Verification]

The submit button must remain disabled until required conditions are satisfied.

============================================================
23. WEB ↔ WHATSAPP AUTO SYNCHRONIZATION
============================================================

If a citizen starts on WhatsApp:

"I want income certificate"

The system creates application.

When citizen opens Web application:

the existing application must automatically appear.

No second application should be created.

Example:

WhatsApp:

Application:
INC-2026-0001

Web:

Application:
INC-2026-0001

Same:

citizen_id
application_id
tracking_id

============================================================
24. TRACKING ID
============================================================

After application creation, maintain one tracking ID.

Example:

INC-2026-0001

This ID must be usable in:

Web
WhatsApp
IVR
Mobile

Citizen can ask:

"Track my application"

or:

"My application number is INC-2026-0001"

System retrieves the same application.

============================================================
25. GOVERNMENT VERIFICATION
============================================================

Do NOT claim to connect to a real government system.

For POC implement:

MockGovernmentAdapter

Example APIs:

POST /mock-government/submit
GET /mock-government/status/{tracking_id}
POST /mock-government/simulate-approval
POST /mock-government/simulate-clarification
POST /mock-government/simulate-rejection

Flow:

Citizen submits
       ↓
Mock Government
       ↓
UNDER_REVIEW
       ↓
Admin/demo can simulate:
APPROVED
or
CLARIFICATION_REQUIRED
or
REJECTED

============================================================
26. PAYMENT FLOW
============================================================

Payment happens ONLY after:

Government APPROVED

Flow:

APPROVED
    ↓
PAYMENT_REQUIRED
    ↓
Citizen pays
    ↓
Payment gateway / mock payment
    ↓
Payment receipt/transaction
    ↓
PAYMENT_COMPLETED
    ↓
Certificate generation
    ↓
CERTIFICATE_READY

For POC payment can remain mocked.

But the state transition must be correct.

============================================================
27. PAYMENT RECEIPT
============================================================

Allow citizen to:

1. Pay
2. Upload payment screenshot/receipt if required by POC
3. Enter transaction ID
4. Validate receipt
5. Mark payment completed

Store:

transaction_id
payment_amount
payment_status
payment_timestamp
receipt_document

Do not mark payment completed merely because frontend clicked a button.

Backend must validate the payment state.

============================================================
28. NOTIFICATIONS
============================================================

Use the existing notification service.

Generate events:

APPLICATION_CREATED
DOCUMENT_UPLOADED
OCR_COMPLETED
MISMATCH_DETECTED
READY_FOR_REVIEW
APPLICATION_SUBMITTED
UNDER_REVIEW
CLARIFICATION_REQUIRED
APPROVED
PAYMENT_REQUIRED
PAYMENT_COMPLETED
CERTIFICATE_READY

Notifications should be available through:

WhatsApp
Web
Mobile
Email/SMS if configured

============================================================
29. EVENT-DRIVEN APPLICATION UPDATES
============================================================

Create:

ApplicationEventService

Whenever application status changes:

1. Update database
2. Create timeline event
3. Notify citizen
4. Update Web
5. Make status available to WhatsApp
6. Make status available to IVR

All channels must read the same status.

============================================================
30. IVR
============================================================

Use the existing IVR implementation.

Do NOT create separate application state for IVR.

Citizen can say:

"Track my application"

IVR resolves citizen/application and responds:

"Your Income Certificate application INC-2026-0001 is currently under government verification."

If approved:

"Your application has been approved. Payment is now required."

============================================================
31. VOICE
============================================================

Do NOT depend only on browser SpeechRecognition.

Use the existing STT/TTS abstraction.

Architecture:

Voice
 ↓
STT
 ↓
Conversation Engine
 ↓
LLM Provider
 ↓
Response
 ↓
TTS
 ↓
Voice

Keep Mock STT/TTS only for explicit development/testing.

Do NOT use mock LLM.

============================================================
32. MULTILINGUAL
============================================================

The user should be able to select or speak in:

English
Hindi
Marathi
Bengali
Gujarati
Tamil
Telugu

Architecture:

User language
      ↓
STT / text
      ↓
LLM
      ↓
Response in same language

Do not hard-code the complete conversation separately for every language.

The YAML should provide important prompts and validation messages.

The LLM should handle natural multilingual responses.

============================================================
33. RULES ENGINE
============================================================

KEEP the existing YAML Rules Engine.

It must remain deterministic.

Responsibilities:

Validation
Eligibility
Required documents
Cross-field validation
Fee
Waiver
SLA
Service metadata

The LLM should NEVER override the Rules Engine.

Example:

Rules Engine:
eligible = false

LLM:
"You currently do not meet the configured eligibility requirement because..."

Not:

LLM decides eligible = true.

============================================================
34. DATA SOVEREIGNTY
============================================================

Keep the existing Data Guard architecture.

Sensitive information must not be unnecessarily sent to the LLM.

Implement:

Data
 ↓
Classification
 ↓
Restricted fields
 ↓
Redaction / minimization
 ↓
LLM

For example:

Do not send full Aadhaar number to LLM.

Instead:

Aadhaar:
XXXX-XXXX-1234

LLM should receive only what is required.

============================================================
35. OFFICER COPILOT
============================================================

Keep the existing officer/admin functionality.

Improve it with:

Application Summary
Readiness Score
Document Match
Eligibility
Mismatch List
Evidence
Timeline
AI-generated explanation

Example:

Application:
INC-2026-0001

Readiness:
92/100

Documents:
4/4

Issues:
Income document differs by 12%

Eligibility:
PASS

Recommendation:
Approve / Request clarification

IMPORTANT:
AI recommendation is advisory.

Final government/officer decision remains deterministic/manual.

============================================================
36. REAL-TIME WEB UPDATE
============================================================

Use existing streaming/SSE/WebSocket capability if available.

Otherwise implement polling for POC.

When government status changes:

Web should update automatically.

Example:

UNDER REVIEW

changes to:

APPROVED

without requiring full page refresh.

============================================================
37. ERROR HANDLING
============================================================

Remove all silent failures.

Current frontend code contains patterns such as:

catch {}

Replace with meaningful logging and controlled UI feedback.

Backend:

Log technical error.

Frontend:

Show:

"Something went wrong. Please try again."

Do not expose:

stack traces
API keys
internal errors
database errors

============================================================
38. NO HARDCODED FRONTEND APPLICATION STATE
============================================================

Frontend should not become the source of truth.

Do not hard-code:

application status
tracking ID
document state
readiness score
payment status

These must come from backend APIs.

Frontend only displays and updates backend state.

============================================================
39. API CLEANUP
============================================================

Review all APIs and ensure consistent naming.

Expected major API groups:

/api/v1/conversation
/api/v1/applications
/api/v1/applications/{id}/fields
/api/v1/applications/{id}/documents
/api/v1/applications/{id}/readiness
/api/v1/applications/{id}/submit
/api/v1/tracking/{tracking_id}
/api/v1/payment
/api/v1/notifications
/api/v1/whatsapp
/api/v1/ivr
/api/v1/mock-government

Do not unnecessarily create duplicate endpoints.

============================================================
40. SECURITY
============================================================

Never expose API keys in frontend.

LLM API calls must happen from backend.

Do not send:

GEMINI_API_KEY
OPENROUTER_API_KEY
GROQ_API_KEY

to React.

All keys must come from backend environment variables.

============================================================
41. REMOVE OLD OLLAMA CODE
============================================================

Search entire repository for:

ollama
OLLAMA_BASE_URL
OLLAMA_MODEL
phi3
phi3:mini
LLM_FALLBACK_ENABLED
local LLM
fallback LLM

Remove unused Ollama implementation and configuration.

Do not merely comment it out.

Clean:

imports
dependencies
environment variables
provider code
documentation
README references
Docker configuration
startup scripts

After modification:

grep/search repository to ensure no active Ollama dependency remains.

============================================================
42. REMOVE CONVERSATIONAL FALLBACK LOGIC
============================================================

Search for logic such as:

if LLM fails:
    use keyword classifier

or:

if no LLM:
    use mock response

or:

fallback_response

or:

keyword-only response

Remove this from the production conversation path.

Deterministic Rules Engine is allowed.

Keyword matching can be used only for explicit deterministic routing if necessary, but NOT as a substitute for conversational AI.

============================================================
43. PROVIDER VALIDATION
============================================================

At application startup:

If:

LLM_PROVIDER=gemini

and GEMINI_API_KEY missing:

Fail fast with clear configuration error.

Same for Groq/OpenRouter.

Do not silently switch provider.

Example:

ERROR:
LLM_PROVIDER=gemini but GEMINI_API_KEY is not configured.

============================================================
44. HEALTH CHECK
============================================================

Create:

GET /api/v1/health/llm

Return:

provider
model
configured
reachable

Do not expose API key.

Example:

{
    "provider": "gemini",
    "model": "configured-model",
    "configured": true,
    "reachable": true
}

============================================================
45. DATABASE CONSISTENCY
============================================================

Inspect existing models.

Ensure application has:

id
citizen_id
service_id
tracking_id
status
channel_origin
current_language
created_at
updated_at

Ensure application fields are persisted.

Ensure documents are linked to application.

Ensure payment is linked to application.

Ensure timeline events are linked to application.

============================================================
46. AUDIT TIMELINE
============================================================

Every important event should be recorded.

Example:

10:01 Application Created
10:03 Personal Details Completed
10:06 Aadhaar Uploaded
10:07 OCR Completed
10:08 Mismatch Detected
10:10 Citizen Corrected DOB
10:11 Readiness 96%
10:12 Final Review Completed
10:13 Submitted
10:20 Government Review
10:35 Approved
10:36 Payment Required
10:40 Payment Completed
10:41 Certificate Generated

The timeline must be visible on Web.

============================================================
47. POC GOLDEN FLOW
============================================================

This exact flow must work end-to-end.

START:

Citizen opens WhatsApp.

Citizen:

"I want an income certificate."

AI:

"Sure, I can help you apply for an Income Certificate."

AI asks required information dynamically.

Citizen provides information naturally.

Example:

"My name is Kunal Wandhare."

"Date of birth is..."

"My father is..."

"I earn around 3 lakh per year."

System stores information.

Citizen uploads Aadhaar.

OCR extracts fields.

System compares:

Application
vs
Aadhaar.

If mismatch:

AI explains mismatch.

Citizen resolves mismatch.

Citizen uploads income proof.

OCR validates income.

System calculates:

Document Match Score.

Then:

Application Readiness Score.

Example:

96/100
READY TO SUBMIT

AI:

"Your application is ready. Please review it on the Web application."

Citizen opens Web.

Web automatically loads:

same application
same tracking ID
same data
same documents

Four sections:

1. Details
2. Personal & Family
3. Documents & Validation
4. Final Review

Citizen reviews.

Citizen accepts consent.

Submit.

Status:

SUBMITTED_FOR_VERIFICATION

Then:

UNDER_REVIEW

Simulate government approval.

Status:

APPROVED

Notification:

"Your application has been approved. Payment is now required."

Citizen pays.

PAYMENT_COMPLETED

Generate certificate.

CERTIFICATE_READY

Citizen asks WhatsApp:

"What is my application status?"

AI:

"Your Income Certificate application INC-2026-0001 has been approved and your certificate is ready."

Citizen can also check via IVR/Web.

============================================================
48. OTHER CERTIFICATES
============================================================

After Income Certificate works end-to-end, ensure the same framework works for:

Caste Certificate
Domicile Certificate
OBC NCL Certificate

Do NOT duplicate business logic.

Use YAML service specifications.

Architecture:

Service
  ↓
YAML
  ↓
Rules Engine
  ↓
Dynamic Question Engine
  ↓
Document Requirements
  ↓
Application
  ↓
Same workflow

Adding a new service should require primarily a new YAML specification rather than rewriting application code.

============================================================
49. TESTING REQUIREMENTS
============================================================

Add/update tests for:

LLM provider selection
Gemini provider
Groq provider
OpenRouter provider
No fallback behavior
Missing API key
Cross-question
Conversation resume
Service selection
Dynamic question engine
Field validation
Eligibility
OCR extraction
Document matching
Readiness score
FSM transitions
Payment order
Government approval
Clarification
Tracking
Citizen resolution
WhatsApp/Web synchronization

Critical test:

If Gemini fails:

Expected:
AI service unavailable.

NOT:
Groq
NOT:
OpenRouter
NOT:
Ollama
NOT:
keyword fallback

============================================================
50. ACCEPTANCE CRITERIA
============================================================

The implementation is considered complete only if:

[ ] Ollama removed
[ ] phi3 removed
[ ] Local LLM removed
[ ] Conversational fallback removed
[ ] Only Gemini/OpenRouter/Groq supported
[ ] Exactly one provider active at runtime
[ ] No automatic provider fallback
[ ] LLM provider configurable through environment
[ ] API keys backend-only
[ ] Cross-question handling works
[ ] Conversation resumes after cross-question
[ ] RAG knowledge layer works
[ ] YAML remains authoritative for deterministic rules
[ ] Dynamic question engine works
[ ] Income Certificate complete
[ ] OCR works
[ ] OCR fields map to application
[ ] Document matching works
[ ] Match score deterministic
[ ] Readiness score implemented
[ ] Evidence mapping implemented
[ ] Four-section Web application implemented
[ ] WhatsApp and Web share one application
[ ] Same citizen identity across channels
[ ] Same tracking ID across channels
[ ] Correct FSM implemented
[ ] Government verification happens before payment
[ ] Mock government adapter implemented
[ ] Payment happens after approval
[ ] Payment receipt handled
[ ] Certificate completion works
[ ] Timeline works
[ ] Notifications work
[ ] IVR reads same application state
[ ] Voice architecture uses STT → LLM → TTS
[ ] Multilingual conversation works
[ ] Data Guard remains active
[ ] Officer Copilot summary works
[ ] Real-time/polling updates work
[ ] Errors handled correctly
[ ] Tests pass
[ ] README updated
[ ] Environment example updated
[ ] No Ollama references remain in active project
```

============================================================
51. IMPORTANT IMPLEMENTATION RULES
==================================

RULE 1:
Do not rewrite working modules unnecessarily.

RULE 2:
Reuse existing:

* Rules Engine
* YAML specifications
* OCR service
* Matching service
* Citizen Resolver
* Payment service
* Notification service
* STT/TTS abstraction
* WhatsApp adapter
* IVR adapter
* Web adapter
* Tracking
* Officer/Admin

RULE 3:
Fix architecture/integration rather than creating duplicate implementations.

RULE 4:
Backend is source of truth.

RULE 5:
LLM is responsible for language understanding and explanation.

RULE 6:
Rules Engine is responsible for deterministic eligibility and validation.

RULE 7:
OCR is responsible for document extraction.

RULE 8:
Matching Engine is responsible for comparison.

RULE 9:
Readiness Engine is responsible for readiness.

RULE 10:
FSM is responsible for lifecycle.

RULE 11:
Government Adapter is responsible for government verification simulation.

RULE 12:
Payment service is responsible for payment.

RULE 13:
Notification service is responsible for notifications.

RULE 14:
One application must be shared across all channels.

============================================================
52. DEVELOPMENT PROCESS
=======================

Before modifying code:

STEP 1:
Inspect complete repository.

STEP 2:
Map existing implementation to requirements above.

STEP 3:
Identify exact files/classes that already implement functionality.

STEP 4:
Do not duplicate existing services.

STEP 5:
Create an implementation plan.

STEP 6:
Implement backend architecture.

STEP 7:
Fix FSM.

STEP 8:
Implement LLM provider abstraction.

STEP 9:
Remove Ollama/fallback.

STEP 10:
Implement RAG.

STEP 11:
Implement dynamic conversation.

STEP 12:
Implement readiness.

STEP 13:
Fix Web four-section flow.

STEP 14:
Integrate WhatsApp/Web shared application.

STEP 15:
Implement mock government lifecycle.

STEP 16:
Fix payment ordering.

STEP 17:
Integrate notifications/tracking.

STEP 18:
Test complete golden path.

STEP 19:
Run backend tests.

STEP 20:
Run frontend build.

STEP 21:
Check for broken imports/API calls.

STEP 22:
Search repository for old Ollama/fallback references.

STEP 23:
Update README and .env.example.

============================================================
53. REQUIRED FINAL REPORT
=========================

After implementation, provide a concise but detailed report containing:

1. Files created
2. Files modified
3. Files removed
4. Architecture changes
5. LLM provider changes
6. Ollama removal confirmation
7. FSM changes
8. RAG implementation
9. Cross-question implementation
10. Readiness engine
11. WhatsApp/Web synchronization
12. Government mock flow
13. Payment flow
14. Testing results
15. Remaining limitations

Also provide:

A. How to configure Gemini

B. How to configure Groq

C. How to configure OpenRouter

D. How to start backend

E. How to start frontend

F. Exact POC demo steps

============================================================
54. FINAL PRIORITY
==================

If you cannot implement everything at once, prioritize exactly in this order:

P0:
Correct FSM + payment order

P0:
Remove Ollama/fallback

P0:
Gemini/Groq/OpenRouter provider architecture

P0:
Income Certificate end-to-end

P0:
Single application state

P0:
Dynamic question engine

P0:
Cross-question handling

P0:
OCR + document matching

P0:
Readiness score

P0:
Four-section Web application

P1:
RAG

P1:
Government mock adapter

P1:
Notifications

P1:
Tracking

P1:
IVR synchronization

P1:
Payment/receipt

P2:
Voice-to-voice

P2:
Evidence Graph UI

P2:
Officer Copilot enhancements

P2:
Mobile enhancements

============================================================
55. DO NOT CLAIM FEATURES WITHOUT TESTING
=========================================

Do not simply create UI elements that look like functionality.

For every important POC feature:

UI
↓
API
↓
Service
↓
Database
↓
State transition

must actually work.

For example, if UI says:

"Readiness Score: 96"

then backend must actually calculate 96.

If UI says:

"Government Approved"

then application status must actually be:

APPROVED.

If UI says:

"Payment Completed"

then payment record must actually exist.

If UI says:

"Certificate Ready"

then certificate status/file must exist.

============================================================
56. FINAL EXPECTED RESULT
=========================

The finished project should demonstrate:

```
                CITIZEN
                   |
         WhatsApp / Web / IVR
                   |
                   v
           MULTILINGUAL AI
                   |
         Gemini / Groq /
           OpenRouter
                   |
                   v
           RAG + CONTEXT
                   |
                   v
        CONVERSATION ENGINE
                   |
                   v
          DYNAMIC QUESTIONS
                   |
                   v
            APPLICATION
                   |
      ┌────────────┼────────────┐
      |            |            |
     OCR        RULES       DOCUMENTS
      |            |            |
      └────────────┼────────────┘
                   |
                   v
          MATCHING ENGINE
                   |
                   v
          READINESS ENGINE
                   |
                   v
            FINAL REVIEW
                   |
                   v
               CONSENT
                   |
                   v
         GOVERNMENT MOCK API
                   |
              UNDER REVIEW
                   |
                APPROVED
                   |
                   v
               PAYMENT
                   |
                   v
            CERTIFICATE
                   |
                   v
               TRACKING
```

The user should experience this as ONE continuous AI-assisted government application process, regardless of whether they start from WhatsApp, Web, IVR, or Mobile.

Implement this as an integration/refactoring of the existing repository, not as a new application.

````

---

## One important change I recommend before you give this to Antigravity

For the POC, configure **one provider first**, rather than trying to test all three simultaneously.

For example, start with:

```env
LLM_PROVIDER=gemini

GEMINI_API_KEY=your_key
GEMINI_MODEL=your_model
````

Then later test:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key
GROQ_MODEL=your_model
```

or:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=your_model
```

The important architecture rule is:

```text
              LLM_PROVIDER
                   |
       ┌───────────┼───────────┐
       ↓           ↓           ↓
    Gemini       Groq      OpenRouter
       |           |           |
       └───────────┼───────────┘
                   ↓
             LLMService
                   ↓
            Conversation
```

**Not:**

```text
Gemini
  ↓ fail
Groq
  ↓ fail
OpenRouter
  ↓ fail
Ollama
  ↓
Keyword fallback
```

That second architecture is exactly what you asked me to remove.

### Your final POC golden path should therefore be

```text
WhatsApp / Web
      ↓
Select Income Certificate
      ↓
AI conversation
      ↓
Dynamic personal/family details
      ↓
Document upload
      ↓
OCR
      ↓
Document ↔ Application matching
      ↓
Mismatch correction
      ↓
Readiness Score
      ↓
Open Web Application
      ↓
4 Sections
      ↓
Final Review + Consent
      ↓
Government Verification
      ↓
APPROVED
      ↓
Payment
      ↓
Receipt / Transaction
      ↓
Certificate Ready
      ↓
Tracking ID
      ↓
WhatsApp / Web / IVR status
```

This is the flow I would use as the **actual acceptance/demo scenario** for your project rather than trying to demonstrate every feature independently.
