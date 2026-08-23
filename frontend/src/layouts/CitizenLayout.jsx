import { Outlet, Link, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import useChatStore from '../store/chatStore'
import { t } from '../i18n'
import styles from './CitizenLayout.module.css'

export default function CitizenLayout() {
  const language = useChatStore((s) => s.language)
  const location = useLocation()

  useEffect(() => {
    document.body.className = 'citizen-theme'
    return () => { document.body.className = '' }
  }, [])

  const navLinks = [
    { to: '/',         label: t(language, 'nav.home') },
    { to: '/services', label: t(language, 'nav.services') },
    { to: '/status',   label: t(language, 'nav.trackApplication') },
  ]

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Link to="/" className={styles.logo}>
          <span className={styles.logoIcon}>🏛️</span>
          <span className={styles.logoText}>RevenueSeva</span>
        </Link>
        <nav className={styles.nav}>
          {navLinks.map(({ to, label }) => (
            <Link key={to} to={to} className={`${styles.navLink} ${location.pathname === to ? styles.active : ''}`}>
              {label}
            </Link>
          ))}
        </nav>
        <div className={styles.headerActions}>
          <Link to="/chat" className={styles.ctaBtn}>{t(language, 'nav.applyNow')}</Link>
          <Link to="/admin/login" className={styles.adminLink}>{t(language, 'nav.adminPortal')}</Link>
        </div>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
