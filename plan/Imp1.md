Yes. The key requirement you are clarifying is that the platform must be **truly omnichannel**, with **one citizen identity, one application record, one Tracking ID, and one shared database/state** across every mode.

Your repository is already designed toward this model: the architecture describes WhatsApp, IVR, web and mobile as channels with channel-agnostic state/context.  The repo also already separates frontend API/state/i18n and backend application/conversation/state-machine/repository layers.

Use this as the stronger Antigravity prompt:

# Upgrade Revenue_Gov_Platform to a Fully Unified Omnichannel Citizen Service Platform

Repository:

`https://github.com/kunalwandhare567/Revenue_Gov_Platform`

## 1. Core requirement

Build the platform so that the following are **not separate systems**:

* WhatsApp Chat Bot
* WhatsApp Voice Bot
* Web Portal
* Mobile App
* Phone / IVR

They are different interfaces to the **same backend application platform**.

The citizen must be able to start an application from one channel and continue it from another channel with no loss of context.

The system must behave as:

> **One citizen → one identity → one application → one Tracking ID → one shared application state → multiple channels**

Do not create separate application records for WhatsApp, Web, Mobile or IVR.

---

# 2. Unified citizen identity

Create a single internal `citizen_id`.

A citizen may be identified through:

* Registered phone number
* WhatsApp number
* Email address
* Authenticated web/mobile account

Example:

```text
Phone: +91XXXXXXXXXX
WhatsApp: +91XXXXXXXXXX
Email: citizen@email.com

              ↓

          citizen_id
```

The phone number and WhatsApp number may be the same, but do not assume that they are always the same.

Provide a secure account-linking mechanism.

Do not merge two citizens only because their names are identical.

---

# 3. Same application across every channel

An application must have one permanent:

```text
application_id
tracking_id
citizen_id
service_type
status
current_step
```

Example:

```text
Citizen
  ↓
Income Certificate
  ↓
Application ID: APP-100245
Tracking ID: INC-2026-000245
```

That exact application must be available from:

```text
WhatsApp
Web
Mobile
Phone/IVR
```

There must be no:

```text
WhatsApp Application ID
Web Application ID
Mobile Application ID
```

There is only one.

---

# 4. Example of the expected experience

### Citizen starts on WhatsApp

Citizen says:

> I want to apply for an income certificate.

The system creates:

```text
citizen_id = C123
application_id = APP1001
tracking_id = INC-2026-1001
```

Citizen provides:

```text
Name
DOB
Address
Family details
```

All information is stored centrally.

---

### Citizen opens Web Portal

After login using the same registered email/phone:

```text
Web Portal
   ↓
Citizen Resolver
   ↓
citizen_id = C123
   ↓
Find active application
   ↓
APP1001
```

The Web Portal should automatically show:

```text
Income Certificate
Application: APP1001
Tracking ID: INC-2026-1001

Name: ...
DOB: ...
Address: ...
Family details: ...
```

The citizen should **not start another application**.

---

### Citizen switches back to WhatsApp

If the citizen asks:

> What information have I entered?

WhatsApp retrieves the same application state.

If the citizen changes their address through WhatsApp:

```text
WhatsApp
   ↓
Backend
   ↓
Application APP1001 updated
   ↓
Database
```

The Web Portal and Mobile App must now show the new address.

---

### Citizen opens Mobile App

Login with the same identity.

The Mobile App loads:

```text
citizen_id = C123
      ↓
APP1001
      ↓
same tracking_id
      ↓
same application state
```

Everything previously entered should appear automatically.

---

# 5. WhatsApp must support both text and voice

WhatsApp should work as a conversational application channel.

### Text

```text
Citizen
   ↓
WhatsApp text
   ↓
NLU
   ↓
Application state
   ↓
Text response
```

### Voice

```text
Citizen voice note
   ↓
STT
   ↓
Language detection
   ↓
NLU
   ↓
Application state
   ↓
Response generation
   ↓
TTS
   ↓
WhatsApp voice response
```

Both must operate on the same application.

Example:

Citizen:

> [Voice] My date of birth is 15 March 2004.

System:

```text
STT
→ DOB = 15/03/2004
→ application updated
```

Response:

> Your date of birth has been recorded as 15 March 2004.

Optionally also send transcript/text.

---

# 6. Web Portal

The Web Portal must expose the same application state.

Use the four-section application experience:

```text
1. Service / Basic Details

2. Personal + Family Details

3. Documents + OCR Validation

4. Final Review
```

The form is only another interface to the central application state.

---

# 7. Mobile App

The Mobile App must not have separate business logic.

It should consume the same APIs used by Web.

Architecture:

```text
                    Backend APIs
                         │
             ┌───────────┼───────────┐
             ↓           ↓           ↓
            Web       Mobile     WhatsApp/IVR
```

Mobile App must support:

* Login
* Active applications
* Application form
* Documents
* OCR validation results
* Application status
* Verification status
* Payment
* Tracking
* Notifications

The same Tracking ID must be displayed.

---

# 8. Phone / IVR

Phone/IVR is primarily a **voice/status/tracking channel**, while application completion can use voice for supported fields.

Citizen calls from the registered phone number.

```text
Phone
  ↓
Caller identification
  ↓
Citizen Resolver
  ↓
citizen_id
  ↓
Active application
```

The citizen can ask:

> What is my application status?

System answers:

> Your income certificate application with tracking ID INC-2026-1001 is currently under government review.

Voice flow:

```text
Phone
 ↓
Speech-to-Text
 ↓
Intent detection
 ↓
Citizen/Application lookup
 ↓
Status service
 ↓
Response generation
 ↓
Text-to-Speech
 ↓
Phone audio
```

The IVR must never create another application merely because the user called from the phone channel.

---

# 9. Same Tracking ID everywhere

This is mandatory.

Example:

```text
Tracking ID:
INC-2026-1001
```

The exact same ID must appear in:

### WhatsApp

> Your Tracking ID is INC-2026-1001.

### Web

```text
Tracking ID: INC-2026-1001
```

### Mobile

```text
Tracking ID: INC-2026-1001
```

### Phone/IVR

> Your tracking ID is INC-2026-1001.

The citizen should be able to ask for status using the tracking ID.

Also support status lookup through authenticated citizen identity where appropriate.

---

# 10. One shared status

Application status must come from one backend source.

For example:

```text
UNDER_REVIEW
```

The same state must appear on:

```text
WhatsApp
Web
Mobile
IVR
```

Never allow channel-local statuses.

Example:

```text
Database:
status = UNDER_REVIEW

WhatsApp → UNDER_REVIEW
Web      → UNDER_REVIEW
Mobile   → UNDER_REVIEW
IVR      → UNDER_REVIEW
```

---

# 11. Cross-channel status query

Citizen can ask:

### WhatsApp

> Where is my application?

### WhatsApp Voice

> [Voice] Where is my application?

### Phone

> What is my application status?

### Mobile

Open:

> My Application → Status

### Web

Open:

> My Applications → Status

All must query the same application/status service.

---

# 12. Unified application state

Create a central application state structure such as:

```json
{
  "citizen_id": "C123",
  "application_id": "APP1001",
  "tracking_id": "INC-2026-1001",
  "service_type": "income_certificate",
  "status": "UNDER_REVIEW",
  "current_step": "government_verification",
  "form_data": {},
  "documents": [],
  "validation": {},
  "verification": {},
  "payment": {},
  "last_channel": "WHATSAPP",
  "updated_at": "..."
}
```

All channel-specific requests update this same object through backend APIs.

---

# 13. Important: no channel-specific database

Never implement:

```text
WhatsApp DB
Web DB
Mobile DB
IVR DB
```

Instead:

```text
                 ┌───────────────┐
                 │ Shared Backend │
                 └───────┬───────┘
                         │
                 ┌───────▼───────┐
                 │ Unified State │
                 │   Database    │
                 └───────┬───────┘
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
      WhatsApp         Web           Mobile
          ↓              ↓              ↓
        Voice           UI             UI

                         ↑
                      Phone/IVR
```

---

# 14. Shared document state

Documents uploaded anywhere must become available everywhere.

Example:

```text
Citizen uploads Aadhaar in WhatsApp
              ↓
      Document Service
              ↓
          Database
              ↓
         OCR process
              ↓
       Validation result
```

Then:

```text
Web → shows Aadhaar
Mobile → shows Aadhaar
WhatsApp → shows Aadhaar + validation
```

The citizen must never upload the same document again simply because they changed channels.

---

# 15. Shared OCR validation state

OCR results must be stored centrally.

Example:

```text
Document:
Aadhaar.pdf

OCR:
Name = Kunal Wadhare
DOB = 15/03/2004

Application:
Name = Kunal Wandhare
DOB = 15/03/2004
```

Result:

```text
Name → mismatch
DOB → match
Overall Data Match Score → 93%
```

That result must be visible on:

```text
WhatsApp
Web
Mobile
```

And voice can explain it:

> The name on your document differs from the name in your application. The data match score is 93 percent. Would you like to use the document name?

---

# 16. Shared conversation context

Conversation context should also be linked to the citizen/application.

Example:

```text
citizen_id
application_id
conversation_id
channel
language
current_intent
known_fields
pending_question
```

If the citizen says on WhatsApp:

> Continue my application.

The bot should know:

```text
Application:
INC-2026-1001

Completed:
Personal details

Pending:
Documents
```

The bot should continue from the correct state.

---

# 17. Channel switching

Implement explicit channel continuity.

Examples:

```text
WhatsApp → Web
Web → WhatsApp
WhatsApp → Mobile
Mobile → WhatsApp
WhatsApp → Phone
Phone → Web
Web → Phone
Mobile → Phone
```

The application state remains unchanged.

Example:

```text
Citizen starts on WhatsApp
        ↓
Application Step 2
        ↓
Opens Mobile App
        ↓
Automatically resumes Step 2
```

No restart.

---

# 18. Real-time synchronization

When one channel changes application state, other active channels should refresh.

Example:

```text
Web edits address
      ↓
Backend
      ↓
Database
      ↓
Application event
      ↓
WhatsApp context updated
      ↓
Mobile updated
```

Use the appropriate mechanism from the current architecture:

