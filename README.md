# 🏛️ Multilingual AI-Powered Citizen Revenue Services Platform (`Rev_Gov_Platform`)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19.2-61DAFB?style=flat&logo=react)](https://react.dev/)
[![Vite 6](https://img.shields.io/badge/Vite-6.4-646CFF?style=flat&logo=vite)](https://vitejs.dev/)
[![SQLite WAL](https://img.shields.io/badge/SQLite-WAL_Mode-003B57?style=flat&logo=sqlite)](https://www.sqlite.org/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, omnichannel, voice-first AI platform designed to deliver statutory revenue certificate services for citizens across India in 7 regional languages (**English, Hindi, Marathi, Tamil, Telugu, Bengali, Gujarati**).

---

## 🌟 Executive Summary & Key Highlights

The **Multilingual AI-Powered Citizen Revenue Services Platform** bridges the digital divide by allowing citizens to apply for statutory government certificates through natural-language conversation across multiple channels (**Web Portal, WhatsApp Web Simulator, IVR Voice Telephony Simulator, Mobile Responsive UI**).

### 🚀 Key Innovations
1. **Single Source of Truth**: Unified database application record (`tracking_id`) synchronized seamlessly across all channels (Web, WhatsApp, IVR).
2. **Deterministic Governance vs. Probabilistic LLM**:
   - **LLM**: Language understanding, dynamic question generation, cross-question explanations, and conversational assistance via **Gemini 1.5 Flash**, **Groq**, or **OpenRouter**.
   - **Deterministic Engines**: Eligibility, document OCR matching scores, 0–100 application readiness scores, fee calculation, waivers, and FSM lifecycle transitions are strictly governed by Python engines and YAML specifications.
3. **Data Guard & PII Trust Boundary**: Real-time PII classifier and firewall that blocks sensitive citizen details (Aadhaar, PAN, names, phone numbers) from reaching external cloud LLMs.
4. **Governed Lifecycle FSM (Post-Approval Payment)**: Payment is strictly enabled **after** back-office verification and approval, followed by automatic digital certificate generation.
5. **Dynamic OCR & Discrepancy Resolution**: Local Tesseract OCR + PyMuPDF regex pattern extraction for identity proof, income proof, and caste certificates with interactive discrepancy resolution.

---

## 📂 Repository Structure

```
Revenue_Gov_platform/
├── backend/                             # Python FastAPI Enterprise Backend Service
│   ├── app/
│   │   ├── api/routes/                  # REST API & SSE Event Endpoints
│   │   ├── channels/                    # Channel adapters (Web, WhatsApp, IVR, Mobile)
│   │   ├── core/                        # Settings, Database Engine, Events, Security
│   │   ├── data_guard/                  # PII Classifier & Firewall Middleware
│   │   ├── data_layer/                  # Repositories & AES-256-GCM Field Encryption
│   │   ├── llm/                         # Provider abstraction (Gemini, Groq, OpenRouter)
│   │   ├── models/                      # SQLAlchemy Database Schema Models (15 tables)
│   │   ├── orchestration/               # NLU, Dynamic Intent, Field Corrector & Application Orchestrator
│   │   ├── rules_engine/                # Service Spec Loader, Field Validator, Eligibility & Fraud Scorer
│   │   └── services/                    # Tesseract OCR, Matching Engine, Readiness Engine, RAG & Payments
│   ├── knowledge/                       # Policy Knowledge Base Markdown files (Income, Caste, Domicile, OBC)
│   ├── seed/service_specs/              # Authoritative YAML Service Specifications
│   ├── tests/                           # 17 Pytest Test Suites (180+ test cases)
│   ├── main.py                          # FastAPI Application Entrypoint
│   └── requirements.txt                 # Backend Dependencies
├── frontend/                            # React 19 + Vite 6 Modern Web Frontend
│   ├── src/
│   │   ├── api/                         # Axios API Clients & Service Endpoints
│   │   ├── components/                  # UI Components (AudioPlayer, DocumentUpload, StatusBadge)
│   │   ├── layouts/                     # PublicLayout, CitizenDashboardLayout, RootLayout
│   │   ├── pages/                       # 16 Specialized Pages (CitizenChat, WhatsAppChat, IVR, Admin, etc.)
│   │   ├── store/                       # Zustand Stores (authStore, chatStore, uiStore)
│   │   └── styles/                      # Glassmorphism & High-Contrast Design System
│   ├── package.json                     # Frontend Dependencies & Scripts
│   └── vite.config.js                   # Vite Bundler Configuration
├── requirements.txt                     # Root Python Requirements (refers to backend)
├── run_backend.bat                      # One-click Windows script to start FastAPI backend (Port 8000)
├── run_frontend.bat                     # One-click Windows script to start Vite dev server (Port 5173)
└── PROJECT_ANALYSIS_AND_PIPELINE_DOCUMENTATION.md # Detailed Architectural Documentation
```

---

## 📜 Statutory Services Supported (POC Scope)

| Service Name | Service ID | Fee | Default SLA | Key Required Documents |
| :--- | :--- | :---: | :---: | :--- |
| **Income Certificate** | `income_certificate` | ₹50 *(Waiver if income ≤ ₹20k / BPL)* | 3 Days | Aadhaar Card, Salary Slip / Income Certificate |
| **Caste Certificate** | `caste_certificate` | ₹50 | 10 Days | Aadhaar Card, Caste Affidavit / Family Record |
| **Domicile Certificate** | `domicile_certificate` | ₹50 | 15 Days | Aadhaar Card, Residence Proof (Electricity Bill) |
| **OBC Non-Creamy Layer (NCL)** | `obc_ncl_certificate` | ₹50 | 15 Days | Aadhaar Card, Income Proof, Caste Certificate |

*Adding a new revenue service requires adding only **one declarative YAML spec** under `backend/seed/service_specs/` without touching code.*

---

## 🛠️ Prerequisites & Installation

### Core Prerequisites
- **Python**: Version 3.10 or higher (Python 3.13 / 3.14 fully supported)
- **Node.js**: Version 18.0 or higher (Node 22 recommended)
- **OCR Engine (Optional)**: [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (Auto-detected if installed at `C:\Program Files\Tesseract-OCR\tesseract.exe` or system PATH; fallback simulated OCR operates out-of-the-box).

---

## ⚡ Quick Start Guide

### Option A: Using Windows Batch Scripts (Recommended)

1. **Start Backend Server**:
   Double click `run_backend.bat` or run:
   ```cmd
   run_backend.bat
   ```
   *(Launches FastAPI backend on `http://localhost:8000`)*

2. **Start Frontend Dev Server**:
   Double click `run_frontend.bat` or run:
   ```cmd
   run_frontend.bat
   ```
   *(Launches React frontend on `http://localhost:5173`)*

---

### Option B: Manual Setup

#### 1. Backend Setup (`backend/`)
```bash
# Navigate to backend directory
cd backend

# Create & activate virtual environment (optional)
python -m venv venv
venv\Scripts\activate      # On Windows
# source venv/bin/activate  # On Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Create environment file from template
copy .env.example .env     # On Windows
# cp .env.example .env      # On Linux/macOS

# Start FastAPI server
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

#### 2. Frontend Setup (`frontend/`)
```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

---

## ⚙️ Environment Configuration (`backend/.env`)

Configure your preferred Cloud LLM provider in `backend/.env`:

```env
# System Configuration
APP_NAME="Multilingual AI-Powered Citizen Revenue Services Platform"
APP_VERSION="3.0.0"
DEBUG=true
SECRET_KEY="revenue-services-dev-secret-key-change-in-production"
DATABASE_URL="sqlite:///./revenue_services.db"

# Select ONE active provider: gemini | groq | openrouter
LLM_PROVIDER="gemini"

# Provider API Keys
GEMINI_API_KEY="your-gemini-api-key"
GEMINI_MODEL="gemini-1.5-flash"

GROQ_API_KEY="your-groq-api-key"
GROQ_MODEL="llama3-8b-8192"

OPENROUTER_API_KEY="your-openrouter-api-key"
OPENROUTER_MODEL="meta-llama/llama-3.1-8b-instruct:free"

# Storage Directories
STORAGE_PATH="./data/uploads"
RECEIPT_PATH="./data/receipts"
CERTIFICATE_PATH="./data/certificates"
AUDIO_PATH="./data/audio"
```

---

## 🌐 Application URLs & Endpoints

| Portal / Feature | URL | Description |
| :--- | :--- | :--- |
| **Citizen Web Portal** | `http://localhost:5173` | Landing page, Service Catalogue, Status Lookup |
| **Citizen Voice & Chat** | `http://localhost:5173/chat` | Multilingual conversational application UI |
| **WhatsApp Simulator** | `http://localhost:5173/whatsapp` | Pixel-perfect WhatsApp Web clone interface |
| **IVR Telephony Simulator** | `http://localhost:5173/ivr` | Voice synthesis & interactive DTMF keypad dialer |
| **4-Section Review Page** | `http://localhost:5173/applications/:id/review` | Section-by-section review & legal consent |
| **Admin & Officer Portal** | `http://localhost:5173/admin/login` | Application review queue & approval actions (*User: `admin` / Pass: `Admin@123`*) |
| **Data Guard Demo** | `http://localhost:5173/data-guard` | Live PII classification and trust boundary tester |
| **Backend API Swagger Docs**| `http://localhost:8000/docs` | Interactive OpenAPI / Swagger documentation |
| **Backend Health Check** | `http://localhost:8000/health` | Backend status & DB connection check |

---

## 🔄 End-to-End Golden Flow Lifecycle

```
[Citizen Input (Web / WhatsApp / IVR)]
                 │
                 ▼
[Data Guard PII Filter] ──(Redacts PII)──► [Cloud LLM (Gemini/Groq/OpenRouter)]
                 │
                 ▼
[NextQuestionEngine] ──(Dynamic Slot Sequencing)──► [Extracts Slots]
                 │
                 ▼
[Document Upload & OCR Engine] ──► [Matching Engine (Match Score %)]
                 │
                 ▼
[Readiness Engine] ──(Score ≥ 75/100)──► [4-Section Web Review & Consent]
                 │
                 ▼
[Submit for Verification] ──► [Admin / Officer Review Queue]
                 │
                 ▼
[Officer Approve] ──► [Payment Required (₹50 Fee)]
                 │
                 ▼
[Citizen Payment / OCR Receipt Verification] ──► [Certificate Issued (PDF + Tracking ID)]
```

---

## 🧪 Running Automated Test Suites

The backend comes with **17 test suites** covering unit, integration, security, and E2E scenarios.

```bash
cd backend

# Run all pytest suites
python -m pytest tests/ -v

# Run specific test module (e.g. Data Guard trust boundary)
python -m pytest tests/test_data_guard.py -v

# Run with test coverage report
python -m pytest --cov=app tests/
```

---

## 🛡️ Security & Privacy Architecture

- **AES-256-GCM Encryption**: Restricted citizen fields (Aadhaar, PAN, Name, DOB, Address) are encrypted before writing to SQLite.
- **HMAC-SHA256 Tokenization**: Citizen identifiers (phone numbers, email addresses) are hashed with salt for privacy preservation across sessions.
- **Data Guard Trust Boundary**: Outbound cloud payloads are scanned and redacted so raw PII never leaves the boundary.
- **Immutable Audit Trail**: Append-only log table recording all system operations with chain-of-custody metadata.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
