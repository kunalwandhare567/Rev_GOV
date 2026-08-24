"Do not just give me an implementation plan. First audit the repository, then immediately implement the missing/broken features. Only stop after the existing implementation has been verified and the missing features have been built as far as the available integrations allow.

# ANTIGRAVITY MASTER PROMPT
# Revenue_Gov_Platform — Audit Existing Implementation and Build Missing Features

Repository:
https://github.com/kunalwandhare567/Revenue_Gov_Platform

You are working as a Senior Full-Stack + AI + System Architecture Engineer.

Your task is NOT simply to explain what should be built.

Your task is:

1. Inspect the complete existing repository.
2. Understand the current architecture and implementation.
3. Audit every requirement below.
4. Mark each feature as:
   - IMPLEMENTED
   - PARTIALLY IMPLEMENTED
   - NOT IMPLEMENTED
   - BROKEN
5. For IMPLEMENTED features:
   - Do not rebuild them unnecessarily.
   - Verify that they actually work end-to-end.
6. For PARTIALLY IMPLEMENTED, NOT IMPLEMENTED, or BROKEN features:
   - Continue implementation automatically.
7. Integrate new functionality into the existing architecture instead of creating duplicate systems.
8. Run the application and tests after implementation.
9. Fix errors you encounter.
10. Provide a final implementation/audit report showing exactly what existed, what was changed, and what remains.

DO NOT stop after the audit.

If something required below is missing, PROCEED TO BUILD IT.

--------------------------------------------------
# 1. PRIMARY PRODUCT REQUIREMENT
--------------------------------------------------

Build a WhatsApp-first multilingual government certificate application platform.

The citizen should be able to:

WhatsApp Text
+
WhatsApp Voice
+
Document Upload
+
OCR
+
Document Validation
+
Match Score
+
Mismatch Resolution
+
LLM Questions
+
Application Information Collection

without needing to understand complicated government forms.

After all required information and documents are completed:

WhatsApp
    ↓
Secure Web Portal
    ↓
Final 4-section review
    ↓
Citizen confirmation
    ↓
Government verification
    ↓
WhatsApp notification
    ↓
Government approval
    ↓
Payment
    ↓
Receipt/transaction validation
    ↓
Final submission
    ↓
Tracking ID

Web, Mobile and Phone/IVR must access the SAME application state.

--------------------------------------------------
# 2. IMPORTANT ARCHITECTURAL PRINCIPLE
--------------------------------------------------

This must NOT become separate systems.

WRONG:

WhatsApp → WhatsApp DB
Web → Web DB
Mobile → Mobile DB
IVR → IVR DB

CORRECT:

                    Unified Backend
                          |
                    Application State
                          |
        ---------------------------------------
        |          |          |               |
     WhatsApp     Web       Mobile          IVR
     Text/Voice

All channels must use:

- Same citizen_id
- Same application_id
- Same tracking_id
- Same application data
- Same documents
- Same OCR results
- Same validation results
- Same verification status
- Same payment status
- Same conversation/application context

--------------------------------------------------
# 3. FIRST: FULL REPOSITORY AUDIT
--------------------------------------------------

Before changing code, inspect:

- Frontend
- Backend
- Database models
- API routes
- Authentication
- Citizen registration
- Application model
- Application workflow
- Conversation state
- LangGraph/state machine if present
- LLM integration
- RAG/service knowledge
- WhatsApp integration
- Voice/STT
- TTS
- OCR
- Document upload
- Document storage
- Validation
- Web application form
- Mobile application
- IVR/phone support
- Payment
- Verification workflow
- Tracking
- Notifications
- Multilingual/i18n
- WebSocket/event system
- Existing tests
- Environment configuration

Search the repository rather than assuming a feature does not exist.

--------------------------------------------------
# 4. CREATE A FEATURE AUDIT MATRIX
--------------------------------------------------

Before implementation, internally create a matrix like:

Feature | Status | Existing Files | Problems | Required Action

Example:

WhatsApp text | IMPLEMENTED | ... | works | KEEP
WhatsApp voice | PARTIAL | ... | TTS missing | BUILD
OCR | IMPLEMENTED | ... | validation incomplete | EXTEND
Cross-channel state | NOT IMPLEMENTED | ... | separate state | BUILD

