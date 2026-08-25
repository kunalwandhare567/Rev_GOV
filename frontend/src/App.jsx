import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import CitizenLayout   from './layouts/CitizenLayout'
import RootLayout      from './layouts/RootLayout'
import AuthGuard       from './layouts/AuthGuard'

import LandingPage        from './pages/LandingPage/LandingPage'
import CitizenChat        from './pages/CitizenChat/CitizenChat'
import StatusTracker      from './pages/StatusTracker/StatusTracker'
import ServiceCatalogue   from './pages/ServiceCatalogue/ServiceCatalogue'

// ── CITIZEN DASHBOARD PAGES ──
import ProfilePage            from './pages/CitizenDashboard/ProfilePage'
import MyApplicationsPage     from './pages/CitizenDashboard/MyApplicationsPage'
import ApplicationDetailsPage  from './pages/CitizenDashboard/ApplicationDetailsPage'

// ── OMNICHANNEL PAGES ──
import WhatsAppChat       from './pages/WhatsAppChat/WhatsAppChat'
import IVRSimulator       from './pages/IVRSimulator/IVRSimulator'
import ApplicationReview  from './pages/ApplicationReview/ApplicationReview'

// ── ADMIN PORTAL ──
import AdminLogin      from './pages/AdminLogin/AdminLogin'
import AdminDashboard  from './pages/AdminDashboard/AdminDashboard'
import DataGuardDemo   from './pages/DataGuardDemo/DataGuardDemo'
import AuditLog        from './pages/AuditLog/AuditLog'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── CITIZEN PORTAL (PUBLIC) ── */}
        <Route element={<CitizenLayout />}>
          <Route path="/"         element={<LandingPage />} />
          <Route path="/status"   element={<StatusTracker />} />
          <Route path="/services" element={<ServiceCatalogue />} />
        </Route>

        {/* ── PROTECTED CITIZEN DASHBOARD ── */}
        <Route element={<AuthGuard requiredRole="CITIZEN"><CitizenLayout /></AuthGuard>}>
          <Route path="/assistant"       element={<CitizenChat />} />
          <Route path="/chat"            element={<CitizenChat />} />
          <Route path="/profile"         element={<ProfilePage />} />
          <Route path="/applications"    element={<MyApplicationsPage />} />
          <Route path="/applications/:id" element={<ApplicationDetailsPage />} />
        </Route>

        {/* ── STANDALONE CHANNEL UIs (no layout wrapper) ── */}
        <Route path="/whatsapp"  element={<WhatsAppChat />} />
        <Route path="/ivr"       element={<IVRSimulator />} />

        {/* ── APPLICATION REVIEW (citizen layout) ── */}
        <Route element={<CitizenLayout />}>
          <Route path="/applications/:id/review" element={<ApplicationReview />} />
          <Route path="/tracking/:id"            element={<ApplicationReview />} />
        </Route>

        {/* ── ADMIN PORTAL (ADMIN role only) ── */}
        <Route path="/admin/login" element={<AdminLogin />} />

        <Route element={<AuthGuard requiredRole="ADMIN"><RootLayout /></AuthGuard>}>
          <Route path="/admin"           element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
          <Route path="/admin/data-guard" element={<DataGuardDemo />} />
          <Route path="/admin/audit"     element={<AuditLog />} />
        </Route>

        {/* ── CATCH-ALL ── */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