* WebSocket
* Server-Sent Events
* event notifications
* polling fallback

Do not introduce unnecessary infrastructure solely for demonstration.

---

# 19. Field-level source tracking

For important fields maintain provenance.

Example:

```json
{
  "full_name": {
    "value": "Kunal Wandhare",
    "source": "WHATSAPP_VOICE",
    "confirmed": true
  },
  "dob": {
    "value": "2004-03-15",
    "source": "OCR",
    "confirmed": false
  }
}
```

Supported sources:

```text
WEB
MOBILE
WHATSAPP_TEXT
WHATSAPP_VOICE
PHONE_VOICE
OCR
OFFICER
SYSTEM
```

This allows the platform to explain where information came from.

---

# 20. Identity and security

The shared state must not mean that any person with a tracking ID can access everything.

Use:

```text
Authentication
+
Citizen identity resolution
+
Authorization
+
Application ownership
```

For example:

```text
Web login
→ authenticated citizen

WhatsApp
→ verified WhatsApp/phone identity

Phone/IVR
→ registered caller + appropriate verification

Tracking ID
→ reference, not sole authorization for sensitive data
```

Do not expose sensitive information solely because someone knows a Tracking ID.

---

# 21. Application lifecycle

Use one common lifecycle:

```text
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
SUBMITTED
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
```

The same lifecycle is used by every channel.

---

# 22. Payment synchronization

Payment can be initiated from Web/Mobile and exposed through WhatsApp as a secure payment continuation.

Example:

```text
Web payment completed
      ↓
Database payment state = PAID
      ↓
WhatsApp:
"Your payment has been received."
      ↓
Mobile:
"Payment completed"
      ↓
Phone:
"Payment for application INC-2026-1001 is completed."
```

---

# 23. Tracking service

Build one tracking service.

Logical API:

```text
GET /applications/{application_id}/status
GET /applications/{application_id}/timeline
GET /tracking/{tracking_id}
```

Every channel uses this same service.

Do not implement:

```text
WhatsApp tracking logic
Web tracking logic
Mobile tracking logic
IVR tracking logic
```

They all call the same backend status service.

---

# 24. Mobile and Web must use the same API contracts

Do not duplicate backend business logic in frontend/mobile.

Preferred:

```text
WhatsApp
Mobile
Web
IVR
     ↓
API / Service Layer
     ↓
Business Rules
     ↓
Application State
     ↓
Database
```

---

# 25. Required end-to-end test

Implement a test with this exact scenario:

```text
1. Register citizen with phone + email
2. Start Income Certificate on WhatsApp
3. Enter personal information
4. Enter family information
5. Upload Aadhaar through WhatsApp
6. OCR processes it
7. Web Portal opens same application
8. Same Tracking ID appears
9. Same document appears
10. Same OCR validation appears
11. Edit address on Web
12. Open Mobile App
13. Verify new address exists
14. Ask WhatsApp for application status
15. Verify returned status
16. Call Phone/IVR
17. Ask for same status
18. Verify same status
19. Change application status in backend
20. Verify Web updates
21. Verify Mobile updates
22. Verify WhatsApp returns new status
23. Verify IVR returns new status
24. Complete payment
25. Verify payment state on every channel
26. Final submission
27. Verify same Tracking ID everywhere
```

---

# 26. Final architecture requirement

The final architecture should be:

```text
                     CITIZEN
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
   WhatsApp          Web Portal       Mobile App
   Text + Voice                         │
        │               │                │
        └───────────────┼────────────────┘
                        │
                   Channel Adapter
                        │
                        ▼
               Citizen Resolver
                        │
                        ▼
             Conversation / NLU
                        │
                        ▼
             Application Orchestrator
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
   Rules Engine     Document/OCR     Status Engine
       │                │                │
       └────────────────┼────────────────┘
                        ▼
               Unified Application
                        │
                 ┌──────┼──────┐
                 ▼      ▼      ▼
               Form   Payment  Verification
                        │
                        ▼
                  Tracking Service
                        │
                        ▼
                     Database
                        ▲
                        │
                    Phone / IVR
```

The **database/state is the center of the architecture, not the channel**.

---

# 27. Success criterion

The implementation is considered successful only when this statement is true:

> **A citizen can start an application through WhatsApp, continue it on the Web Portal or Mobile App, upload documents from any supported channel, receive OCR validation, switch back to WhatsApp or voice, check the same application through Phone/IVR, complete payment, and track the application using the exact same Tracking ID — without creating another application or losing context.**

The citizen should experience the system as **one government service assistant available through multiple channels**, not as five separate applications.

Before coding, inspect the existing repository and map this requirement to the current application model, citizen model, conversation state, repositories, frontend store, APIs and state machine. Reuse existing architecture wherever possible and implement the minimum new abstractions required for unified cross-channel state.

### The most important concept

Think of it as:

**Not this:**

```text
WhatsApp ──> WhatsApp DB
Web      ──> Web DB
Mobile   ──> Mobile DB
IVR      ──> IVR DB
```

**But this:**

```text
                 ┌───────────────┐
 WhatsApp ──────►│               │
 Web ───────────►│ Unified       │
 Mobile ────────►│ Application   │
 Voice ─────────►│ State + DB    │◄──── IVR
                 │               │
                 └───────────────┘
```

For example, when the citizen uploads an Aadhaar through WhatsApp, that single document belongs to the **application**, not to WhatsApp. Therefore Web, Mobile and the voice assistant immediately know that the document exists and can access its validation result.

Likewise, the **Tracking ID belongs to the application**, not to the channel. So `INC-2026-1001` is the same identifier everywhere.

The architecture document already describes the repository's goal of channel-agnostic state and continuity across WhatsApp, IVR, web and mobile, so this requirement is consistent with the intended direction of the existing platform.



Yes. Your clarified product flow is more specific now:

**WhatsApp is the primary citizen-facing application channel** where the citizen can complete the entire information/document collection process using **text or voice in Indian languages**. The **Web Portal is used for the final structured review and verification submission**. After that, WhatsApp remains the citizen's primary notification/status/payment communication channel. Web/mobile/IVR provide additional access to the same application state.

The LLM should also act as a **service-aware conversational assistant**, so citizens can ask cross-questions at any point instead of being forced to follow rigid questions.

Here is the consolidated prompt I recommend giving directly to Antigravity.

# Revenue_Gov_Platform — WhatsApp-First Multilingual Omnichannel Government Certificate Application

Repository:

`https://github.com/kunalwandhare567/Revenue_Gov_Platform`

## 1. PRODUCT VISION

Upgrade the existing Revenue Government Platform into a **WhatsApp-first, multilingual, voice-enabled AI citizen service platform**.

The primary goal is to make government certificate applications easy for citizens who:

* Have limited digital literacy
* Are not comfortable filling long government forms
* Face language barriers
* Prefer speaking instead of typing
* May not understand government terminology
* May have difficulty understanding which documents are required
* Need assistance while applying

The citizen should be able to complete the difficult part of the application through **WhatsApp using either text or voice**.

The Web Portal should primarily be used for:

1. Final application review
2. Structured verification of all information
3. Citizen confirmation
4. Sending the completed application for government verification

After verification submission, WhatsApp becomes the primary communication channel for:

* Verification updates
* Clarification requests
* Government approval notification
* Payment notification
* Payment guidance
* Final submission notification
* Tracking/status queries

The system must support Web, Mobile App and Phone/IVR as additional access channels using the **same citizen identity, application, documents, status and Tracking ID**.

---

# 2. CORE USER JOURNEY

The complete intended journey is:

```text
Citizen
   ↓
WhatsApp
   ↓
Choose Certificate
   ↓
LLM Conversational Assistant
   ↓
Personal Details
   ↓
Family Details
   ↓
Service-Specific Details
   ↓
Required Documents
   ↓
Upload Documents in WhatsApp
   ↓
OCR
   ↓
Document ↔ Application Validation
   ↓
Match Score
   ↓
Mismatch Resolution in WhatsApp
   ↓
Citizen can continue using Text OR Voice
   ↓
All required information/documents completed
   ↓
WhatsApp tells citizen:
"Your application is ready for final review."
   ↓
Secure Web Portal Link
   ↓
Final 4-Section Application Form
   ↓
Citizen Reviews Everything
   ↓
Citizen Confirms
   ↓
Send for Government Verification
   ↓
WhatsApp Confirmation
   ↓
Government Review
   ↓
WhatsApp Status/Clarification Messages
   ↓
Government Approval
   ↓
WhatsApp:
"Your application has been approved."
   ↓
Payment Process
   ↓
Payment
   ↓
Receipt/Transaction Confirmation
   ↓
Final Submission
   ↓
Tracking ID
   ↓
WhatsApp + Web + Mobile + IVR Status Tracking
```

This is the primary business flow.

---

# 3. WHATSAPP IS THE PRIMARY APPLICATION CHANNEL

Do NOT design WhatsApp as merely a notification bot.

WhatsApp is the **main application intake and assistance channel**.

The citizen should be able to perform almost all information collection through WhatsApp before the final Web review.

WhatsApp must support:

```text
Text Chat
+
Voice
+
Document Upload
+
OCR
+
Validation
+
Correction
+
Application Progress
+
LLM Questions
+
Status
+
Notifications
```

---

# 4. WHATSAPP TEXT + VOICE

The citizen can switch between text and voice at any point.

Example:

```text
Citizen:
I want to apply for income certificate.

AI:
Sure. I will help you apply for an Income Certificate.
You can type or speak in your preferred language.
```

Citizen sends voice:

> "मेरा नाम कुणाल वांधरे है।"

System:

```text
Voice
 ↓
STT
 ↓
Language Detection
 ↓
LLM/NLU
 ↓
Name = Kunal Wandhare
 ↓
Application State Updated
```

AI responds in the same language through:

* Text
* Voice/TTS where voice mode is active

---

# 5. INDIAN LANGUAGE SUPPORT

The platform must be designed for multilingual Indian citizens.

The interaction layer should support Indian languages appropriate to the POC, with architecture allowing additional languages to be added without changing business logic.

At minimum design the system to support:

