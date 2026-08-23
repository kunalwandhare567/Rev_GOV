# 🏛️ Multilingual Voice-First Revenue Services Platform
## Enterprise Backend — Setup & Run Guide

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+ (3.13 supported)
- No Docker required — uses SQLite

### 1. Setup Virtual Environment
```bash
cd "d:\AI Club Hackathon\revenue_platform"
python -m venv venv
venv\Scripts\activate       # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
copy .env.example .env
# Edit .env if needed (defaults work out of the box)
```

### 4. Run the Server
```bash
python main.py
# OR
uvicorn main:app --reload --port 8000
```

### 5. Access API
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **ReDoc**: http://localhost:8000/redoc

---

## 📡 Key API Endpoints

### Conversation (Main Chat)
```
POST /api/v1/conversation/message
```
```json
{
  "citizen_identifier": "test_user_001",
  "text": "I need an income certificate",
  "channel": "WEB",
  "language": "en"
}
```

### Document Upload
```
POST /api/v1/conversation/document-upload
```

### Channel Switch (Omnichannel)
```
POST /api/v1/conversation/channel-switch
```

### Application Status
```
GET /api/v1/applications/status/{application_number}
```

### Service Catalogue
```
GET /api/v1/applications/services
```

---

## 🛡️ Data Guard Demo
The trust boundary can be demonstrated live:

```bash
# This will be BLOCKED (applicant_name is PII)
curl -X POST http://localhost:8000/api/v1/data-guard/check \
  -H "Content-Type: application/json" \
  -d '{"payload": {"message": "translate", "applicant_name": "Ramesh Kumar"}}'

# This will be ALLOWED (no PII)
curl -X POST http://localhost:8000/api/v1/data-guard/check \
  -H "Content-Type: application/json" \
  -d '{"payload": {"message": "translate income certificate to Tamil"}}'
```

---

## 📊 Dashboard
```
GET /api/v1/dashboard/overview        # Full metrics
GET /api/v1/dashboard/audit-log       # Immutable audit trail
GET /api/v1/dashboard/data-guard-stats  # Data Guard activity
GET /api/v1/dashboard/service-health  # Component health
```

---

## 🧪 Running Tests
```bash
pytest tests/ -v
```

---

## 🏗️ Architecture

```
revenue_platform/
├── main.py                          # FastAPI entry point
├── .env                             # Config (no hardcoded values)
├── requirements.txt
├── app/
│   ├── core/
│   │   ├── config.py                # All settings from env
│   │   └── database.py              # SQLite engine
│   ├── models/
│   │   └── db_models.py             # 15 SQLAlchemy tables
│   ├── api/routes/
│   │   ├── conversation.py          # Chat + doc upload + channel switch
│   │   ├── applications.py          # Status, catalogue, officer actions
│   │   ├── dashboard.py             # Operational metrics
│   │   └── data_guard.py            # Live trust boundary demo
│   ├── orchestration/
│   │   ├── nlu/local_llm.py         # Ollama + keyword fallback NLU
│   │   └── state_machine/orchestrator.py  # Full 13-node state machine
│   ├── rules_engine/
│   │   ├── engine.py                # YAML spec loader + field validator + fee calc
│   │   └── fraud_scorer.py          # Behavioral anomaly scoring
│   ├── data_guard/
│   │   └── guard.py                 # OPA-lite PII enforcement
│   └── data_layer/
│       ├── encryption.py            # AES-256-GCM field encryption
│       └── repositories/            # Audit, citizen, application, session repos
├── seed/
│   └── service_specs/               # Declarative YAML service specs
│       ├── income_certificate.yaml
│       ├── caste_certificate.yaml
│       ├── obc_ncl_certificate.yaml
│       └── domicile_certificate.yaml
└── tests/
    ├── test_data_guard.py           # Adversarial PII tests
    ├── test_rules_engine.py         # Validation + eligibility + fee tests
    └── test_integration.py          # Full journey API tests
```

---

## ⚙️ Services Available (4 for POC)
| Service | ID | Fee | SLA |
|---|---|---|---|
| Income Certificate | `income_certificate` | ₹50 | 3 days |
| Caste Certificate | `caste_certificate` | ₹50 | 10 days |
| OBC-NCL Certificate | `obc_ncl_certificate` | ₹50 | 15 days |
| Domicile Certificate | `domicile_certificate` | ₹50 | 15 days |

Adding a new service = **add one YAML file** in `seed/service_specs/`. No code changes needed.

---

## 🌐 Supported Languages
`en` (English) · `hi` (Hindi) · `ta` (Tamil) · `te` (Telugu) · `mr` (Marathi)

---

## 🔒 Security Features
- **Data Guard**: All PII stays on-premise. Cloud calls are intercepted and blocked if PII detected.
- **Field Encryption**: AES-256-GCM for RESTRICTED data fields in SQLite
- **Tokenized Citizens**: `citizen_ref` is HMAC-SHA256 of raw identifier — cannot be reversed
- **Immutable Audit Log**: Append-only with chain-of-custody hashing
- **Fraud Scoring**: Behavioral anomaly detection on every submission

---

## 🧠 NLU Setup (Optional)
For local LLM support, install [Ollama](https://ollama.ai) and pull a model:
```bash
ollama pull phi3:mini
```
If Ollama is not available, the system automatically falls back to keyword-based NLU.