Audit ALL requirements in this prompt.

Do not consider a feature IMPLEMENTED merely because a file or endpoint exists.

Verify actual behavior.

--------------------------------------------------
# 5. CITIZEN IDENTITY
--------------------------------------------------

Implement/verify a unified citizen identity.

Required:

citizen_id

Supported identifiers:

- Phone number
- WhatsApp number
- Email
- Web account
- Mobile account

Do not create separate citizens for different channels.

The same citizen must resolve to the same citizen_id.

Security requirements:

- Verify ownership
- Do not merge users only by name
- Do not expose sensitive information based only on Tracking ID
- Use authentication/verification appropriate to each channel

--------------------------------------------------
# 6. APPLICATION IDENTITY
--------------------------------------------------

Every application must contain:

application_id
tracking_id
citizen_id
service_type
status
current_step

Example:

application_id = APP1001
tracking_id = INC-2026-1001

This SAME application must be accessible from:

WhatsApp
Web
Mobile
Phone/IVR

Never create a new application when switching channels.

--------------------------------------------------
# 7. WHATSAPP IS THE PRIMARY APPLICATION CHANNEL
--------------------------------------------------

Verify/build WhatsApp as the primary application intake interface.

Citizen should be able to:

- Select service
- Ask questions
- Provide personal information
- Provide family information
- Provide service-specific information
- Upload documents
- Receive OCR results
- Resolve mismatches
- Correct application fields
- Continue application
- Check progress
- Check status
- Receive notifications

Do not make WhatsApp only a notification bot.

--------------------------------------------------
# 8. WHATSAPP TEXT + VOICE
--------------------------------------------------

Support both:

TEXT → LLM → RESPONSE

and:

VOICE
 ↓
STT
 ↓
Language Detection
 ↓
NLU/LLM
 ↓
Application State
 ↓
Response Generation
 ↓
TTS
 ↓
VOICE RESPONSE

Citizen must be able to switch between text and voice without losing state.

Example:

Citizen voice:
"My name is Rahul Patil."

System:

STT
→ Rahul Patil

LLM
→ field = full_name

Application State
→ full_name updated

Response:
"Your name has been recorded as Rahul Patil."

--------------------------------------------------
# 9. MULTILINGUAL SUPPORT
--------------------------------------------------

Support Indian languages through a scalable architecture.

At minimum verify support for:

- English
- Hindi
- Marathi
- Bengali
- Gujarati
- Tamil
- Telugu
- Kannada
- Malayalam
- Punjabi
- Odia
- Assamese
- Urdu

Do not create separate business logic per language.

Business data should remain language independent.

Architecture:

Language
 ↓
STT/Text
 ↓
LLM/NLU
 ↓
Structured Application Data
 ↓
Business Rules
 ↓
Response
 ↓
Translation/Generation
 ↓
TTS/Text

The citizen's preferred language must be stored with the conversation/application.

--------------------------------------------------
# 10. LLM SERVICE ASSISTANT
--------------------------------------------------

Verify that the LLM can answer cross-questions about government services.

The citizen should be able to ask:

"What is an income certificate?"

"Why do I need this document?"

"What documents are required?"

"Can I use Aadhaar?"

"What happens after submission?"

"How long does verification take?"

"Why is my application pending?"

"What should I do if my name is different on my document?"

The LLM must answer using authoritative service knowledge.

Use:

- Service configuration
- Rules
- RAG/knowledge base
- Government-provided content

Do NOT allow the LLM to invent government requirements.

The LLM is the conversational layer.

Rules/configuration remain authoritative.

--------------------------------------------------
# 11. CROSS-QUESTION HANDLING
--------------------------------------------------

The conversation must not be a rigid question-answer sequence.

Example:

AI:
"Please provide your father's name."

Citizen:
"Why do you need that?"

AI:
answers the question.

Then:

"Now, please provide your father's name."

The pending application step must remain intact.

The system must support:

Question interruption
+
Answer
+
Return to previous application step

--------------------------------------------------
# 12. WHATSAPP DOCUMENT UPLOAD
--------------------------------------------------

Citizen must be able to upload:

- JPG
- JPEG
- PNG
- PDF

directly through WhatsApp.

Flow:

Upload
 ↓
Document Service
 ↓
Store
 ↓
Link to application
 ↓