```text
English
Hindi
Marathi
Bengali
Gujarati
Tamil
Telugu
Kannada
Malayalam
Punjabi
Odia
Assamese
Urdu
```

Do not hard-code business rules separately for each language.

Architecture:

```text
User Language
      ↓
STT / Text
      ↓
Language Detection
      ↓
LLM/NLU
      ↓
Language-independent structured data
      ↓
Application / Rules Engine
      ↓
Response
      ↓
Translation / Language Generation
      ↓
Text + TTS
```

Business logic remains language-independent.

---

# 6. LLM MUST BE SERVICE-AWARE

The LLM should not only extract form fields.

It must also act as a **government-service conversational assistant**.

The citizen can ask questions at any point.

Examples:

```text
What is an income certificate?

Why do I need this document?

What documents do I need?

Can I apply for this certificate?

What is the difference between caste and NCL certificate?

Why do you need my father's details?

What should I upload as address proof?

What happens after I submit?

How long does verification take?

Why is my application pending?

What does this status mean?

Do I need to pay anything?

What should I do if my document has a different name?
```

The LLM should answer using the application's **service catalogue, YAML rules, requirements, policies and approved knowledge base**, not hallucinate government requirements.

---

# 7. CROSS-QUESTION HANDLING

This is extremely important.

The conversation must not be a rigid:

```text
Q1 → A1
Q2 → A2
Q3 → A3
```

flow.

Instead:

```text
Application State
       +
Service Knowledge
       +
Conversation Context
       +
LLM
```

Example:

AI:

> Please upload your address proof.

Citizen:

> Why do you need address proof?

The AI should answer the question.

Then automatically continue:

> Address proof is required to verify your residential address for this application. You can upload Aadhaar, voter ID, or another accepted document according to the applicable requirements. Shall we continue with the upload?

The application state must not be lost because the citizen asked a question.

---

# 8. LLM MUST NOT OVERRIDE GOVERNMENT RULES

The LLM is a conversational interface.

The authoritative source must remain:

```text
Service Rules
+
Eligibility Rules
+
Required Documents
+
Field Requirements
+
Validation Rules
+
Fee Rules
+
Workflow Rules
```

Prefer the existing YAML/configuration-driven rules architecture.

The LLM should retrieve/interpret these rules and explain them.

It must not invent requirements.

Architecture:

```text
Citizen
   ↓
LLM
   ↓
Intent
   ↓
Rules / Service Knowledge
   ↓
Validated Action
   ↓
Application State
```

---

# 9. APPLICATION STARTS FROM WHATSAPP

The normal application flow starts through WhatsApp.

Example:

Citizen:

> I want to make an income certificate.

LLM identifies:

```text
service = income_certificate
```

Then loads the service configuration.

The system should know:

```text
Required fields
Required documents
Eligibility
Validation rules
Workflow
Payment rules
```

---

# 10. CONVERSATIONAL INFORMATION COLLECTION

The AI should ask only for information that is:

* Required
* Missing
* Relevant to the selected service
* Not already known

Do not repeatedly ask for information.

Example:

If citizen already provided:

```text
Name = Kunal Wandhare
DOB = 15/03/2004
```

then do not ask:

> Please provide your name.

Instead continue with the next missing field.

---

# 11. APPLICATION STATE

Maintain one centralized application state.

Example:

```json
{
  "citizen_id": "C123",
  "application_id": "APP1001",
  "tracking_id": "INC-2026-1001",
  "service_type": "income_certificate",
  "current_step": "document_collection",
  "status": "IN_PROGRESS",
  "form_data": {},
  "required_documents": [],
  "uploaded_documents": [],
  "validation_results": {},
  "verification_status": null,
  "payment_status": null,
  "preferred_language": "mr"
}
```

WhatsApp is only the interaction channel.

The database/application state is the source of truth.

---

# 12. DOCUMENT UPLOAD DIRECTLY IN WHATSAPP

This is one of the most important features.

Citizen must be able to upload:

```text
JPG
JPEG
PNG
PDF
```

directly through WhatsApp.

Flow:

```text
Citizen uploads document
       ↓
WhatsApp adapter
       ↓
Document service
       ↓
Store document
       ↓
Link to application
       ↓
OCR
       ↓
Field extraction
       ↓
Validation
```

Immediately respond:

> Document received. I am checking it against the information in your application.

---

# 13. DOCUMENT TYPE DETECTION

The system should identify what document was uploaded.

Example:

```text
Aadhaar
Address Proof
Income Proof
Caste Certificate
Self Declaration
Bank Document
Payment Receipt
```

If the system cannot confidently identify it:

> I could not confidently identify this document. Is this your Aadhaar Card, Address Proof, or another document?

---

# 14. OCR PIPELINE

For uploaded documents:

```text
Document
 ↓
Pre-processing
 ↓
OCR
 ↓
Structured field extraction
 ↓
Normalization
 ↓
Application comparison
```

Extract relevant fields based on document type.

Example:

```text
Aadhaar

Name
DOB
Gender
Address
Document number
```

---

# 15. APPLICATION DATA VS DOCUMENT DATA

Compare the OCR-extracted values with the information collected through WhatsApp.

Example:

### WhatsApp/application

```text
Name: Kunal Wandhare
DOB: 15/03/2004
```

### OCR

```text
Name: Kunal Wadhare
DOB: 15/03/2004
```

Validation engine:

```text
Name → mismatch
DOB → match
```

---

# 16. MATCH SCORE

Generate a field-level and overall match score.

Example:

```text
Name       87%
DOB        100%
Address    95%

Overall Match Score: 93%
```

Clearly label this as:

> Application-to-document data match score.

Do NOT call it:

> Document authenticity score.

It is not proof that the document itself is genuine.

---

# 17. MISMATCH HANDLING IN WHATSAPP

If mismatch occurs, WhatsApp must automatically respond.

Example:

> I found a difference between the information you provided and your document.
>
> **Name**
>
> Your application: Kunal Wandhare
> Document: Kunal Wadhare
>
> Match: 87%
>
> Please choose:
>
> 1. Use document name
> 2. Keep application name
> 3. Edit manually

The citizen must be able to resolve the issue directly in WhatsApp.

---

# 18. VOICE MISMATCH RESOLUTION

The same process must work using voice.

AI:

> The name in your document is Kunal Wadhare, while your application says Kunal Wandhare. Which one would you like to use?

Citizen:

> Use the document name.

System:

```text
OCR value selected
 ↓
Application updated
 ↓
Validation recalculated
 ↓
Application state saved
```

AI:

> Done. I have updated your name according to the document.

---

# 19. CHAT CAN CORRECT FORM INFORMATION

The citizen should be able to say:

> Change my address.

AI:

> Sure. Please tell me your new address.

Citizen provides the address through text or voice.

The application state is updated.

The same updated value must eventually appear on the Web Portal.

---

# 20. DOCUMENT VALIDATION SHOULD RUN ASYNCHRONOUSLY

Uploading a document should not freeze the entire conversation.

Flow:

```text
Upload
 ↓
Document saved
 ↓
Chat continues
 ↓
OCR processing in background
 ↓
Validation completed
 ↓
Citizen notified
```

Possible status:

```text
UPLOADED
OCR_PROCESSING
VALIDATING
MATCHED
REVIEW_REQUIRED
VALIDATION_FAILED
```

---

# 21. WHATSAPP APPLICATION PROGRESS

WhatsApp should understand the current application state.

Citizen:

> How much of my application is completed?

AI:

> Your Income Certificate application is 80% complete.
>
> Completed:
> ✓ Personal details
> ✓ Family details
> ✓ Address
> ✓ Aadhaar validation
>
> Remaining:
> • Income proof
> • Final review on the Web Portal

---

# 22. FINAL WEB REDIRECT

Once all required information and documents are collected and validation is complete, WhatsApp should not force the citizen to fill everything again.

Instead:

> Your application information and documents are ready.
>
> Please open the secure Web Portal to review your complete application before sending it for government verification.
>
> [Review Application]

The link must open the citizen's existing application.

Do not create a new application.

---

# 23. WEB PORTAL FINAL REVIEW

The Web Portal must show the same application collected through WhatsApp.

Use four sections:

```text
1. Service / Basic Details

2. Personal + Family Details

3. Documents + Validation

4. Final Review
```

All fields should already be populated.

Citizen should be able to review and correct information.

---

# 24. DOCUMENT SECTION ON WEB

Show:

```text
Document
Upload Source
OCR Status
Extracted Data
Match Score
Validation Status
Mismatch Resolution
```

Example:

```text
Aadhaar.pdf

Uploaded via: WhatsApp
OCR: Completed
Data Match: 94%
Status: Validated
```

---

# 25. FINAL REVIEW

Show complete application summary.

Example:

```text
Income Certificate

Personal Details       ✓
Family Details         ✓
Required Documents     ✓
Document Validation    ✓
Missing Information    0
Mismatches             0
```

Citizen must explicitly confirm:

> I confirm that the information provided is correct.

Then:

```text
SEND FOR GOVERNMENT VERIFICATION
```

---

# 26. VERIFICATION SUBMISSION

After citizen submits from Web:

```text
Web
 ↓
Application API
 ↓
Validation
 ↓
Government verification adapter
 ↓
Application status
```

Set:

```text
status = SUBMITTED_FOR_VERIFICATION
```

---

# 27. IMMEDIATE WHATSAPP CONFIRMATION

After Web submission, send WhatsApp notification:

> Your Income Certificate application has been successfully sent for government verification.
>
> Tracking ID: INC-2026-1001
>
> We will notify you when the government verification status changes.

This is important because WhatsApp remains the citizen's primary communication channel.

---

# 28. GOVERNMENT REVIEW

After submission, the citizen does not need to continuously open the Web Portal.

WhatsApp should inform them.

Example:

> Your application INC-2026-1001 is currently under government review.

---

# 29. CLARIFICATION REQUEST

If government verification requires clarification:

WhatsApp:

> Your application requires additional information.
>
> The verification officer has requested an updated address proof.
>
> Please upload the document here.

Citizen uploads it through WhatsApp.

Then:

```text
Upload
 ↓
OCR
 ↓
Validation
 ↓
Application update
 ↓
Resubmission/clarification workflow
```

