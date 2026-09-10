# Implementation Plan — TCS Hackathon Round 2 Winning Features

This implementation plan outlines the key frontend and backend enhancements designed to make the **Multilingual AI-Powered Citizen Revenue Services Platform** a standout, winning solution for Round 2 of the TCS Hackathon.

## Goal
Equip the platform with:
2. **Omnichannel Command Center (`/demo`)** showing Web, WhatsApp, and IVR synced in real time side-by-side.
3. **Official Digital Certificate Modal** with dynamic QR code verification.
4. **Voice AI Waveform & Native Regional TTS Reader** for voice-first accessibility.
5. **Data Guard Redaction Visualizer** demonstrating DPDP Act 2023 compliance to judges.

---

## User Review Required

> [!IMPORTANT]
> - **Demo Mode Floating Bar**: A floating button will be added to the bottom-right corner of the application UI across all routes. It can be collapsed or expanded during the hackathon presentation.
> - **New Split-Screen Route (`/demo`)**: A dedicated route will be added to display Web, WhatsApp, and IVR in a unified 3-column view for live evaluator demos.

---

## Open Questions

> [!NOTE]
> All key architectural decisions are aligned with current project conventions. No open questions require user input before proceeding.

---

## Proposed Changes

### Frontend Components & Pages

#### [NEW] [HackathonPitchBar.jsx](file:///c:/Users/lenovo/projects/Rev_GOV/frontend/src/components/HackathonPitchBar/HackathonPitchBar.jsx)
- Floating widget rendered across all pages in [RootLayout.jsx](file:///c:/Users/lenovo/projects/Rev_GOV/frontend/src/layouts/RootLayout.jsx) / [PublicLayout.jsx](file:///c:/Users/lenovo/projects/Rev_GOV/frontend/src/layouts/PublicLayout.jsx).
- Provides 1-click pitch controls:
  - **Auto-Fill Application**: Pre-populates an Income Certificate application with sample citizen data (*Rajesh Sharma*, ₹48,000 income).
  - **Trigger Mismatch**: Simulates uploading an Aadhaar card where the OCR extracted name differs from declared name.
  - **Inspect Data Guard**: Opens the live PII redaction firewall inspection modal.
  - **Open Omnichannel Demo**: Navigates to `/demo` pre-loaded with active application number.

#### [NEW] [OmnichannelDemo.jsx](file:///c:/Users/lenovo/projects/Rev_GOV/frontend/src/pages/OmnichannelDemo/OmnichannelDemo.jsx)
- 3-column split-screen layout displaying:
  - **Panel 1**: Citizen Web Chat view.
  - **Panel 2**: WhatsApp Web Simulator view.
  - **Panel 3**: IVR Voice Call Simulator view.
- Real-time synchronization powered by Server-Sent Events (SSE) and shared Zustand state.

#### [NEW] [DigitalCertificateModal.jsx](file:///c:/Users/lenovo/projects/Rev_GOV/frontend/src/components/DigitalCertificateModal/DigitalCertificateModal.jsx)
- Rendered when an application reaches `COMPLETED` or `PAYMENT_COMPLETED` state.
- Features State Revenue Department watermark, seal, dynamic QR code verification link, digital signature, and PDF/Print export.

#### [NEW] [VoiceWaveform.jsx](file:///c:/Users/lenovo/projects/Rev_GOV/frontend/src/components/VoiceWaveform/VoiceWaveform.jsx)
- Animated canvas/CSS audio visualizer waveform displayed in [CitizenChat.jsx](file:///c:/Users/lenovo/projects/Rev_GOV/frontend/src/pages/CitizenChat/CitizenChat.jsx) when STT microphone is actively listening.

#### [MODIFY] [CitizenChat.jsx](file:///c:/Users/lenovo/projects/Rev_GOV/frontend/src/pages/CitizenChat/CitizenChat.jsx)
- Integrate `VoiceWaveform` into input bar.
- Add "🔊 Listen in Native Language" TTS audio playback buttons on assistant message bubbles.
- Attach `DigitalCertificateModal` trigger upon completion.

#### [MODIFY] [App.jsx](file:///c:/Users/lenovo/projects/Rev_GOV/frontend/src/App.jsx)
- Add `/demo` route pointing to `OmnichannelDemo.jsx`.
- Mount `<HackathonPitchBar />` across main layouts.

---

### Backend API Services

#### [NEW] [demo.py](file:///c:/Users/lenovo/projects/Rev_GOV/backend/app/api/routes/demo.py)
- `POST /api/v1/demo/quick-seed`: Creates a fully-formed sample application record in SQLite with mock document OCR data and optional mismatch flags.
- `GET /api/v1/demo/certificate/{app_number}`: Returns certificate JSON + base64 QR code image string.

#### [MODIFY] [main.py](file:///c:/Users/lenovo/projects/Rev_GOV/backend/main.py)
- Register `demo.py` router under `/api/v1/demo`.

---

## Verification Plan

### Automated Tests
- Run backend pytest suite:
  ```powershell
  python -m pytest
  ```
- Run frontend build verification:
  ```powershell
  cd frontend
  npm run build
  ```

### Manual Verification
1. Open `http://localhost:5173/` and test the floating **⚡ Hackathon Pitch Bar**.
2. Click **Auto-Fill Application** and verify chat pre-fills without manual typing.
3. Open `http://localhost:5173/demo` and test real-time split-screen sync across Web, WhatsApp, and IVR.
4. Verify the **Digital Certificate Modal** displays with QR code upon payment completion.
5. Verify the **Voice AI Waveform** animates while speaking into the mic.