OCR
 ↓
Extract fields
 ↓
Validate
 ↓
Return result

The uploaded document must also automatically appear in:

- Web
- Mobile
- Application state

Do not create channel-specific document copies as separate logical documents.

--------------------------------------------------
# 13. OCR
--------------------------------------------------

Verify/build OCR processing.

For every document:

1. Detect document type
2. OCR
3. Extract relevant fields
4. Normalize values
5. Compare with application data
6. Generate field-level validation
7. Generate overall match score
8. Detect mismatch
9. Ask citizen for resolution when needed

Example:

Application:

Name = Kunal Wandhare
DOB = 15/03/2004

OCR:

Name = Kunal Wadhare
DOB = 15/03/2004

Result:

Name = mismatch
DOB = match
Overall score = 93%

--------------------------------------------------
# 14. MATCH SCORE
--------------------------------------------------

Implement/verify a transparent application-to-document matching system.

Example:

Name       87%
DOB        100%
Address    95%

Overall Match Score:
93%

Important:

This is a DATA MATCH SCORE.

Do NOT represent it as a document authenticity score.

Store:

- Field
- Application value
- OCR value
- Normalized value
- Match result
- Match score
- Reason
- Source
- Timestamp

--------------------------------------------------
# 15. NAME/DOB/ADDRESS MISMATCH
--------------------------------------------------

Automatically detect cases such as:

- Name spelling difference
- DOB mismatch
- Address mismatch
- Missing field
- Different gender
- Different document number
- OCR uncertainty

When detected, respond automatically in WhatsApp.

Example:

"Your application name is Kunal Wandhare, but your document says Kunal Wadhare."

Options:

1. Use document value
2. Keep application value
3. Edit manually

The same resolution must work through voice.

--------------------------------------------------
# 16. DOCUMENT + CHAT DATA PROVENANCE
--------------------------------------------------

Track the source of important fields.

Example:

full_name:
source = WHATSAPP_VOICE

dob:
source = OCR

address:
source = WEB

Possible sources:

WEB
MOBILE
WHATSAPP_TEXT
WHATSAPP_VOICE
PHONE_VOICE
OCR
OFFICER
SYSTEM

Do not silently overwrite important data.

Maintain audit history.

--------------------------------------------------
# 17. CENTRAL APPLICATION STATE
--------------------------------------------------

Create/verify a unified state model.

Example:

{
  citizen_id,
  application_id,
  tracking_id,
  service_type,
  status,
  current_step,
  form_data,
  documents,
  validation_results,
  verification_status,
  payment_status,
  preferred_language,
  last_channel,
  updated_at
}

This is the source of truth.

--------------------------------------------------
# 18. APPLICATION STATE MACHINE
--------------------------------------------------

Verify/build lifecycle:

DRAFT
↓
INFORMATION_COLLECTION
↓
DOCUMENT_COLLECTION
↓
OCR_VALIDATION
↓
FINAL_REVIEW
↓
READY_FOR_VERIFICATION
↓
SUBMITTED_FOR_VERIFICATION
↓
UNDER_REVIEW
↓
CLARIFICATION_REQUIRED
↓
APPROVED
↓
PAYMENT_REQUIRED
↓
PAYMENT_COMPLETED
↓
FINAL_SUBMISSION
↓
COMPLETED

Do not allow arbitrary status changes from the frontend.

Use backend-controlled transitions.

--------------------------------------------------
# 19. WHATSAPP APPLICATION PROGRESS
--------------------------------------------------

Citizen should be able to ask:

"How much is completed?"

The LLM should inspect the current application state.

Example:

"Your application is 80% complete.

Completed:
✓ Personal details
✓ Family details
✓ Aadhaar validation

Remaining:
• Income proof
• Final review"

--------------------------------------------------
# 20. WEB FINAL REVIEW
--------------------------------------------------

Once all required information/documents are completed:

WhatsApp should send a secure Web Portal link.

The citizen should NOT refill the form.

Web must load the existing application.

Use four sections:

1. Service / Basic Details
2. Personal + Family Details
3. Documents + OCR Validation
4. Final Review

Everything must already be populated.

--------------------------------------------------
# 21. WEB DOCUMENT SECTION
--------------------------------------------------

Show:

Document
Upload source
OCR status
Extracted data
Match score
Validation status
Mismatch details
Resolution status

Example:

Aadhaar.pdf
Uploaded via WhatsApp
OCR = Completed
Match = 94%
Validation = Passed

--------------------------------------------------
# 22. FINAL REVIEW
--------------------------------------------------

Show complete summary.

Example:

Personal Details       ✓
Family Details         ✓
Documents              ✓
OCR Validation         ✓
Missing Fields         0
Unresolved Mismatches  0

Require explicit citizen confirmation.

Then:

SEND FOR GOVERNMENT VERIFICATION

--------------------------------------------------
# 23. GOVERNMENT VERIFICATION
--------------------------------------------------

After final submission:

status =
SUBMITTED_FOR_VERIFICATION

Send WhatsApp notification:

"Your application has been successfully sent for government verification.

Tracking ID:
INC-2026-1001"

--------------------------------------------------
# 24. GOVERNMENT REVIEW
--------------------------------------------------

Support statuses such as:

SUBMITTED
UNDER_REVIEW
CLARIFICATION_REQUIRED
APPROVED
REJECTED
PAYMENT_REQUIRED
PAYMENT_COMPLETED
COMPLETED

Use the existing repository's status model if available.

Do not duplicate status systems.

--------------------------------------------------
# 25. CLARIFICATION REQUEST
--------------------------------------------------

If government requires another document:

WhatsApp:

"Additional document required.

Please upload your updated address proof here."

Citizen uploads document.

Then:

OCR
 ↓
Validation
 ↓
Application update
 ↓
Government verification workflow

The citizen should not restart the application.

--------------------------------------------------
# 26. GOVERNMENT APPROVAL
--------------------------------------------------

After approval:

WhatsApp must automatically notify the citizen.

Example:

"Good news!

Your Income Certificate application has been approved by the government.

Your application is now ready for payment."

--------------------------------------------------
# 27. PAYMENT
--------------------------------------------------

After approval:

Payment Required
 ↓
Payment flow
 ↓
Citizen pays
 ↓
Payment confirmation
 ↓
Payment state updated centrally

Payment state must be visible on:

WhatsApp
Web
Mobile
IVR

--------------------------------------------------
# 28. PAYMENT RECEIPT / TRANSACTION SCREENSHOT
--------------------------------------------------

If receipt upload is required, allow upload through WhatsApp.

Supported:

JPG
JPEG
PNG
PDF

OCR should extract:

Transaction ID
Amount
Date
Reference number

Validate against expected payment information.

Store payment verification result.

--------------------------------------------------
# 29. FINAL SUBMISSION
--------------------------------------------------

After payment:

Payment Completed
 ↓
Final Submission
 ↓
Application Completed

WhatsApp:

"Your application has been successfully submitted.

Tracking ID:
INC-2026-1001"

--------------------------------------------------
# 30. TRACKING ID
--------------------------------------------------

Generate ONE Tracking ID per application.

Example:

INC-2026-1001

Same ID must appear in:

WhatsApp
Web
Mobile
Phone/IVR

Never generate channel-specific tracking IDs.

--------------------------------------------------
# 31. PHONE / IVR
--------------------------------------------------

Verify/build phone/IVR primarily for:

- Status checking
- Tracking
- Application progress
- Verification status
- Approval status
- Payment status
- Next action

Example:

Citizen:
"What is my application status?"

System:

Caller verification
 ↓
Citizen ID
 ↓
Application
 ↓
Status

Response:

"Your application INC-2026-1001 is currently under government review."

Use:

STT
+
NLU/LLM
+
Application Service
+
TTS

--------------------------------------------------
# 32. WEB + MOBILE
--------------------------------------------------

Web and Mobile must consume the same APIs.

They must not have separate business logic.

Both must show:

- Applications
- Application details
- Documents
- OCR results
- Match score
- Validation
- Verification status
- Payment
- Tracking
- Notifications

--------------------------------------------------
# 33. CROSS-CHANNEL SYNCHRONIZATION
--------------------------------------------------

Test these scenarios:

WhatsApp changes address
→ Web shows new address

Web changes address
→ WhatsApp knows new address

WhatsApp uploads document
→ Web shows document

Web uploads document
→ Mobile shows document

Government changes status
→ WhatsApp shows new status