The citizen does not have to restart the application.

---

# 30. GOVERNMENT APPROVAL MESSAGE

After approval:

WhatsApp:

> Good news! Your Income Certificate application has been approved by the government.
>
> Your application is now ready for the payment process.
>
> Please continue with payment.

The exact wording should be configurable.

---

# 31. PAYMENT

After approval:

```text
Government Approved
       ↓
Payment Required
       ↓
WhatsApp payment guidance/link
       ↓
Citizen pays
       ↓
Payment confirmation
```

The Web/Mobile application should also show the same payment status.

---

# 32. PAYMENT RECEIPT

If receipt/screenshot upload is required:

Citizen can send it through WhatsApp.

```text
Receipt
 ↓
OCR
 ↓
Transaction ID extraction
 ↓
Amount extraction
 ↓
Payment validation
```

Example:

```text
Expected Amount: ₹X
Paid Amount: ₹X
Transaction ID: XXXXX
Status: Validated
```

---

# 33. FINAL SUBMISSION

After successful payment validation:

```text
Payment Completed
 ↓
Final Application Submission
 ↓
Government/Service system
 ↓
Application submitted
 ↓
Tracking ID
```

WhatsApp:

> Your application has been successfully submitted.
>
> Tracking ID: INC-2026-1001

---

# 34. ONE TRACKING ID EVERYWHERE

The Tracking ID belongs to the application.

Example:

```text
INC-2026-1001
```

It must be identical in:

```text
WhatsApp
Web
Mobile App
Phone/IVR
```

Do not generate a different tracking ID per channel.

---

# 35. PHONE / IVR ROLE

Phone/IVR is primarily intended for citizens who want to **check status and track their application through voice**.

Example:

Citizen calls.

System:

> Welcome. Please tell me what you would like to know.

Citizen:

> Check my application status.

System resolves the registered phone number.

```text
Phone Number
 ↓
Citizen ID
 ↓
Application
 ↓
Tracking ID
 ↓
Current Status
```

Response:

> Your Income Certificate application INC-2026-1001 is currently under government review.

The IVR should also support:

```text
What is my tracking ID?
What is my application status?
Has my application been approved?
Is any document pending?
Has payment been completed?
What should I do next?
```

---

# 36. SAME DATABASE FOR EVERYTHING

This is mandatory.

Use:

```text
Citizen
Application
Conversation
Documents
OCR
Validation
Verification
Payment
Tracking
Events
```

as centralized backend state.

Conceptually:

```text
                 ┌───────────────┐
                 │   CITIZEN DB  │
                 └───────┬───────┘
                         │
                 ┌───────▼───────┐
                 │ APPLICATION DB│
                 └───────┬───────┘
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
  Conversation       Documents          Status
       │                 │                 │
       │                OCR                │
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                  Payment/Tracking
```

---

# 37. ALL CHANNELS MUST KNOW THE SAME CONTEXT

Example:

Citizen tells WhatsApp:

> My address is now Nagpur.

Database changes:

```text
address = Nagpur
```

Later citizen calls IVR:

> What address do you have for my application?

The voice system should retrieve the updated value.

Likewise, if the citizen changes it on Web, WhatsApp should know.

---

# 38. APPLICATION EVENTS

Use application events to synchronize channels.

Examples:

```text
APPLICATION_CREATED
FIELD_UPDATED
DOCUMENT_UPLOADED
OCR_COMPLETED
VALIDATION_COMPLETED
MISMATCH_DETECTED
MISMATCH_RESOLVED
READY_FOR_REVIEW
REVIEW_CONFIRMED
VERIFICATION_SUBMITTED
VERIFICATION_STATUS_CHANGED
CLARIFICATION_REQUIRED
APPLICATION_APPROVED
PAYMENT_REQUIRED
PAYMENT_COMPLETED
FINAL_SUBMISSION
APPLICATION_COMPLETED
```

Each event should contain:

```text
citizen_id
application_id
event_type
source_channel
timestamp
```

---

# 39. LLM + APPLICATION STATE

The LLM must always receive relevant application context.

For example:

```text
Citizen:
What is left?

LLM context:

Service = Income Certificate
Current Step = Documents
Personal Details = Complete
Family Details = Complete
Aadhaar = Validated
Income Proof = Missing
```

LLM response:

> Your personal and family details are complete. Your Aadhaar has also been validated. You still need to upload your income proof. After that, I will prepare your application for final review.

The LLM should not needlessly ask questions already answered.

---

# 40. LLM SHOULD HANDLE INTERRUPTIONS

Example:

AI:

> Please provide your father's name.

Citizen:

> Before that, can I use Aadhaar as address proof?

LLM answers the question using service rules.

Then returns to the pending state:

> Yes, Aadhaar can be used as address proof for this service according to the configured requirements. Now, please tell me your father's name.

The conversation state must remain intact.

---

# 41. LLM SHOULD SUPPORT NATURAL LANGUAGE STATUS

Citizen does not need exact commands.

All of these should work:

```text
Where is my certificate?
What happened to my application?
Is it approved?
Why is it taking so long?
Do I need to do anything?
Has the government checked it?
What documents are left?
Can I check my application?
```

Map them to the same status service.

---

# 42. CHANNEL ARCHITECTURE

Use adapters:

```text
WhatsApp Adapter
Web Adapter
Mobile Adapter
IVR Adapter
```

All normalize input into a common internal format:

```json
{
  "citizen_ref": "...",
  "application_ref": "...",
  "channel": "WHATSAPP",
  "modality": "VOICE",
  "language": "mr",
  "message": "..."
}
```

Then:

```text
Channel
 ↓
Channel Normalizer
 ↓
Citizen Resolver
 ↓
Conversation/LLM
 ↓
Application Orchestrator
 ↓
Rules
 ↓
Database
```

The business logic must not contain:

```text
if whatsapp...
if mobile...
if ivr...
```

for every business operation.

Channel differences belong in the adapter layer.

---

# 43. MOBILE APP

Mobile is another client of the same application APIs.

It should show:

```text
My Applications
Application Details
Documents
Validation
Verification Status
Payment
Tracking
Notifications
```

It must load the same `citizen_id` and `application_id`.

---

# 44. WEB PORTAL

Web is primarily the final review/submission interface but can also show:

```text
Application progress
Documents
Validation
Government status
Payment
Tracking
```

Do not force the citizen to re-enter WhatsApp information.

---

# 45. SECURITY

Use the same central identity model.

Important:

* Tracking ID is not sufficient by itself to expose sensitive citizen information.
* Verify citizen identity before showing sensitive data.
* WhatsApp must use verified phone identity.
* Web/Mobile must use authenticated sessions.
* IVR should use registered caller identification plus appropriate verification.
* Documents must be protected.
* Avoid unnecessary PII in logs.
* Respect the repository's existing Data Guard/security architecture.

---

# 46. DO NOT CREATE DUPLICATE LOGIC

Before implementing:

1. Inspect existing repository.
2. Find current application model.
3. Find current citizen model.
4. Find conversation/state-machine logic.
5. Find document handling.
6. Find OCR implementation.
7. Find existing service/rules configuration.
8. Find existing i18n.
9. Find existing frontend state/store.
10. Reuse existing functionality.

Refactor instead of creating duplicate services.

---

# 47. IMPLEMENTATION ORDER

Implement in this order:

### Phase 1

Unified citizen/application identity.

### Phase 2

WhatsApp-first conversation/application state.

### Phase 3

LLM service-aware Q&A and cross-question handling.

### Phase 4

WhatsApp document upload.

### Phase 5

OCR + field extraction.

### Phase 6

Application/document matching and score.

### Phase 7

WhatsApp mismatch resolution using text and voice.

### Phase 8

Web four-section final review.

### Phase 9

Verification submission.

### Phase 10

WhatsApp verification notifications.

### Phase 11

Government approval → payment.

### Phase 12

Receipt/payment validation.

### Phase 13

Final submission + Tracking ID.

### Phase 14

Web/Mobile/IVR status synchronization.

### Phase 15

End-to-end multilingual testing.

---

# 48. CRITICAL END-TO-END ACCEPTANCE TEST

The following must work:

```text
1. Citizen registers with phone + email.

2. Citizen starts Income Certificate through WhatsApp.

3. Citizen chooses Marathi.

4. Citizen asks questions in Marathi.

5. LLM answers questions in Marathi.

6. Citizen provides personal information through voice.

7. STT converts voice to text.

8. LLM extracts fields.

9. Application state is updated.

10. Citizen uploads Aadhaar through WhatsApp.

11. OCR processes the document.

12. OCR extracts name/DOB/address.

13. System compares OCR data against application data.

14. Match score is generated.

15. Mismatch is detected.

16. WhatsApp automatically explains mismatch.

17. Citizen resolves mismatch through voice.

18. Application state updates.

19. Citizen uploads remaining documents.

20. System validates them.

21. WhatsApp says:
"Your application is ready for final review."

22. Citizen receives secure Web Portal link.

23. Web Portal loads the SAME application.

24. Web Portal shows the SAME documents.

25. Web Portal shows the SAME OCR scores.

26. Citizen reviews four sections.

27. Citizen confirms information.

28. Citizen sends application for government verification.

29. WhatsApp immediately confirms submission.

30. Government status becomes UNDER_REVIEW.

31. WhatsApp sends status notification.

32. Citizen asks through WhatsApp:
"What is my application status?"

33. LLM retrieves current status.

34. Citizen calls Phone/IVR.

35. IVR retrieves the SAME application.

36. IVR returns the SAME status.

37. Citizen opens Mobile App.

38. Mobile shows the SAME application.

39. Government approves application.

40. WhatsApp sends approval notification.

41. Payment becomes available.

42. Citizen completes payment.

43. Payment status updates centrally.

44. WhatsApp confirms payment.

45. Final submission occurs.

46. Same Tracking ID is available on:
    WhatsApp
    Web
    Mobile
    IVR.

47. Citizen can track the application from any supported channel.
```

---

# 49. FINAL SUCCESS CRITERIA

The implementation is successful only if the following statement is true:

