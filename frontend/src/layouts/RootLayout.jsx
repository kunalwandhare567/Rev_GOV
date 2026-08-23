import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { LayoutDashboard, Shield, ScrollText, AlertTriangle, FileSearch, LogOut, ExternalLink, Menu } from 'lucide-react'
import toast from 'react-hot-toast'
import useAuthStore from '../store/authStore'
import useUIStore from '../store/uiStore'
import { logout } from '../api/auth'
import styles from './RootLayout.module.css'

const NAV_ITEMS = [
  { to: '/admin/dashboard',   icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/admin/data-guard',  icon: Shield,          label: 'Data Guard' },
  { to: '/admin/audit',       icon: ScrollText,      label: 'Audit Log' },
  { to: '/admin/escalations', icon: AlertTriangle,   label: 'Escalations' },
]

export default function RootLayout() {
  const { user, clearAuth } = useAuthStore()
  const { sidebarOpen, toggleSidebar } = useUIStore()
  const navigate = useNavigate()

  useEffect(() => {
    document.body.className = 'admin-theme'
    return () => { document.body.className = '' }
  }, [])

  useEffect(() => {
    const handler = () => {
      clearAuth()
      toast.error('Session expired. Please login again.')
      navigate('/admin/login')
    }
    window.addEventListener('auth:expired', handler)
    return () => window.removeEventListener('auth:expired', handler)
  }, [clearAuth, navigate])

  const handleLogout = async () => {
    try { await logout() } catch (_) {}
    clearAuth()
    toast.success('Logged out successfully')
    navigate('/admin/login')
  }

  return (
    <div className={styles.shell}>
      <aside className={`${styles.sidebar} ${sidebarOpen ? styles.open : styles.collapsed}`}>
        <div className={styles.sidebarHeader}>
          <span className={styles.logoIcon}>🏛️</span>
          {sidebarOpen && <span className={styles.logoText}>RevenueSeva</span>}
        </div>
        <nav className={styles.nav}>
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}>
              <Icon size={18} className={styles.navIcon} />
              {sidebarOpen && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>
        <div className={styles.sidebarFooter}>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className={styles.navItem}>
            <ExternalLink size={18} className={styles.navIcon} />
            {sidebarOpen && <span>API Docs</span>}
          </a>
          <button className={styles.navItem} onClick={handleLogout}>
            <LogOut size={18} className={styles.navIcon} />
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </aside>
      <div className={styles.main}>
        <header className={styles.topbar}>
          <button className={styles.menuBtn} onClick={toggleSidebar} aria-label="Toggle sidebar"><Menu size={20} /></button>
          <div className={styles.topbarRight}>
            <span className={styles.userRole}>{user?.role}</span>
            <span className={styles.userName}>{user?.username}</span>
            <span className={styles.liveIndicator}><span className={styles.liveDot} />LIVE</span>
          </div>
        </header>
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