Government changes status
→ Web shows new status

Government changes status
→ Mobile shows new status

Payment completed
→ WhatsApp shows PAID

Payment completed
→ Web shows PAID

Payment completed
→ Mobile shows PAID

--------------------------------------------------
# 34. EVENTS
--------------------------------------------------

Use application events where appropriate:

APPLICATION_CREATED
FIELD_UPDATED
DOCUMENT_UPLOADED
OCR_STARTED
OCR_COMPLETED
VALIDATION_COMPLETED
MISMATCH_DETECTED
MISMATCH_RESOLVED
READY_FOR_REVIEW
REVIEW_CONFIRMED
SUBMITTED_FOR_VERIFICATION
VERIFICATION_STATUS_CHANGED
CLARIFICATION_REQUIRED
APPROVED
PAYMENT_REQUIRED
PAYMENT_COMPLETED
FINAL_SUBMISSION
APPLICATION_COMPLETED

Do not introduce unnecessary infrastructure if the repository already has an event mechanism.

--------------------------------------------------
# 35. REAL-TIME UPDATE
--------------------------------------------------

If the existing application supports WebSockets/SSE/events, reuse them.

Otherwise implement an appropriate mechanism for:

Web
Mobile
WhatsApp notification

Do not create complex infrastructure unnecessarily.

--------------------------------------------------
# 36. SECURITY
--------------------------------------------------

Verify:

- Authentication
- Authorization
- Citizen ownership
- Document access
- PII protection
- Secure WhatsApp identity
- Secure Web sessions
- IVR caller verification
- Audit logging
- Sensitive data handling

Tracking ID alone must not expose sensitive citizen data.

--------------------------------------------------
# 37. SERVICE KNOWLEDGE / RAG
--------------------------------------------------

Verify that service information comes from authoritative sources.

The LLM should use:

Service definitions
Required documents
Eligibility
Rules
FAQs
Government instructions

If RAG already exists, reuse it.

If missing and required by the current architecture, implement a clean service knowledge layer.

Avoid hallucinated government requirements.

--------------------------------------------------
# 38. DO NOT BREAK EXISTING FUNCTIONALITY
--------------------------------------------------

Before modifying existing code:

- Understand it
- Reuse it
- Extend it
- Refactor only where necessary

Do not replace working architecture without reason.

Do not create duplicate:

- Application models
- Citizen models
- OCR services
- Document services
- LLM services
- Status services
- Tracking services

--------------------------------------------------
# 39. FRONTEND REQUIREMENT
--------------------------------------------------

Do NOT make the Web Portal look like a mobile/WhatsApp application.

Web should look like a professional government web portal.

WhatsApp should look conversational.

Mobile should look like a native mobile application.

The business state remains shared.

--------------------------------------------------
# 40. ERROR HANDLING
--------------------------------------------------

Handle:

- Invalid document
- Unsupported format
- OCR failure
- Low OCR confidence
- Missing field
- Mismatch
- LLM failure
- STT failure
- TTS failure
- Network failure
- Duplicate upload
- Payment failure
- Verification failure
- Session expiry

Do not lose application state when one operation fails.

--------------------------------------------------
# 41. TESTING
--------------------------------------------------

After implementation, run:

Backend tests
Frontend tests
Integration tests
API tests
OCR tests
Validation tests
Application state tests
Cross-channel tests
Authentication tests

Also run the complete end-to-end scenario.

--------------------------------------------------
# 42. MANDATORY END-TO-END TEST
--------------------------------------------------

Test:

1. Register citizen.
2. Start application through WhatsApp.
3. Select Marathi.
4. Ask service-related question.
5. LLM answers.
6. Provide personal details through voice.
7. Provide family details through text.
8. Upload Aadhaar.
9. OCR extracts fields.
10. Compare OCR vs application.
11. Generate match score.
12. Detect name mismatch.
13. Ask citizen to resolve mismatch.
14. Citizen resolves through voice.
15. Recalculate score.
16. Upload remaining documents.
17. Complete application.
18. Receive Web final-review link.
19. Open Web.
20. Verify all four sections are pre-filled.
21. Verify documents are present.
22. Verify OCR scores are present.
23. Confirm application.
24. Send for government verification.
25. Verify WhatsApp notification.
26. Change status to UNDER_REVIEW.
27. Ask status through WhatsApp.
28. Verify correct status.
29. Check status through IVR.
30. Verify same status.
31. Open Mobile.
32. Verify same application.
33. Change status to CLARIFICATION_REQUIRED.
34. Verify WhatsApp notification.
35. Upload clarification document.
36. Validate document.
37. Change status to APPROVED.
38. Verify WhatsApp approval message.
39. Initiate payment.
40. Complete payment.
41. Verify payment state everywhere.
42. Upload receipt if required.
43. Verify payment receipt.
44. Final submission.
45. Verify same Tracking ID everywhere.