> **The citizen does not need to understand the government portal or know which form field belongs where. They can simply communicate with the WhatsApp AI assistant in their preferred Indian language using text or voice, answer questions naturally, ask cross-questions, upload documents, receive OCR-based validation and match scores, resolve mismatches, and complete all required information. Once the application is ready, WhatsApp redirects them to the Web Portal only for final structured review and verification submission. After submission, WhatsApp continues to keep them informed about verification, clarification, approval, payment and final submission. Web, Mobile and Phone/IVR can access the exact same application and Tracking ID because all channels use the same citizen identity, application state and database.**

The architecture should therefore be:

```text
                         CITIZEN
                            │
                            ▼
                    ┌──────────────┐
                    │   WhatsApp   │
                    │ TEXT + VOICE │
                    └──────┬───────┘
                           │
                 PRIMARY APPLICATION
                       CHANNEL
                           │
                           ▼
                 ┌──────────────────┐
                 │ LLM + NLU + RAG  │
                 │ Service Assistant │
                 └────────┬─────────┘
                          │
                 ┌────────▼─────────┐
                 │ Application      │
                 │ Orchestrator     │
                 └────────┬─────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
        Form Data      Documents       Status
                          │
                          ▼
                         OCR
                          │
                          ▼
                  Match / Validation
                          │
              ┌───────────┴──────────┐
              ▼                      ▼
           MATCH                  MISMATCH
                                     │
                               WhatsApp Chat
                               WhatsApp Voice
                                     │
                                     ▼
                              Citizen Resolution
                                     │
                                     ▼
                           Updated Application
                                     │
                                     ▼
                              READY FOR REVIEW
                                     │
                                     ▼
                            ┌─────────────────┐
                            │    WEB PORTAL   │
                            │  4-Section Form │
                            └────────┬────────┘
                                     │
                              Citizen Review
                                     │
                              Final Confirmation
                                     │
                                     ▼
                         Government Verification
                                     │
                                     ▼
                         WhatsApp Notification
                                     │
                          ┌──────────┴─────────┐
                          ▼                    ▼
                     Clarification          Approved
                          │                    │
                      WhatsApp              Payment
                          │                    │
                          └──────────┬─────────┘
                                     ▼
                              Final Submission
                                     │
                                     ▼
                                TRACKING ID
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
          WhatsApp                 Web                  Mobile
              │                      │                      │
              └──────────────────────┼──────────────────────┘
                                     │
                                  Phone/IVR
```

**Most important implementation rule:** do not treat WhatsApp, Web, Mobile and IVR as four applications. They are four interfaces over **one citizen/application state**. The LLM is the conversational layer, the rules engine is the authority for service requirements, and the database/application state is the source of truth.




Yes. For your system, I would **not train the LLM on government rules**. Instead, create a **Government Service Knowledge Base + RAG layer** where the LLM retrieves the relevant authoritative information at runtime.

Your existing architecture already mentions YAML-driven service rules and RAG/knowledge components, so this can fit naturally into the current platform.

## 1. Where should the knowledge come from?

You need to collect information from **authoritative government sources**, preferably in this order:

### Source A — Official Government Portals

For each service, identify the official government page/portal containing:

* Service description
* Eligibility
* Required documents
* Application procedure
* Fees
* Processing time
* Application conditions
* FAQs
* Government instructions
* Contact/office information

For Maharashtra, for example, you would look at official government/revenue-service portals rather than blogs or private certificate websites.

The important rule is:

> **Do not use Google search results directly as your knowledge base.**

Search is useful for discovering sources, but your production knowledge should come from verified official documents/pages.

---

# 2. Government PDFs are particularly useful

Government departments frequently publish:

* GRs / Government Resolutions
* Circulars
* Notifications
* Service manuals
* Application guidelines
* Citizen charters
* Department instructions
* Official FAQs
* Forms
* Acts/rules

These can become your RAG documents.

Example:

```text
knowledge/
├── income_certificate/
│   ├── service_definition.md
│   ├── eligibility.md
│   ├── required_documents.md
│   ├── faq.md
│   └── government_instructions.pdf
│
├── caste_certificate/
│   ├── service_definition.md
│   ├── eligibility.md
│   ├── required_documents.md
│   └── faq.md
│
├── domicile_certificate/
│   └── ...
```

---

# 3. Separate "Rules" from "Knowledge"

This is extremely important for your architecture.

Don't put everything into RAG.

Use **two layers**.

### Layer 1 — Structured Rules

Use YAML/JSON for things the system must enforce.

Example:

```yaml
service:
  id: income_certificate
  name: Income Certificate

eligibility:
  state: Maharashtra
  resident_required: true

required_documents:
  - aadhaar
  - address_proof
  - income_proof

fields:
  - name: full_name
    required: true

  - name: date_of_birth
    required: true

validation:
  name:
    source: document
    match_required: true

workflow:
  review_required: true
  government_verification: true
```

This is used by the **application engine**.

---

### Layer 2 — RAG Knowledge

Use RAG for explanations.

Example:

Citizen:

> Why do I need an income certificate?

RAG retrieves the official explanation.

LLM:

> An income certificate is used to establish the applicant's income for government schemes and services. According to the applicable government guidelines...

So:

```text
YAML
 ↓
What the system MUST enforce

RAG
 ↓
What the AI SHOULD explain
```

---

# 4. Recommended Knowledge Architecture

For your project, I recommend:

```text
              GOVERNMENT SOURCES
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
    Web Pages       PDFs        Circulars
       │             │             │
       └─────────────┼─────────────┘
                     ▼
              Document Ingestion
                     │
                     ▼
               Text Extraction
                     │
                     ▼
              Cleaning / Parsing
                     │
                     ▼
              Metadata Tagging
                     │
                     ▼
               Chunking
                     │
                     ▼
              Embedding Model
                     │
                     ▼
          Vector Database / pgvector
                     │
                     ▼
                 RAG Retriever
                     │
              ┌──────┴──────┐
              ▼             ▼
          LLM Answer     Rule Engine
```

---

# 5. Metadata is very important

Don't just store:

```text
"Income certificate requires Aadhaar..."
```

Store metadata with it.

Example:

```json
{
  "document_id": "gov-income-001",
  "service": "income_certificate",
  "state": "Maharashtra",
  "department": "Revenue Department",
  "source_type": "official_guideline",
  "source_url": "...",
  "title": "Income Certificate Guidelines",
  "effective_date": "2026-01-01",
  "language": "en",
  "authority": "Government of Maharashtra",
  "version": "1.2"
}
```

This becomes extremely useful when the LLM answers citizens.

---

# 6. Why metadata matters for your system

Suppose a citizen asks:

> What documents are required for income certificate?

The RAG system should retrieve only:

```text
service = income_certificate
state = Maharashtra
document_type = required_documents
status = active
```

Not:

```text
caste certificate
NCL certificate
old guidelines
another state
```

So your retrieval becomes:

```text
Citizen Question
      ↓
Intent Detection
      ↓
Service = Income Certificate
      ↓
State = Maharashtra
      ↓
Knowledge Retrieval
      ↓
Official Sources
      ↓
LLM
```

---

# 7. Add source priority

I strongly recommend defining a source hierarchy.

For example:

```text
Priority 1
Official Government Notification / GR

Priority 2
Official Government Department Website

Priority 3
Official Service Portal

Priority 4
Official Government FAQ / Citizen Charter

Priority 5
Official Government Forms / Manuals

Priority 6
Other verified sources
```

The LLM should prefer higher-priority sources.

For government-related answers, don't allow an arbitrary internet source to override an official rule.

---

# 8. RAG should return citations internally

When the LLM answers a citizen, your RAG result should contain:

```json
{
  "answer_context": "...",
  "source": {
    "authority": "Government of Maharashtra",
    "title": "Income Certificate Guidelines",
    "url": "...",
    "effective_date": "...",
    "version": "..."
  }
}
```

Then the LLM can answer:

> According to the Maharashtra Revenue Department guidelines, the required documents include...

On Web you can show:

**Source: Government of Maharashtra — Income Certificate Guidelines**

For WhatsApp, you can optionally provide:

> Source: Government of Maharashtra official guidelines.

---

# 9. RAG should NOT decide eligibility by itself

This is another critical point.

Suppose citizen asks:

> Am I eligible for this certificate?

Don't do:

```text
Question
 ↓
Vector Search
 ↓
LLM
 ↓
YES
```

Instead:

```text
Question
 ↓
LLM extracts facts
 ↓
Structured applicant data
 ↓
Rules Engine
 ↓
Eligibility calculation
 ↓
LLM explains result
```

Example:

```text
Citizen:
I have lived in Maharashtra for 5 years. Can I apply?

        ↓

LLM:
residency_duration = 5 years

        ↓

Rules Engine:
required_residency = X

        ↓

Result:
eligible / not eligible / more information required

        ↓

LLM:
Explain result in citizen's language
```

This prevents hallucinated eligibility decisions.

---

# 10. Use RAG for your LLM cross-question capability

This directly supports the feature you described.

Citizen:

> मला उत्पन्न प्रमाणपत्रासाठी कोणते कागदपत्र लागतील?

System:

```text
Language = Marathi

Intent = required_documents

Service = income_certificate

        ↓

RAG

        ↓

Official documents

        ↓

LLM

        ↓

Marathi answer
```

Response:

> उत्पन्न प्रमाणपत्रासाठी तुमच्या अर्जाच्या नियमांनुसार आधार कार्ड, पत्त्याचा पुरावा आणि उत्पन्नाचा पुरावा आवश्यक आहे. तुमच्या अर्जासाठी अजून उत्पन्नाचा पुरावा अपलोड करायचा आहे.

This is much better than translating an English hard-coded response.

---

# 11. Build a Service Knowledge Package

For each certificate, create a standard knowledge package.

For example:

```text
income_certificate/
│
├── service.yaml
├── eligibility.yaml
├── documents.yaml
├── fields.yaml
├── validation.yaml
├── workflow.yaml
│
└── knowledge/
    ├── official_guidelines.pdf
    ├── faq.md
    ├── procedure.md
    └── government_instructions.pdf
```

### YAML

Machine-enforced rules.

### RAG documents

Human-readable authoritative knowledge.

---

# 12. Example `service.yaml`

