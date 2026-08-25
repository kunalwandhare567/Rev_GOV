import { useState, useEffect } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import useChatStore from '../store/chatStore'
import CitizenAuthModal from '../components/CitizenAuth/CitizenAuthModal'
import styles from './CitizenLayout.module.css'

const NAV_ITEMS = [
  { to: '/assistant', icon: 'smart_toy',          label: 'Assistant' },
  { to: '/applications', icon: 'assignment',       label: 'Applications' },
  { to: '/services',     icon: 'verified',         label: 'Certificates' },
  { to: '/status',       icon: 'history',          label: 'Recent' },
]

const NAV_ITEMS_AUTH = [
  { to: '/assistant',    icon: 'smart_toy',         label: 'Assistant' },
  { to: '/applications', icon: 'assignment',        label: 'Applications' },
  { to: '/profile',      icon: 'person',            label: 'Profile' },
  { to: '/services',     icon: 'verified',          label: 'Certificates' },
  { to: '/status',       icon: 'history',           label: 'Track Status' },
]

const MOBILE_NAV = [
  { to: '/assistant',    icon: 'smart_toy',  label: 'Assistant' },
  { to: '/applications', icon: 'assignment', label: 'Apps' },
  { to: '/services',     icon: 'verified',   label: 'Services' },
  { to: '/status',       icon: 'history',    label: 'Track' },
]

function initials(name) {
  if (!name) return 'C'
  return name.trim().split(' ').map(w => w[0]).join('').slice(0,2).toUpperCase()
}

export default function CitizenLayout() {
  const location  = useLocation()
  const navigate  = useNavigate()
  const language  = useChatStore((s) => s.language)

  const { isCitizenAuthenticated, citizenUser, clearCitizenAuth } = useAuthStore()
  const [authModalOpen, setAuthModalOpen]   = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    document.body.className = 'citizen-theme'
    return () => { document.body.className = '' }
  }, [])

  const navLinks = isCitizenAuthenticated ? NAV_ITEMS_AUTH : NAV_ITEMS

  const isActive = (to) =>
    to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)

  const handleLogout = () => {
    clearCitizenAuth()
    useChatStore.getState().reset()
    navigate('/')
  }

  return (
    <div className={styles.shell}>

      {/* ═══ LEFT SIDEBAR ═══ */}
      <nav className={styles.sidebar}>

        {/* Logo */}
        <div className={styles.sidebarLogo}>
          <div className={styles.sidebarLogoIcon}>
            <span className="material-symbols-outlined">account_balance</span>
          </div>
          <div>
            <div className={styles.sidebarBrandName}>RevenueGov</div>
            <div className={styles.sidebarBrandTagline}>Government Services, Simplified</div>
          </div>
        </div>

        {/* New Application CTA */}
        <Link to="/assistant" className={styles.newAppBtn}>
          <span className="material-symbols-outlined">add</span>
          New Application
        </Link>

        {/* Navigation links */}
        <ul className={styles.navList}>
          {navLinks.map(({ to, icon, label }) => (
            <li key={to}>
              <Link
                to={to}
                className={`${styles.navItem} ${isActive(to) ? styles.active : ''}`}
              >
                <span
                  className="material-symbols-outlined"
                  style={isActive(to) ? { fontVariationSettings: "'FILL' 1" } : {}}
                >
                  {icon}
                </span>
                {label}
              </Link>
            </li>
          ))}

          {/* Separator items */}
          <li style={{ marginTop: '0.5rem' }}>
            <Link
              to="/status"
              className={`${styles.navItem} ${isActive('/status') && location.pathname === '/status' ? styles.active : ''}`}
              style={{ display: isActive('/status') && navLinks.find(n => n.to === '/status') ? 'none' : undefined }}
            >
              <span className="material-symbols-outlined">notifications_active</span>
              Notifications
            </Link>
          </li>

          <li>
            <Link to="/admin/login" className={styles.navItem}>
              <span className="material-symbols-outlined">settings</span>
              Admin Portal
            </Link>
          </li>
        </ul>

        {/* Profile / Auth section at bottom */}
        <div className={styles.sidebarProfile}>
          {isCitizenAuthenticated ? (
            <>
              <div className={styles.profileRow} onClick={() => navigate('/profile')}>
                <div className={styles.profileAvatar}>
                  {initials(citizenUser?.name || citizenUser?.citizen_id)}
                </div>
                <div>
                  <div className={styles.profileName}>
                    {citizenUser?.name || 'Citizen Account'}
                  </div>
                  <div className={styles.profileId}>
                    {citizenUser?.citizen_id}
                  </div>
                </div>
                <div className={styles.profileChevron}>
                  <span className="material-symbols-outlined">chevron_right</span>
                </div>
              </div>
              <button className={styles.logoutBtnSidebar} onClick={handleLogout}>
                <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>logout</span>
                Sign Out
              </button>
            </>
          ) : (
            <button
              className={styles.loginBtnSidebar}
              onClick={() => setAuthModalOpen(true)}
            >
              <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>login</span>
              Login / Register
            </button>
          )}
        </div>
      </nav>

      {/* ═══ RIGHT: CONTENT AREA ═══ */}
      <div className={styles.contentWrap}>

        {/* Mobile top bar */}
        <header className={styles.mobileHeader}>
          <span className={styles.mobileLogo}>RevenueGov</span>
          <div className={styles.mobileActions}>
            <button className={styles.mobileIconBtn}>
              <span className="material-symbols-outlined">notifications</span>
            </button>
            <button
              className={styles.mobileIconBtn}
              onClick={() => setMobileMenuOpen(v => !v)}
            >
              <span className="material-symbols-outlined">menu</span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className={styles.main}>
          <Outlet />
        </main>

        {/* Mobile bottom navigation */}
        <nav className={styles.mobileBottomNav}>
          {MOBILE_NAV.map(({ to, icon, label }) => (
            <Link
              key={to}
              to={to}
              className={`${styles.mobileNavTab} ${isActive(to) ? styles.active : ''}`}
            >
              <span
                className="material-symbols-outlined"
                style={isActive(to) ? { fontVariationSettings: "'FILL' 1" } : {}}
              >
                {icon}
              </span>
              {label}
            </Link>
          ))}
        </nav>
      </div>

      {/* Auth Modal */}
      <CitizenAuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={() => {
          setAuthModalOpen(false)
          navigate('/assistant')
        }}
      />
    </div>
  )
}
