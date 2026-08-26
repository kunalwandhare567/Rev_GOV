# 🏛️ Multilingual AI-Powered Citizen Revenue Services Platform — Enterprise Backend

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/SQLite-WAL_Mode-003B57?style=flat&logo=sqlite)](https://www.sqlite.org/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python)](https://www.python.org/)
[![Pytest](https://img.shields.io/badge/Pytest-8.3-0A9EDC?style=flat&logo=pytest)](https://docs.pytest.org/)

The enterprise backend service for the **Multilingual AI-Powered Citizen Revenue Services Platform**. Built with **FastAPI**, **SQLAlchemy 2.0**, **Pydantic v2**, and **SQLite (WAL mode)**, providing an omnichannel conversational backend across Web, WhatsApp, IVR Voice, and Admin channels.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+ (Python 3.13 / 3.14 fully supported)
- SQLite3 (included with Python)
- System Tesseract OCR (Optional — fallback simulated OCR works out of the box)

### 1. Setup Virtual Environment
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# Create .env from template
copy .env.example .env    # Windows
# cp .env.example .env     # Linux/macOS
```
*Edit `.env` to select your active Cloud LLM provider (`gemini`, `groq`, or `openrouter`) and add your API key.*

### 4. Run the Development Server
```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
Or directly run:
```bash
python main.py
```

### 5. Access Interactive API Documentation
- **Swagger UI (Interactive Docs)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 🏗️ Backend Directory Layout

```
backend/
├── app/
│   ├── api/
│   │   └── routes/                 # REST & SSE API Route Handlers
│   │       ├── applications.py      # Application CRUD, review & admin queue
│   │       ├── auth.py              # Citizen & Admin JWT authentication
│   │       ├── conversation.py      # Main citizen web chat endpoint
│   │       ├── data_guard.py        # PII inspection & Data Guard live stats
│   │       ├── documents.py         # Document upload, OCR & discrepancy resolution
│   │       ├── ivr.py               # IVR phone telephony & DTMF status routes
│   │       ├── mock_government.py   # Back-office government simulation routes
│   │       ├── payment.py           # Post-approval payment & receipt OCR
│   │       ├── stream.py            # Server-Sent Events (SSE) live updates
│   │       ├── tracking.py          # Public QR certificate status lookup
│   │       └── whatsapp.py          # WhatsApp web simulator webhooks
│   ├── channels/                   # Channel adapters (Web, WhatsApp, IVR, Mobile)
│   ├── core/                       # App configuration, DB session, Security middleware
│   ├── data_guard/                 # Data Guard PII Classifier & OPA policy firewall
│   ├── data_layer/                 # AES-256 field encryption & Data Repositories
│   ├── llm/                        # Provider Abstraction (Gemini, Groq, OpenRouter)
│   │   ├── base.py
│   │   ├── gemini_provider.py
│   │   ├── groq_provider.py
│   │   ├── openrouter_provider.py
│   │   ├── provider_factory.py     # Single-provider initialization (fail-fast)
│   │   └── llm_service.py
│   ├── models/                     # SQLAlchemy DB Models (15 tables)
│   │   └── db_models.py
│   ├── orchestration/              # Conversational State Machine & NLU
│   │   ├── nlu/                    # NLU Service, Intent Classifier & Field Corrector
│   │   └── state_machine/          # 13-node Application FSM & Orchestrator
│   ├── rules_engine/               # Declarative Rules Engine
│   │   ├── engine.py               # Spec Loader, Validator, Eligibility & Fee Calc
│   │   └── fraud_scorer.py         # Anomaly & Fraud Scoring Engine
│   └── services/                   # Business Services
│       ├── citizen_resolver.py     # Channel Identity & Tokenized Citizen Resolver
│       ├── ocr_service.py          # Tesseract OCR & PyMuPDF text extractor
│       ├── matching_service.py     # Weighted field similarity matcher
│       ├── readiness_engine.py     # 0-100 Application Readiness Score
│       ├── rag_service.py          # Knowledge base RAG search engine
│       ├── payment_service.py      # Post-approval payment gateway adapter
│       └── certificate_service.py  # PDF Certificate Generation & Storage
├── knowledge/                      # RAG Markdown Knowledge Base (Income, Caste, Domicile, OBC)
├── seed/service_specs/             # Declarative YAML Service Definitions
│   ├── income_certificate.yaml
│   ├── caste_certificate.yaml
│   ├── domicile_certificate.yaml
│   └── obc_ncl_certificate.yaml
├── tests/                          # 17 Pytest Test Suites (180+ tests)
├── main.py                         # Application Entrypoint
└── requirements.txt                # Dependencies
```

---

## 📡 Key REST API Endpoints

### 💬 Conversation & Chat
- `POST /api/v1/conversation/message`: Send user utterance, get AI response & state.
- `POST /api/v1/conversation/channel-switch`: Transfer ongoing session across channels.

### 📄 Document Upload & Discrepancy Resolution
- `POST /api/v1/documents/upload`: Upload file (PDF/Image), runs OCR, returns extracted fields & match score.
- `POST /api/v1/documents/resolve-mismatch`: Resolve declared vs. OCR field discrepancies.

### 📋 Applications & Admin Review
- `GET /api/v1/applications/my-applications`: List authenticated citizen's applications.
- `GET /api/v1/applications/admin/list`: List applications in admin review queue.
- `POST /api/v1/applications/admin/{id}/decision`: Admin decision (`APPROVE`, `REJECT`, `REQUEST_CLARIFICATION`).

### 💳 Post-Approval Payment & Receipt
- `POST /api/v1/payment/initiate`: Initiate fee payment (*allowed ONLY after government approval*).
- `POST /api/v1/payment/verify-receipt`: Upload payment screenshot for OCR verification.

### 📜 Certificate Tracking & Public Lookup
- `GET /api/v1/tracking/{tracking_id}`: Public status lookup by tracking ID or certificate number.

---

## ⚙️ Services Available (Declarative YAML Specs)

| Service Name | Spec ID | Fee | Default SLA |
| :--- | :--- | :---: | :---: |
| **Income Certificate** | `income_certificate` | ₹50 | 3 Days |
| **Caste Certificate** | `caste_certificate` | ₹50 | 10 Days |
| **Domicile Certificate** | `domicile_certificate` | ₹50 | 15 Days |
| **OBC Non-Creamy Layer** | `obc_ncl_certificate` | ₹50 | 15 Days |

*Adding a new revenue service requires adding **only one YAML file** into `seed/service_specs/`.*

---

## 🔒 Security & Data Guard Architecture

1. **Zero-PII Cloud Rule**: Data Guard scans outgoing prompts and blocks/redacts sensitive citizen details (Aadhaar, PAN, phone, address, income) before sending requests to external LLM providers.
2. **Field-Level Encryption**: All RESTRICTED fields stored in SQLite are encrypted with **AES-256-GCM**.
3. **Tokenized Identities**: Citizen primary identifiers are converted into SHA-256 hashes (`citizen_ref`), protecting privacy across logs and database tables.
4. **Immutable Audit Trail**: Append-only audit table logging every PII redaction, state transition, and admin action.

---

## 🧪 Running Pytest Test Suite

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_data_guard.py -v
python -m pytest tests/test_rules_engine.py -v
python -m pytest tests/test_fsm_order.py -v
python -m pytest tests/test_readiness_engine.py -v
```
