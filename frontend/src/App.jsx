import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

// ── LAYOUTS ──
import PublicLayout             from './layouts/PublicLayout'
import CitizenLayout            from './layouts/CitizenLayout'           // kept for legacy routes
import CitizenDashboardLayout   from './layouts/CitizenDashboardLayout'  // new 3-col dashboard
import RootLayout               from './layouts/RootLayout'
import AuthGuard                from './layouts/AuthGuard'

// ── PUBLIC PAGES ──
import LandingPage      from './pages/LandingPage/LandingPage'
import StatusTracker    from './pages/StatusTracker/StatusTracker'
import ServiceCatalogue from './pages/ServiceCatalogue/ServiceCatalogue'

// ── AUTH ──
import AuthPage from './pages/AuthPage/AuthPage'

// ── CITIZEN DASHBOARD PAGES (authenticated) ──
import CitizenChat           from './pages/CitizenChat/CitizenChat'
import ProfilePage           from './pages/CitizenDashboard/ProfilePage'
import MyApplicationsPage    from './pages/CitizenDashboard/MyApplicationsPage'
import ApplicationDetailsPage from './pages/CitizenDashboard/ApplicationDetailsPage'

// ── DOCUMENTS TAB ──
import DocumentsPage from './pages/CitizenDashboard/DocumentsPage'

// ── OMNICHANNEL (standalone, no layout) ──
import WhatsAppChat      from './pages/WhatsAppChat/WhatsAppChat'
import IVRSimulator      from './pages/IVRSimulator/IVRSimulator'
import ApplicationReview from './pages/ApplicationReview/ApplicationReview'

// ── ADMIN PORTAL ──
import AdminLogin        from './pages/AdminLogin/AdminLogin'
import AdminDashboard    from './pages/AdminDashboard/AdminDashboard'
import AdminApplications from './pages/AdminApplications/AdminApplications'
import DataGuardDemo     from './pages/DataGuardDemo/DataGuardDemo'
import AuditLog          from './pages/AuditLog/AuditLog'
import OfficerReview     from './pages/OfficerReview/OfficerReview'
import EscalationPanel   from './pages/EscalationPanel/EscalationPanel'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>

        {/* ══════════════════════════════════════════════════
            PUBLIC ROUTES — No sidebar, clean top nav
            ══════════════════════════════════════════════════ */}
        <Route element={<PublicLayout />}>
          <Route path="/"         element={<LandingPage />} />
          <Route path="/status"   element={<StatusTracker />} />
          <Route path="/services" element={<ServiceCatalogue />} />
        </Route>

        {/* ══════════════════════════════════════════════════
            AUTH PAGE — standalone, no layout wrapper
            ══════════════════════════════════════════════════ */}
        <Route path="/login" element={<AuthPage />} />

        {/* ══════════════════════════════════════════════════
            CITIZEN DASHBOARD — 3-column responsive layout
            All routes require CITIZEN auth
            ══════════════════════════════════════════════════ */}
        <Route
          element={
            <AuthGuard requiredRole="CITIZEN">
              <CitizenDashboardLayout />
            </AuthGuard>
          }
        >
          <Route path="/assistant"        element={<CitizenChat />} />
          <Route path="/chat"             element={<Navigate to="/assistant" replace />} />
          <Route path="/applications"     element={<MyApplicationsPage />} />
          <Route path="/applications/:id" element={<ApplicationDetailsPage />} />
          <Route path="/documents"        element={<DocumentsPage />} />
          <Route path="/profile"          element={<ProfilePage />} />
        </Route>

        {/* ══════════════════════════════════════════════════
            APPLICATION REVIEW / TRACKING — citizen layout
            ══════════════════════════════════════════════════ */}
        <Route element={<CitizenLayout />}>
          <Route path="/applications/:id/review" element={<ApplicationReview />} />
          <Route path="/tracking/:id"            element={<ApplicationReview />} />
        </Route>

        {/* ══════════════════════════════════════════════════
            STANDALONE CHANNEL UIs — no layout wrapper
            ══════════════════════════════════════════════════ */}
        <Route path="/whatsapp" element={<WhatsAppChat />} />
        <Route path="/ivr"      element={<IVRSimulator />} />

        {/* ══════════════════════════════════════════════════
            ADMIN PORTAL
            ══════════════════════════════════════════════════ */}
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route
          element={
            <AuthGuard requiredRole="ADMIN">
              <RootLayout />
            </AuthGuard>
          }
        >
          <Route path="/admin"                   element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="/admin/dashboard"         element={<AdminDashboard />} />
          <Route path="/admin/applications"      element={<AdminApplications />} />
          <Route path="/admin/review/:appNumber" element={<OfficerReview />} />
          <Route path="/admin/documents"         element={<DataGuardDemo />} />
          <Route path="/admin/data-guard"        element={<DataGuardDemo />} />
          <Route path="/admin/audit"             element={<AuditLog />} />
          <Route path="/admin/escalations"       element={<EscalationPanel />} />
          <Route path="/admin/live-events"       element={<AuditLog />} />
        </Route>

        {/* ══════════════════════════════════════════════════
            CATCH-ALL
            ══════════════════════════════════════════════════ */}
        <Route path="*" element={<Navigate to="/" replace />} />

      </Routes>
    </BrowserRouter>
  )
}
