import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import CitizenLayout   from './layouts/CitizenLayout'
import RootLayout      from './layouts/RootLayout'
import AuthGuard       from './layouts/AuthGuard'

import LandingPage        from './pages/LandingPage/LandingPage'
import CitizenChat        from './pages/CitizenChat/CitizenChat'
import StatusTracker      from './pages/StatusTracker/StatusTracker'
import ServiceCatalogue   from './pages/ServiceCatalogue/ServiceCatalogue'

// ── NEW OMNICHANNEL PAGES ──
import WhatsAppChat       from './pages/WhatsAppChat/WhatsAppChat'
import IVRSimulator       from './pages/IVRSimulator/IVRSimulator'
import ApplicationReview  from './pages/ApplicationReview/ApplicationReview'

import AdminLogin      from './pages/AdminLogin/AdminLogin'
import OfficerLogin    from './pages/OfficerLogin/OfficerLogin'
import AdminDashboard  from './pages/AdminDashboard/AdminDashboard'
import DataGuardDemo   from './pages/DataGuardDemo/DataGuardDemo'
import AuditLog        from './pages/AuditLog/AuditLog'
import OfficerReview   from './pages/OfficerReview/OfficerReview'
import EscalationPanel from './pages/EscalationPanel/EscalationPanel'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── CITIZEN PORTAL (with layout) ── */}
        <Route element={<CitizenLayout />}>
          <Route path="/"         element={<LandingPage />} />
          <Route path="/chat"     element={<CitizenChat />} />
          <Route path="/status"   element={<StatusTracker />} />
          <Route path="/services" element={<ServiceCatalogue />} />
        </Route>

        {/* ── STANDALONE CHANNEL UIs (no layout wrapper) ── */}
        <Route path="/whatsapp"  element={<WhatsAppChat />} />
        <Route path="/ivr"       element={<IVRSimulator />} />

        {/* ── APPLICATION REVIEW (with citizen layout) ── */}
        <Route element={<CitizenLayout />}>
          <Route path="/applications/:id/review" element={<ApplicationReview />} />
          <Route path="/tracking/:id"            element={<ApplicationReview />} />
        </Route>

        {/* ── ADMIN / OFFICER PORTALS ── */}
        <Route path="/admin/login"   element={<AdminLogin />} />
        <Route path="/officer/login" element={<OfficerLogin />} />

        <Route element={<AuthGuard requiredRole="ADMIN"><RootLayout /></AuthGuard>}>
          <Route path="/admin"                    element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="/admin/dashboard"          element={<AdminDashboard />} />
          <Route path="/admin/data-guard"         element={<DataGuardDemo />} />
          <Route path="/admin/audit"              element={<AuditLog />} />
          <Route path="/admin/escalations"        element={<EscalationPanel />} />
        </Route>

        <Route element={<AuthGuard requiredRole="OFFICER"><RootLayout /></AuthGuard>}>
          <Route path="/officer"                        element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="/admin/review/:appNumber"        element={<OfficerReview />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