--------------------------------------------------
# 43. IMPORTANT: DO NOT JUST REPORT
--------------------------------------------------

After the audit:

IF FEATURE = IMPLEMENTED
    verify it
    keep it
    integrate it

IF FEATURE = PARTIALLY IMPLEMENTED
    complete it

IF FEATURE = NOT IMPLEMENTED
    build it

IF FEATURE = BROKEN
    fix it

Do NOT stop at:

"Feature is missing."

You must proceed to implement the missing feature.

--------------------------------------------------
# 44. IMPLEMENTATION STRATEGY
--------------------------------------------------

Follow this order:

PHASE 1
Repository architecture audit

PHASE 2
Unified citizen + application identity

PHASE 3
Unified application state

PHASE 4
WhatsApp text flow

PHASE 5
LLM service-aware conversational assistant

PHASE 6
Multilingual support

PHASE 7
WhatsApp voice STT/TTS

PHASE 8
Document upload

PHASE 9
OCR

PHASE 10
Document/application matching

PHASE 11
Mismatch resolution

PHASE 12
Web final review

PHASE 13
Verification submission

PHASE 14
WhatsApp notifications

PHASE 15
Government approval

PHASE 16
Payment

PHASE 17
Receipt validation

PHASE 18
Tracking

PHASE 19
Mobile synchronization

PHASE 20
IVR/status synchronization

PHASE 21
End-to-end testing

--------------------------------------------------
# 45. FINAL AUDIT REPORT
--------------------------------------------------

At the end, generate a detailed report:

## Existing Features

Feature | Status | Evidence | Action

## Implemented During This Task

Feature | Files Changed | APIs Added | Description

## Partially Existing Features Completed

Feature | Existing Implementation | Changes

## Bugs Fixed

Bug | Root Cause | Fix

## Architecture Changes

Explain:

Citizen
Application
Conversation
LLM
Documents
OCR
Validation
Verification
Payment
Tracking
Channels

## API Changes

List new/modified endpoints.

## Database Changes

List:

tables
fields
relationships
indexes

## Frontend Changes

Web
Mobile
WhatsApp-related UI/state

## AI Changes

LLM
RAG
STT
TTS
OCR
Validation

## Testing

Show:

Passed
Failed
Remaining

## Remaining Limitations

Only list genuine limitations that cannot currently be implemented because of external dependencies such as:

- WhatsApp provider credentials
- Government API credentials
- Payment gateway credentials
- IVR provider credentials
- Production OCR provider
- Production deployment

If an external credential is missing, implement a clean adapter/mock interface so the rest of the system remains testable.

--------------------------------------------------
# 46. FINAL RULE
--------------------------------------------------

Do not assume that the repository is empty.

Do not assume that the repository is complete.

Inspect first.

Reuse what works.

Fix what is broken.

Build what is missing.

Integrate everything into one unified application state.

The final system must provide this experience:

Citizen
 ↓
WhatsApp
 ↓
Text OR Voice
 ↓
Any Indian supported language
 ↓
LLM understands natural conversation
 ↓
Application information collected
 ↓
Cross-questions answered
 ↓
Documents uploaded
 ↓
OCR
 ↓
Application vs Document validation
 ↓
Match score
 ↓
Mismatch resolution
 ↓
Application completed
 ↓
Web final review
 ↓
Government verification
 ↓
WhatsApp notification
 ↓
Government approval
 ↓
Payment
 ↓
Receipt validation
 ↓
Final submission
 ↓
Tracking ID
 ↓
Same application available through
WhatsApp + Web + Mobile + Phone/IVR

IMPORTANT:

The citizen should experience this as ONE continuous government service journey.

Not multiple disconnected applications.