```yaml
service:
  id: income_certificate
  name:
    en: Income Certificate
    hi: आय प्रमाण पत्र
    mr: उत्पन्न प्रमाणपत्र

authority:
  department: Revenue Department
  state: Maharashtra

eligibility:
  resident_required: true

required_documents:
  - aadhaar
  - address_proof
  - income_proof

required_fields:
  - full_name
  - date_of_birth
  - address
  - family_details

workflow:
  whatsapp_collection: true
  web_final_review: true
  government_verification: true
  payment_after_approval: true
```

---

# 13. Example RAG document

Create something like:

```markdown
# Income Certificate — Official Service Information

Service:
Income Certificate

Authority:
Government Revenue Department

State:
Maharashtra

Source:
Official Government Notification

Effective Date:
YYYY-MM-DD

## Purpose

[Official explanation]

## Eligibility

[Official eligibility information]

## Required Documents

[Official document requirements]

## Application Process

[Official process]

## Fees

[Official fee information]

## Frequently Asked Questions

### Why is an income certificate required?

[Official explanation]

### How is income verified?

[Official explanation]
```

Do not manually invent this information. Populate it from verified government sources.

---

# 14. How do you actually collect this knowledge?

You have three practical approaches.

### Approach 1 — Manual curated knowledge

Best for your POC.

You manually identify official sources and create structured documents.

Example:

```text
Official Website
      ↓
Download official PDF
      ↓
Extract text
      ↓
Clean
      ↓
Add metadata
      ↓
Add to RAG
```

For 1–4 certificates, this is completely reasonable.

---

### Approach 2 — Government website ingestion

For a larger system:

```text
Official Government Website
        ↓
Crawler
        ↓
Document Parser
        ↓
Change Detection
        ↓
Knowledge Base
```

But don't automatically trust everything crawled.

Only whitelist approved government domains.

For example:

```text
allowed_domains:
  - official-government-domain
  - official-service-portal
```

Then require human verification before publishing changed rules.

---

### Approach 3 — Government API

Best if available.

```text
Government API
      ↓
Service information
      ↓
Rules/knowledge adapter
      ↓
Platform
```

This is preferable because the source is structured and can potentially be synchronized.

---

# 15. Knowledge update mechanism

Government rules change.

Therefore don't make your RAG static forever.

Add:

```text
Knowledge Version
Effective Date
Expiry Date
Source
Last Verified
Verified By
Authority
```

Example:

```json
{
  "version": "2026.08",
  "effective_from": "2026-08-01",
  "effective_until": null,
  "status": "ACTIVE",
  "last_verified": "2026-08-20"
}
```

Then when a new government notification arrives:

```text
Old Version
      ↓
NEW GOVERNMENT RULE
      ↓
Review
      ↓
Approve
      ↓
New Active Version
```

---

# 16. Don't let old RAG documents cause wrong answers

This is a common RAG problem.

Suppose:

```text
2024 document:
Required documents = A, B, C

2026 notification:
Required documents = A, B, C, D
```

A vector search could retrieve the 2024 document.

Therefore retrieval should include:

```text
service
state
authority
effective_date
status
version
```

Then prefer:

```text
ACTIVE + latest effective document
```

---

# 17. Hybrid search is ideal

For your existing architecture, I'd recommend:

```text
User Query
     │
     ├───────────────┐
     ▼               ▼
Vector Search    Keyword Search
     │               │
     └───────┬───────┘
             ▼
        Re-ranking
             ▼
       Relevant sources
             ▼
            LLM
```

Why?

A question such as:

> "What documents are needed for NCL?"

contains important exact terms.

Keyword search can find:

`NCL`

while semantic search understands:

> "Which papers do I need?"

Combining both is more reliable.

---

# 18. Your existing pgvector setup can fit here

If you already have a PostgreSQL/pgvector-based RAG implementation, **reuse it rather than creating another vector database**.

Conceptually:

```text
PostgreSQL
│
├── citizens
├── applications
├── documents
├── validation_results
├── payments
│
└── knowledge_chunks
       │
       ├── embedding
       ├── service
       ├── source
       ├── authority
       ├── effective_date
       └── metadata
```

This keeps your architecture simpler.

---

# 19. Recommended `knowledge_chunks` table

Something like:

```text
knowledge_chunks
-----------------------------
id
document_id
service_id
title
content
embedding
authority
source_type
source_url
state
language
effective_from
effective_until
version
status
created_at
updated_at
```

Then query:

```text
WHERE service_id = 'income_certificate'
AND state = 'Maharashtra'
AND status = 'ACTIVE'
```

before semantic retrieval.

---

# 20. RAG + LLM + Rules together

Your final architecture should be:

```text
                  CITIZEN
                     │
              WhatsApp Voice/Text
                     │
                     ▼
              Language Detection
                     │
                     ▼
                    LLM
                     │
          ┌──────────┴──────────┐
          │                     │
     Cross-question         Application
          │                  extraction
          ▼                     │
        RAG                     ▼
          │              Rules Engine
          │                     │
          └──────────┬──────────┘
                     ▼
             Application State
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
     Documents      OCR        Workflow
        │            │            │
        └────────────┼────────────┘
                     ▼
                 Web Review
                     │
                     ▼
              Government Verify
```

---

## 21. The most important distinction

I would tell Antigravity to implement **three separate knowledge/control mechanisms**:

| Component              | Purpose                        | Example                  |
| ---------------------- | ------------------------------ | ------------------------ |
| **Service YAML**       | Machine-enforced rules         | Aadhaar required         |
| **RAG Knowledge Base** | Explain government information | Why Aadhaar is required  |
| **Application DB**     | Citizen-specific facts         | Citizen uploaded Aadhaar |

So:

```text
Government Rule:
"Address proof is required."
        ↓
YAML

Government Explanation:
"Address proof establishes residence..."
        ↓
RAG

Citizen:
"Aadhaar uploaded, OCR says address X."
        ↓
Application DB
```

The LLM combines all three.

---

## 22. For your POC, don't over-engineer it

Since you're demonstrating this system, I would start with **one certificate**, probably Income Certificate.

Create:

```text
1 service YAML
1 official service guideline
1 official FAQ
1 official document requirement source
1 eligibility source
1 government instruction
```

Then build:

```text
Official Sources
       ↓
Curated Knowledge
       ↓
Chunking
       ↓
Embeddings
       ↓
pgvector
       ↓
RAG
       ↓
LLM
```

Once that works correctly, adding:

```text
Caste
Domicile
NCL
```

becomes mostly a matter of adding new service configurations and authoritative knowledge packages rather than rewriting the AI.

### One final recommendation

For a government application system, make the LLM answer with **source grounding** internally. For every service-related answer, retain:

```text
answer
source_document
source_authority
source_url
effective_date
knowledge_version
confidence/retrieval score
```

That gives you a much stronger demo:

> **Citizen asks a question → LLM retrieves the applicable government source → answers in Marathi/Hindi/etc. → system knows which official rule it used.**

That is substantially safer and more defensible than simply giving the LLM a collection of PDFs and asking it to answer.



# can you give me mock data knowledge base because . iwant now only to built prototype so please give me as you have regarding this ,


Yes. For your **POC/prototype**, I recommend creating a **mock Government Knowledge Base** for the four services you have been designing:

1. Income Certificate
2. Caste Certificate
3. Domicile Certificate
4. NCL Certificate

Important: this data should be explicitly marked **MOCK / DEMO DATA**. Do not present it to citizens as actual government requirements until you replace it with verified official sources.

A good prototype should have **two knowledge layers**:

```text
                    MOCK KNOWLEDGE BASE
                           │
              ┌────────────┴────────────┐
              │                         │
        STRUCTURED RULES           RAG DOCUMENTS
          YAML/JSON                 Markdown
              │                         │
              ▼                         ▼
        Form / Validation          LLM Answers
        Eligibility                FAQs
        Documents                  Explanations
        Workflow                   Procedures
```

Below is a ready-to-use structure.

---

# 1. Recommended folder structure

Put this inside your backend, for example:

```text
knowledge_base/
│
├── README.md
│
├── services/
│   │
│   ├── income_certificate/
│   │   ├── service.yaml
│   │   ├── eligibility.md
│   │   ├── required_documents.md
│   │   ├── faq.md
│   │   ├── procedure.md
│   │   └── government_instructions.md
│   │
│   ├── caste_certificate/
│   │   ├── service.yaml
│   │   ├── eligibility.md
│   │   ├── required_documents.md
│   │   ├── faq.md
│   │   ├── procedure.md
│   │   └── government_instructions.md
│   │
│   ├── domicile_certificate/
│   │   ├── service.yaml
│   │   ├── eligibility.md
│   │   ├── required_documents.md
│   │   ├── faq.md
│   │   ├── procedure.md
│   │   └── government_instructions.md
│   │
│   └── ncl_certificate/
│       ├── service.yaml
│       ├── eligibility.md
│       ├── required_documents.md
│       ├── faq.md
│       ├── procedure.md
│       └── government_instructions.md
│
└── metadata/
    └── sources.yaml
```

---

# 2. `README.md`

```markdown
# Government Service Knowledge Base

## IMPORTANT

This knowledge base contains MOCK / DEMONSTRATION DATA
for the Revenue Government Platform POC.

It is NOT an official government knowledge source.

All service requirements, eligibility criteria, documents,
fees, processing times and procedures must be replaced or
verified against authoritative government sources before
production use.

## Supported Services

1. Income Certificate
2. Caste Certificate
3. Domicile Certificate
4. NCL Certificate

## Knowledge Types

- Service Definition
- Eligibility
- Required Documents
- Application Procedure
- FAQs
- Government Instructions
- Validation Rules
```

---

# 3. Income Certificate

## `service.yaml`

