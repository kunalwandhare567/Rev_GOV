import { useState, useEffect, useRef } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import useChatStore from '../store/chatStore'
import { RightPanelProvider, useRightPanel } from './RightPanelContext'
import styles from './CitizenDashboardLayout.module.css'

const CITIZEN_NAV = [
  { to: '/assistant',    icon: 'smart_toy',     label: 'Assistant'    },
  { to: '/applications', icon: 'assignment',    label: 'Applications' },
  { to: '/documents',    icon: 'folder_open',   label: 'Documents'    },
  { to: '/profile',      icon: 'person',        label: 'Profile'      },
]

const MOBILE_NAV = [
  { to: '/assistant',    icon: 'smart_toy',     label: 'Assistant'  },
  { to: '/applications', icon: 'assignment',    label: 'Apps'       },
  { to: '/documents',    icon: 'folder_open',   label: 'Docs'       },
  { to: '/profile',      icon: 'person',        label: 'Profile'    },
]

function initials(name) {
  if (!name) return 'C'
  return name.trim().split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

/* Inner shell that reads the right panel context */
function DashboardShell() {
  const location  = useLocation()
  const navigate  = useNavigate()
  const { isCitizenAuthenticated, citizenUser, clearCitizenAuth } = useAuthStore()
  const { panelContent, panelTitle } = useRightPanel()

  const [sidebarOpen,   setSidebarOpen]   = useState(false)
  const [rightOpen,     setRightOpen]     = useState(false)
  const [collapsed,     setCollapsed]     = useState(false)  // icon-only mode

  // Apply theme class
  useEffect(() => {
    document.body.className = 'citizen-theme'
    return () => { document.body.className = '' }
  }, [])

  // Close drawers on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false)
    setRightOpen(false)
  }, [location.pathname])

  const isActive = (to) =>
    to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)

  const handleLogout = () => {
    clearCitizenAuth()
    useChatStore.getState().reset()
    navigate('/')
  }

  return (
    <div className={`${styles.shell} ${collapsed ? styles.collapsed : ''}`}>

      {/* ══════ LEFT SIDEBAR ══════ */}
      {sidebarOpen && (
        <div className={styles.mobileOverlay} onClick={() => setSidebarOpen(false)} />
      )}

      <nav className={`${styles.sidebar} ${sidebarOpen ? styles.sidebarOpen : ''}`}>
        {/* Logo row */}
        <div className={styles.sidebarLogo}>
          <div className={styles.sidebarLogoIcon}>
            <span className="material-symbols-outlined">account_balance</span>
          </div>
          {!collapsed && (
            <div className={styles.sidebarBrandWrap}>
              <div className={styles.sidebarBrandName}>RevenueGov</div>
              <div className={styles.sidebarBrandTag}>Government Services</div>
            </div>
          )}
          {/* Collapse toggle — desktop only */}
          <button
            className={styles.collapseBtn}
            onClick={() => setCollapsed(v => !v)}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <span className="material-symbols-outlined">
              {collapsed ? 'chevron_right' : 'chevron_left'}
            </span>
          </button>
        </div>

        {/* New Application CTA */}
        <Link
          to="/assistant"
          className={`${styles.newAppBtn} ${collapsed ? styles.newAppBtnCollapsed : ''}`}
          title="New Application"
        >
          <span className="material-symbols-outlined">add</span>
          {!collapsed && <span>New Application</span>}
        </Link>

        {/* Nav links */}
        <ul className={styles.navList}>
          {CITIZEN_NAV.map(({ to, icon, label }) => (
            <li key={to}>
              <Link
                to={to}
                className={`${styles.navItem} ${isActive(to) ? styles.navActive : ''}`}
                title={label}
              >
                <span
                  className="material-symbols-outlined"
                  style={isActive(to) ? { fontVariationSettings: "'FILL' 1" } : {}}
                >
                  {icon}
                </span>
                {!collapsed && <span className={styles.navLabel}>{label}</span>}
              </Link>
            </li>
          ))}
        </ul>

        {/* Bottom profile */}
        {isCitizenAuthenticated && (
          <div className={styles.sidebarProfile}>
            {!collapsed ? (
              <>
                <div className={styles.profileRow} onClick={() => navigate('/profile')}>
                  <div className={styles.profileAvatar}>
                    {initials(citizenUser?.name || citizenUser?.citizen_id)}
                  </div>
                  <div className={styles.profileInfo}>
                    <div className={styles.profileName}>
                      {citizenUser?.name || 'Citizen Account'}
                    </div>
                    <div className={styles.profileId}>{citizenUser?.citizen_id}</div>
                  </div>
                  <span className={`material-symbols-outlined ${styles.profileChevron}`}>
                    chevron_right
                  </span>
                </div>
                <button className={styles.logoutBtn} onClick={handleLogout}>
                  <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>logout</span>
                  Sign Out
                </button>
              </>
            ) : (
              <button
                className={styles.profileAvatarSmall}
                onClick={() => navigate('/profile')}
                title={citizenUser?.name || 'Profile'}
              >
                {initials(citizenUser?.name || citizenUser?.citizen_id)}
              </button>
            )}
          </div>
        )}
      </nav>

      {/* ══════ MAIN CONTENT ══════ */}
      <div className={styles.contentWrap}>

        {/* Mobile top bar */}
        <header className={styles.mobileTopBar}>
          <button
            className={styles.mobileMenuBtn}
            onClick={() => setSidebarOpen(v => !v)}
            aria-label="Open menu"
          >
            <span className="material-symbols-outlined">menu</span>
          </button>
          <Link to="/" className={styles.mobileBrand}>RevenueGov</Link>
          <div className={styles.mobileTopActions}>
            {panelContent && (
              <button
                className={styles.mobileContextBtn}
                onClick={() => setRightOpen(v => !v)}
              >
                <span className="material-symbols-outlined">info</span>
              </button>
            )}
            {isCitizenAuthenticated && (
              <div
                className={styles.mobileAvatar}
                onClick={() => navigate('/profile')}
              >
                {initials(citizenUser?.name || citizenUser?.citizen_id)}
              </div>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className={styles.main}>
          <Outlet />
        </main>

        {/* Mobile bottom nav */}
        <nav className={styles.mobileBottomNav}>
          {MOBILE_NAV.map(({ to, icon, label }) => (
            <Link
              key={to}
              to={to}
              className={`${styles.mobileNavTab} ${isActive(to) ? styles.mobileNavActive : ''}`}
            >
              <span
                className="material-symbols-outlined"
                style={isActive(to) ? { fontVariationSettings: "'FILL' 1" } : {}}
              >
                {icon}
              </span>
              <span className={styles.mobileNavLabel}>{label}</span>
            </Link>
          ))}
        </nav>
      </div>

      {/* ══════ RIGHT PANEL (desktop / tablet drawer) ══════ */}
      {panelContent && (
        <>
          {/* Desktop right panel */}
          <aside className={styles.rightPanel}>
            {panelTitle && (
              <div className={styles.rightPanelHeader}>
                <span className={styles.rightPanelTitle}>{panelTitle}</span>
              </div>
            )}
            <div className={styles.rightPanelBody}>
              {panelContent}
            </div>
          </aside>

          {/* Context toggle button — visible on small laptop only */}
          <button
            className={styles.contextToggleBtn}
            onClick={() => setRightOpen(v => !v)}
            title="Show context panel"
          >
            <span className="material-symbols-outlined">
              {rightOpen ? 'close' : 'chevron_left'}
            </span>
          </button>

          {/* Tablet/mobile right drawer */}
          {rightOpen && (
            <>
              <div className={styles.mobileOverlay} onClick={() => setRightOpen(false)} />
              <div className={styles.rightDrawer}>
                <div className={styles.bottomSheetHandle} />
                {panelTitle && (
                  <div className={styles.rightPanelHeader}>
                    <span className={styles.rightPanelTitle}>{panelTitle}</span>
                    <button onClick={() => setRightOpen(false)} className={styles.closeBtn}>
                      <span className="material-symbols-outlined">close</span>
                    </button>
                  </div>
                )}
                {panelContent}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

export default function CitizenDashboardLayout() {
  return (
    <RightPanelProvider>
      <DashboardShell />
    </RightPanelProvider>
  )
}
