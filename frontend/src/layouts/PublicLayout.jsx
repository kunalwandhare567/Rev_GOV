import { useState } from 'react'
import { Outlet, Link, useNavigate } from 'react-router-dom'
import useChatStore from '../store/chatStore'
import useAuthStore from '../store/authStore'
import styles from './PublicLayout.module.css'

const LANGUAGE_NAMES_LOCAL = { en: 'English', hi: 'हिंदी', mr: 'मराठी' }
const SUPPORTED_LANGS = ['en', 'hi', 'mr']


export default function PublicLayout() {
  const navigate  = useNavigate()
  const { language, setLanguage } = useChatStore()
  const { isCitizenAuthenticated, citizenUser } = useAuthStore()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className={styles.page}>
      {/* ═══ TOP NAVIGATION BAR ═══ */}
      <header className={styles.topbar}>
        <Link to="/" className={styles.brand}>
          <div className={styles.brandIcon}>
            <span className="material-symbols-outlined">account_balance</span>
          </div>
          <div className={styles.brandText}>
            <span className={styles.brandName}>RevenueGov</span>
            <span className={styles.brandTagline}>Government Services</span>
          </div>
        </Link>

        {/* Desktop right section */}
        <div className={styles.navRight}>
          {/* Language switcher */}
          <div className={styles.langSwitcher}>
            {['en', 'hi', 'mr'].map(lang => (
              <button
                key={lang}
                className={`${styles.langBtn} ${language === lang ? styles.langActive : ''}`}
                onClick={() => setLanguage(lang)}
              >
                {LANGUAGE_NAMES_LOCAL[lang]}
              </button>
            ))}
          </div>

          {/* Auth buttons */}
          {isCitizenAuthenticated ? (
            <button
              className={styles.dashboardBtn}
              onClick={() => navigate('/assistant')}
            >
              <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>dashboard</span>
              My Dashboard
            </button>
          ) : (
            <>
              <button
                className={styles.loginBtn}
                onClick={() => navigate('/login')}
              >
                Sign In
              </button>
              <button
                className={styles.registerBtn}
                onClick={() => navigate('/login?tab=register')}
              >
                Register
              </button>
            </>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className={styles.menuBtn}
          onClick={() => setMenuOpen(v => !v)}
          aria-label="Open menu"
        >
          <span className="material-symbols-outlined">{menuOpen ? 'close' : 'menu'}</span>
        </button>
      </header>

      {/* Mobile menu drawer */}
      {menuOpen && (
        <>
          <div className={styles.mobileOverlay} onClick={() => setMenuOpen(false)} />
          <div className={styles.mobileMenu}>
            <div className={styles.mobileLangRow}>
              {['en', 'hi', 'mr'].map(lang => (
                <button
                  key={lang}
                  className={`${styles.langBtn} ${language === lang ? styles.langActive : ''}`}
                  onClick={() => { setLanguage(lang); setMenuOpen(false) }}
                >
                  {LANGUAGE_NAMES_LOCAL[lang]}
                </button>
              ))}
            </div>
            {isCitizenAuthenticated ? (
              <button
                className={`${styles.registerBtn} ${styles.mobileFullBtn}`}
                onClick={() => { navigate('/assistant'); setMenuOpen(false) }}
              >
                My Dashboard
              </button>
            ) : (
              <>
                <button
                  className={`${styles.loginBtn} ${styles.mobileFullBtn}`}
                  onClick={() => { navigate('/login'); setMenuOpen(false) }}
                >
                  Sign In
                </button>
                <button
                  className={`${styles.registerBtn} ${styles.mobileFullBtn}`}
                  onClick={() => { navigate('/login?tab=register'); setMenuOpen(false) }}
                >
                  Register
                </button>
              </>
            )}
          </div>
        </>
      )}

      {/* Page content */}
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