```yaml
metadata:
  knowledge_type: service_definition
  environment: MOCK
  authority: "Mock Revenue Department"
  state: "Maharashtra"
  version: "1.0"
  status: "DEMO_ONLY"

service:
  id: income_certificate
  name:
    en: Income Certificate
    hi: आय प्रमाण पत्र
    mr: उत्पन्न प्रमाणपत्र

  description:
    en: "A certificate used to establish the annual income of an individual or family."
    hi: "व्यक्ति या परिवार की वार्षिक आय दर्शाने वाला प्रमाणपत्र।"
    mr: "व्यक्ती किंवा कुटुंबाचे वार्षिक उत्पन्न दर्शविणारे प्रमाणपत्र."

application:
  primary_channel: whatsapp
  final_review_channel: web

supported_modes:
  whatsapp_text: true
  whatsapp_voice: true
  web: true
  mobile: true
  phone_ivr: true

workflow:
  information_collection: true
  document_upload: true
  ocr_validation: true
  final_web_review: true
  government_verification: true
  payment_after_approval: true

required_fields:

  - id: full_name
    label: Full Name
    type: string
    required: true

  - id: date_of_birth
    label: Date of Birth
    type: date
    required: true

  - id: gender
    label: Gender
    type: enum
    required: true

  - id: mobile_number
    label: Mobile Number
    type: phone
    required: true

  - id: email
    label: Email
    type: email
    required: false

  - id: address
    label: Residential Address
    type: address
    required: true

  - id: district
    label: District
    type: string
    required: true

  - id: taluka
    label: Taluka
    type: string
    required: true

  - id: village
    label: Village
    type: string
    required: false

  - id: family_income
    label: Annual Family Income
    type: number
    required: true

  - id: father_name
    label: Father's Name
    type: string
    required: true

documents:
  - aadhaar
  - address_proof
  - income_proof
  - self_declaration

validation:
  document_field_matching: true
  ocr_required: true

review:
  citizen_confirmation_required: true

verification:
  government_verification_required: true

payment:
  enabled: true
  stage: after_government_approval
```

---

# 4. Income Certificate — Required Documents

`required_documents.md`

```markdown
# Income Certificate — Required Documents

IMPORTANT:
This is MOCK / DEMO information for the prototype.

## Required Documents

The prototype expects the following documents:

1. Aadhaar Card
2. Address Proof
3. Income Proof
4. Self Declaration

## Aadhaar Card

The system may extract:

- Applicant name
- Date of birth
- Gender
- Address

## Address Proof

The system may extract:

- Applicant name
- Residential address

## Income Proof

The system may extract:

- Applicant/family name
- Income amount
- Financial period
- Issuing authority

## Self Declaration

The system checks whether:

- Applicant name is present
- Declaration text is present
- Date is present
- Signature/confirmation is present

## Missing Document Behaviour

If a required document is missing, the AI should inform the citizen.

Example:

"Your application is almost complete. We still need your income proof."

The citizen can upload the document directly through WhatsApp.
```

---

# 5. Income Certificate — Eligibility

`eligibility.md`

```markdown
# Income Certificate — Eligibility

IMPORTANT:
MOCK / DEMO DATA ONLY.

The prototype uses the following simplified eligibility conditions.

## Conditions

An applicant should:

1. Provide valid identity information.
2. Provide a residential address.
3. Provide family income information.
4. Provide required supporting documents.
5. Complete the citizen declaration.

## AI Behaviour

The AI should not make a final government eligibility decision.

Instead it should say:

"Based on the information you provided, your application appears to meet the basic conditions configured for this service. Final eligibility will be determined during government verification."

## Missing Information

If information is missing:

"Before we continue, I need your annual family income."

## Cross Question

Citizen:

"Can I apply if I don't have an income proof?"

AI:

"According to the requirements configured for this prototype, income proof is required. Please upload an accepted income document or follow the clarification process."
```

---

# 6. Income Certificate FAQ

`faq.md`

```markdown
# Income Certificate — FAQ

IMPORTANT:
MOCK / DEMO DATA ONLY.

## Q1. What is an income certificate?

An income certificate is a document used to establish the annual income of an individual or family.

## Q2. Why do I need an income certificate?

It may be required for certain government services, schemes, benefits, scholarships or other official purposes.

## Q3. What documents are required?

The prototype requires:

- Aadhaar
- Address proof
- Income proof
- Self declaration

## Q4. Can I upload documents through WhatsApp?

Yes. In this prototype, citizens can upload supported documents through WhatsApp.

## Q5. Can I speak instead of typing?

Yes. The WhatsApp assistant supports voice interaction.

## Q6. What languages are supported?

The prototype is designed for multilingual interaction and can support Indian languages configured in the system.

## Q7. What happens after I upload a document?

The system performs OCR and compares extracted information with your application information.

## Q8. What is the validation score?

The validation score represents how closely the information extracted from the document matches the information provided in the application.

It is not a government approval score.

## Q9. What happens if my name is different on the document?

The system will show the difference and ask you whether you want to:

1. Use the document information
2. Keep the application information
3. Edit the information

## Q10. Where do I finally submit my application?

After completing information and documents through WhatsApp, you will be redirected to the Web Portal for final review and submission for verification.

## Q11. Can I check my application through phone?

Yes. The prototype supports phone/IVR status checking.

## Q12. Can I track my application through WhatsApp?

Yes. The citizen can ask for application status through WhatsApp.

## Q13. Will my tracking ID be the same everywhere?

Yes. The same application Tracking ID is used by WhatsApp, Web, Mobile and Phone/IVR.
```

---

# 7. Income Certificate — Procedure

`procedure.md`

```markdown
# Income Certificate — Application Procedure

IMPORTANT:
MOCK / DEMO DATA ONLY.

## Step 1 — Start

Citizen starts through WhatsApp.

## Step 2 — Select Service

Citizen selects Income Certificate.

## Step 3 — Personal Information

AI collects:

- Name
- DOB
- Gender
- Mobile
- Address

## Step 4 — Family Information

AI collects:

- Father's name
- Family members
- Annual family income

## Step 5 — Documents

Citizen uploads required documents through WhatsApp.

## Step 6 — OCR

The system extracts information from uploaded documents.

## Step 7 — Validation

The system compares OCR information with application information.

## Step 8 — Mismatch Resolution

If differences are found, the AI asks the citizen to resolve them.

## Step 9 — Final Review

Once all information is complete, the citizen receives a secure Web Portal link.

## Step 10 — Citizen Confirmation

Citizen reviews all four sections and confirms the application.

## Step 11 — Government Verification

The application is sent for government verification.

## Step 12 — Notification

WhatsApp informs the citizen about verification status.

## Step 13 — Approval

After government approval, the citizen receives a WhatsApp notification.

## Step 14 — Payment

Citizen completes payment if applicable.

## Step 15 — Final Submission

Payment/receipt is validated and application is submitted.

## Step 16 — Tracking

Citizen receives a Tracking ID.
```

---

# 8. Caste Certificate

Create `caste_certificate/service.yaml`

```yaml
metadata:
  knowledge_type: service_definition
  environment: MOCK
  authority: "Mock Revenue Department"
  state: "Maharashtra"
  version: "1.0"
  status: "DEMO_ONLY"

service:
  id: caste_certificate

  name:
    en: Caste Certificate
    hi: जाति प्रमाण पत्र
    mr: जात प्रमाणपत्र

  description:
    en: "A certificate used to record the applicant's caste category."
    hi: "आवेदक की जाति श्रेणी दर्शाने वाला प्रमाणपत्र।"
    mr: "अर्जदाराची जात श्रेणी दर्शविणारे प्रमाणपत्र."

application:
  primary_channel: whatsapp
  final_review_channel: web

supported_modes:
  whatsapp_text: true
  whatsapp_voice: true
  web: true
  mobile: true
  phone_ivr: true

required_fields:

  - id: full_name
    type: string
    required: true

  - id: date_of_birth
    type: date
    required: true

  - id: father_name
    type: string
    required: true

  - id: address
    type: address
    required: true

  - id: caste_name
    type: string
    required: true

  - id: district
    type: string
    required: true

documents:
  - aadhaar
  - address_proof
  - caste_supporting_document
  - family_document
  - self_declaration

validation:
  document_field_matching: true
  ocr_required: true

review:
  citizen_confirmation_required: true

verification:
  government_verification_required: true

payment:
  enabled: true
  stage: after_government_approval
```

---

# 9. Caste FAQ

```markdown
# Caste Certificate FAQ

IMPORTANT:
MOCK / DEMO DATA ONLY.

## What is a caste certificate?

A caste certificate is an official document used to establish the caste category of an applicant.

## What documents are required?

The prototype requires:

- Aadhaar
- Address proof
- Caste supporting document
- Family document
- Self declaration

## Can I apply using WhatsApp?

Yes. The prototype supports starting the application through WhatsApp.

## Can I use voice?

Yes. The citizen can speak to the assistant.

## What happens if my name is different on my document?

The OCR validation system will detect the difference and ask you to resolve it.

## Can I change my information?

Yes. Before final submission, the citizen can update information through WhatsApp or the Web Portal.

## Where is final review done?

Final review is performed on the Web Portal.

## How can I track my application?

The same Tracking ID can be used across WhatsApp, Web, Mobile and Phone/IVR.
```

---

# 10. Domicile Certificate

`domicile_certificate/service.yaml`

```yaml
metadata:
  knowledge_type: service_definition
  environment: MOCK
  authority: "Mock Revenue Department"
  state: "Maharashtra"
  version: "1.0"
  status: "DEMO_ONLY"

service:
  id: domicile_certificate

  name:
    en: Domicile Certificate
    hi: निवास प्रमाण पत्र
    mr: अधिवास प्रमाणपत्र

  description:
    en: "A certificate used to establish residential/domicile status."
    hi: "निवास या अधिवास स्थिति दर्शाने वाला प्रमाणपत्र।"
    mr: "निवासी किंवा अधिवास स्थिती दर्शविणारे प्रमाणपत्र."

application:
  primary_channel: whatsapp
  final_review_channel: web

supported_modes:
  whatsapp_text: true
  whatsapp_voice: true
  web: true
  mobile: true
  phone_ivr: true

required_fields:

  - id: full_name
    type: string
    required: true

  - id: date_of_birth
    type: date
    required: true

  - id: father_name
    type: string
    required: true

  - id: current_address
    type: address
    required: true

  - id: residence_duration
    type: number
    required: true

  - id: district
    type: string
    required: true

documents:
  - aadhaar
  - address_proof
  - residence_proof
  - birth_or_school_document
  - self_declaration

validation:
  document_field_matching: true
  ocr_required: true

review:
  citizen_confirmation_required: true

verification:
  government_verification_required: true

payment:
  enabled: true
  stage: after_government_approval
```

