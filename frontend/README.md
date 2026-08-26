# 🏛️ Multilingual Citizen Revenue Services Platform — Frontend

[![React 19](https://img.shields.io/badge/React-19.2-61DAFB?style=flat&logo=react)](https://react.dev/)
[![Vite 6](https://img.shields.io/badge/Vite-6.4-646CFF?style=flat&logo=vite)](https://vitejs.dev/)
[![Zustand](https://img.shields.io/badge/Zustand-5.0-764ABC?style=flat)](https://zustand-demo.pmnd.rs/)
[![Lucide Icons](https://img.shields.io/badge/Lucide-1.33-FF6F61?style=flat)](https://lucide.dev/)

Modern, responsive, accessible web application for the **Multilingual AI-Powered Citizen Revenue Services Platform**. Built with **React 19**, **Vite 6**, **React Router DOM v7**, **Zustand**, and modern **CSS Modules** featuring glassmorphism design, dark mode accents, and high-contrast accessibility.

---

## 🌟 Key Frontend Features

1. **Citizen Voice & Text Chat (`/chat`)**:
   - Conversational AI assistant supporting 7 Indian languages with real-time slot filling progress bar.
   - Speech-to-Text (Web Speech API) and Text-to-Speech synthesis for voice-first interactions.
   - Interactive action cards, quick-reply chips, and side-panel inspection (Form slots, Uploaded docs, Readiness score).
2. **WhatsApp Web Simulator (`/whatsapp`)**:
   - Pixel-perfect clone of WhatsApp Web interface for testing omnichannel application flows.
   - Voice note player simulation, image/document attachment upload, interactive chip responses, and real-time message sync.
3. **IVR Voice Telephony Simulator (`/ivr`)**:
   - Interactive phone dialer with DTMF keypads, call timer, caller ID configuration, and real-time audio transcript generation.
4. **4-Section Web Application Review (`/applications/:id/review`)**:
   - Section 1: Basic & Application Details (Service type, Applicant name, DOB, Mobile, Address, Purpose).
   - Section 2: Personal & Family Details (Father/Mother name, Occupation, Annual Income, Family members).
   - Section 3: Documents & Validation (Document cards, OCR confidence scores, extracted vs declared discrepancy resolution).
   - Section 4: Final Review & Consent (Deterministic Readiness Score breakdown, Legal Consent Checkbox, Submit for Verification button).
5. **Admin & Officer Verification Portal (`/admin/dashboard`)**:
   - Real-time application review queue, OCR discrepancy viewer, document side-by-side verification, and one-click Approval / Clarification / Rejection actions.
6. **Data Guard Live Inspection (`/data-guard`)**:
   - Interactive demonstration showing real-time PII classification (Restricted vs Quasi-identifier vs Public) and Data Guard trust boundary firewall.
7. **Public Status Lookup (`/status`)**:
   - Instant public tracking by Application Number or Certificate Tracking ID without logging in.

---

## 📂 Frontend Directory Structure

```
frontend/
├── src/
│   ├── api/                           # Axios API Client Modules
│   │   ├── client.js                  # Axios instance with auth interceptors
│   │   ├── applications.js            # Application CRUD & review endpoints
│   │   ├── auth.js                    # Login & registration APIs
│   │   ├── conversation.js            # Chat session endpoints
│   │   ├── documents.js               # File upload & OCR resolution APIs
│   │   ├── ivr.js                     # IVR telephony endpoints
│   │   └── whatsapp.js                # WhatsApp simulator endpoints
│   ├── components/                    # Reusable UI Components
│   │   ├── AudioPlayer.jsx            # Voice message playback component
│   │   ├── DocumentUpload.jsx         # Drag-and-drop document uploader
│   │   ├── MismatchResolverModal.jsx  # Discrepancy resolution modal
│   │   ├── ReadinessGauge.jsx         # 0-100 Readiness Score visual gauge
│   │   ├── StatusBadge.jsx            # Application lifecycle status badge
│   │   └── TopNavigation.jsx          # Primary application header
│   ├── layouts/                       # Page Layout Components
│   │   ├── AuthGuard.jsx              # Protected route guard
│   │   ├── CitizenDashboardLayout.jsx # Authenticated citizen layout
│   │   ├── PublicLayout.jsx           # Public portal layout
│   │   └── RootLayout.jsx             # Master application root
│   ├── pages/                         # Application Pages
│   │   ├── AdminDashboard/            # Admin review queue & metrics
│   │   ├── ApplicationDetails/        # Application details view
│   │   ├── ApplicationReview/         # 4-Section Web Review & Consent
│   │   ├── Auth/                      # Citizen login & registration
│   │   ├── CitizenChat/               # Conversational AI web chat
│   │   ├── DataGuardDemo/             # Live PII firewall inspection
│   │   ├── IVRSimulator/              # IVR phone telephony simulator
│   │   ├── LandingPage/               # Public home & hero banner
│   │   ├── MyApplications/            # Citizen active application list
│   │   ├── OfficerReview/             # Deep officer application inspection
│   │   ├── ServiceCatalogue/          # Service requirement cards
│   │   ├── StatusTracker/             # Public tracking lookup
│   │   └── WhatsAppChat/              # WhatsApp Web simulator page
│   ├── store/                         # Zustand State Stores
│   │   ├── authStore.js               # Citizen & Admin JWT auth store
│   │   ├── chatStore.js               # Active chat session & messages store
│   │   └── uiStore.js                 # Theme, language & drawer UI store
│   ├── styles/                        # CSS Modules & Global Styles
│   │   ├── globals.css                # Global CSS resets & design tokens
│   │   └── *.module.css               # Component & page specific stylesheets
│   ├── App.jsx                        # React Router configuration
│   └── main.jsx                       # React DOM root entrypoint
├── package.json                       # Scripts & Dependencies
└── vite.config.js                     # Vite Bundler Settings
```

---

## ⚡ Setup & Development

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Run Development Server
```bash
npm run dev
```
*(Runs Vite development server on `http://localhost:5173` with HMR)*

### 3. Build for Production
```bash
npm run build
```
*(Compiles optimized static bundle into `dist/` directory)*

### 4. Preview Production Build
```bash
npm run preview
```

---

## 🛠️ Key Dependencies

- **Framework**: `react` (v19.2), `react-dom` (v19.2)
- **Build Tool**: `vite` (v6.4)
- **Routing**: `react-router-dom` (v7.18)
- **State Management**: `zustand` (v5.0)
- **HTTP Client**: `axios` (v1.19)
- **Icons & Visuals**: `lucide-react` (v1.33), `recharts` (v3.10)
- **Notifications**: `react-hot-toast` (v2.6)
- **Markdown Rendering**: `react-markdown` (v10.1)
- **Drag & Drop Upload**: `react-dropzone` (v20.1)
- **Animations**: `framer-motion` (v13.1)