---

# 11. Domicile FAQ

```markdown
# Domicile Certificate FAQ

IMPORTANT:
MOCK / DEMO DATA ONLY.

## What is a domicile certificate?

It is a document used to establish a person's residential or domicile status.

## What documents are required?

The prototype requires:

- Aadhaar
- Address proof
- Residence proof
- Birth or school document
- Self declaration

## Can I apply using WhatsApp?

Yes.

## Can I use voice?

Yes. The AI assistant supports voice interaction.

## Why do you need my residence information?

Residence information is used by the configured rules to evaluate the application.

## What happens after document upload?

OCR extracts information and compares it with your application.

## What if the address on my document is different?

The system will show the mismatch and ask you how you want to resolve it.

## Where do I submit the final application?

The final application is reviewed and submitted through the Web Portal.
```

---

# 12. NCL Certificate

`ncl_certificate/service.yaml`

```yaml
metadata:
  knowledge_type: service_definition
  environment: MOCK
  authority: "Mock Revenue Department"
  state: "Maharashtra"
  version: "1.0"
  status: "DEMO_ONLY"

service:
  id: ncl_certificate

  name:
    en: Non-Creamy Layer Certificate
    hi: नॉन-क्रीमी लेयर प्रमाण पत्र
    mr: नॉन-क्रीमी लेयर प्रमाणपत्र

  description:
    en: "A certificate used to establish non-creamy layer status for applicable purposes."
    hi: "लागू उद्देश्यों के लिए नॉन-क्रीमी लेयर स्थिति दर्शाने वाला प्रमाणपत्र।"
    mr: "लागू उद्देशांसाठी नॉन-क्रीमी लेयर स्थिती दर्शविणारे प्रमाणपत्र."

application:
  primary_channel: whatsapp
  final_review_channel: web

supported_modes:
  whatsapp_text: true
  whatsapp_voice: true
  web: true
  mobile: true
  phone_ivr: true

required_fields:

  - id: full_name
    type: string
    required: true

  - id: date_of_birth
    type: date
    required: true

  - id: father_name
    type: string
    required: true

  - id: caste_category
    type: string
    required: true

  - id: family_income
    type: number
    required: true

  - id: address
    type: address
    required: true

  - id: district
    type: string
    required: true

documents:
  - aadhaar
  - caste_certificate
  - income_proof
  - address_proof
  - family_income_document
  - self_declaration

validation:
  document_field_matching: true
  ocr_required: true

review:
  citizen_confirmation_required: true

verification:
  government_verification_required: true

payment:
  enabled: true
  stage: after_government_approval
```

---

# 13. NCL FAQ

```markdown
# NCL Certificate FAQ

IMPORTANT:
MOCK / DEMO DATA ONLY.

## What is an NCL certificate?

It is a certificate used to establish non-creamy layer status for applicable purposes.

## What information is required?

The prototype collects:

- Applicant name
- DOB
- Father's name
- Caste category
- Family income
- Address

## What documents are required?

The prototype requires:

- Aadhaar
- Caste certificate
- Income proof
- Address proof
- Family income document
- Self declaration

## Why is family income required?

The prototype uses family income as one of the configured inputs for the NCL assessment workflow.

## Can I provide information through voice?

Yes.

## Can I ask questions during the application?

Yes. The AI assistant supports cross-question handling.

## Can I upload documents through WhatsApp?

Yes.

## What happens if my documents don't match?

The AI will show the mismatch and ask you to resolve it before final review.

## Where is final review performed?

The Web Portal.

## How do I track the application?

Use the same Tracking ID through WhatsApp, Web, Mobile or Phone/IVR.
```

---

# 14. Mock Government Instructions

For each service, create a `government_instructions.md`.

Example:

```markdown
# Government Instructions

IMPORTANT:
MOCK / DEMO DATA ONLY.

1. Applicant must provide truthful information.

2. Documents uploaded should be clear and readable.

3. The applicant should verify all information before final submission.

4. If information differs between the application and documents,
   the applicant must resolve the mismatch.

5. OCR validation is an assistance mechanism and does not constitute
   government verification.

6. Final approval is performed by the authorized government authority.

7. The citizen should retain the application Tracking ID.

8. The citizen may use supported channels to check application status.

9. Additional documents may be requested during government verification.

10. Payment should only be completed through the authorized payment process.

11. The AI assistant cannot guarantee government approval.

12. The information in this file is only for the Revenue Government
    Platform prototype and must be replaced with verified government
    instructions before production.
```

---

# 15. Mock source metadata

Create:

`metadata/sources.yaml`

```yaml
knowledge_base:
  environment: MOCK
  version: "0.1"

  disclaimer: >
    All sources in this prototype knowledge base are mock/demo sources.
    They are not authoritative government sources.

sources:

  - id: mock_income_001
    service: income_certificate
    title: "Mock Income Certificate Service Guidelines"
    authority: "Mock Revenue Department"
    source_type: "government_guideline"
    source_url: "https://example.gov.in/income-certificate"
    state: "Maharashtra"
    language: "en"
    version: "1.0"
    effective_from: "2026-01-01"
    status: "DEMO"

  - id: mock_caste_001
    service: caste_certificate
    title: "Mock Caste Certificate Guidelines"
    authority: "Mock Revenue Department"
    source_type: "government_guideline"
    source_url: "https://example.gov.in/caste-certificate"
    state: "Maharashtra"
    language: "en"
    version: "1.0"
    effective_from: "2026-01-01"
    status: "DEMO"

  - id: mock_domicile_001
    service: domicile_certificate
    title: "Mock Domicile Certificate Guidelines"
    authority: "Mock Revenue Department"
    source_type: "government_guideline"
    source_url: "https://example.gov.in/domicile-certificate"
    state: "Maharashtra"
    language: "en"
    version: "1.0"
    effective_from: "2026-01-01"
    status: "DEMO"

  - id: mock_ncl_001
    service: ncl_certificate
    title: "Mock NCL Certificate Guidelines"
    authority: "Mock Revenue Department"
    source_type: "government_guideline"
    source_url: "https://example.gov.in/ncl-certificate"
    state: "Maharashtra"
    language: "en"
    version: "1.0"
    effective_from: "2026-01-01"
    status: "DEMO"
```

**Do not actually use `example.gov.in` as if it were a real authority.** It is only a placeholder to make your POC schema complete.

---

# 16. RAG chunks

When you ingest these documents into your existing RAG, each chunk should carry metadata.

Example:

```json
{
  "chunk_id": "income_faq_001",
  "service_id": "income_certificate",
  "knowledge_type": "faq",
  "content": "What documents are required for an income certificate?...",
  "authority": "Mock Revenue Department",
  "state": "Maharashtra",
  "language": "en",
  "version": "1.0",
  "status": "DEMO"
}
```

Another:

```json
{
  "chunk_id": "income_eligibility_001",
  "service_id": "income_certificate",
  "knowledge_type": "eligibility",
  "content": "The prototype expects the applicant to provide...",
  "authority": "Mock Revenue Department",
  "state": "Maharashtra",
  "language": "en",
  "version": "1.0",
  "status": "DEMO"
}
```

---

# 17. How your LLM should use it

Suppose the citizen asks:

> What documents do I need for income certificate?

Your backend should do approximately:

```text
User Question
     ↓
Language Detection
     ↓
LLM Intent Extraction
     ↓
service = income_certificate
intent = required_documents
     ↓
RAG Filter
     ↓
service_id = income_certificate
knowledge_type = required_documents
status = DEMO
     ↓
Vector Search
     ↓
Relevant Chunks
     ↓
LLM
     ↓
Answer in Citizen Language
```

---

# 18. Cross-question example

Citizen:

> Why do you need income proof?

RAG retrieves:

```text
income_certificate
knowledge_type = faq
```

LLM answers:

> Income proof is required in this prototype to support the income information provided in your application. The document is checked against the details you entered.

Then the conversation continues:

> Please upload your income proof.

---

# 19. Very important: don't put all knowledge into one giant prompt

Avoid this:

```text
LLM prompt:

Here are all 500 pages of government documents...
Now answer the citizen.
```

Instead:

```text
Citizen Question
      ↓
Intent
      ↓
Service
      ↓
Metadata filter
      ↓
RAG
      ↓
Top relevant chunks
      ↓
LLM
```

This will be faster, cheaper and much easier to control.

---

# 20. What I recommend for your POC

You don't need to build a huge government crawler right now.

Use this architecture:

```text
               MOCK GOVERNMENT DATA
                       │
              ┌────────┴────────┐
              ▼                 ▼
           YAML Rules        Markdown
              │                 │
              │                 ▼
              │            Chunking
              │                 │
              │             Embeddings
              │                 │
              │              pgvector
              │                 │
              │                RAG
              │                 │
              └────────┬────────┘
                       ▼
                      LLM
                       │
              ┌────────┴────────┐
              ▼                 ▼
       Application Action    Explanation
```

**YAML controls what the system does.**

**RAG controls what the LLM knows/explains.**

**Database controls what the citizen has actually provided.**

That separation is exactly what you want for your WhatsApp-first prototype.

### Example final interaction

```text
Citizen:
"मला उत्पन्न प्रमाणपत्रासाठी कोणते कागदपत्र लागतील?"

             ↓

Language = Marathi
Service = Income Certificate
Intent = Required Documents

             ↓

RAG

             ↓

Mock Knowledge Base

             ↓

LLM

             ↓

"उत्पन्न प्रमाणपत्रासाठी या प्रोटोटाइपमध्ये
आधार कार्ड, पत्त्याचा पुरावा, उत्पन्नाचा पुरावा
आणि स्वयंघोषणा आवश्यक आहे.

तुम्ही आधार कार्ड आधीच अपलोड केले आहे.
आता कृपया उत्पन्नाचा पुरावा अपलोड करा."
```

And importantly, the LLM simultaneously knows the **citizen's actual application state**. That's what turns your RAG from a generic FAQ chatbot into the **service-aware application assistant** you want.


