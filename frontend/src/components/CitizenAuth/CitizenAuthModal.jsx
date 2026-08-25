import { useState } from 'react'
import useAuthStore from '../../store/authStore'
import { loginCitizen, registerCitizen } from '../../api/auth'
import styles from './CitizenAuthModal.module.css'

export default function CitizenAuthModal({ isOpen, onClose, onSuccess }) {
  const [activeTab, setActiveTab] = useState('login') // 'login' | 'register'
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const setCitizenAuth = useAuthStore((s) => s.setCitizenAuth)

  if (!isOpen) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (activeTab === 'login') {
        const res = await loginCitizen({ identifier, password })
        setCitizenAuth(res.access_token, {
          citizen_id: res.citizen_id,
          name: res.name,
          email: res.email,
          phone: res.phone,
          role: 'CITIZEN',
        })
      } else {
        const res = await registerCitizen({
          identifier,
          password,
          name: name || undefined,
          address: address || undefined,
        })
        setCitizenAuth(res.access_token, {
          citizen_id: res.citizen_id,
          name: res.name,
          email: res.email,
          phone: res.phone,
          role: 'CITIZEN',
        })
      }
      setLoading(false)
      if (onSuccess) onSuccess()
      onClose()
    } catch (err) {
      setLoading(false)
      setError(err.message || 'Authentication failed. Please check your credentials.')
    }
  }

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <div className={styles.headerIcon}>
              <span className="material-symbols-outlined">account_balance</span>
            </div>
            <div>
              <h3 className={styles.title}>
                {activeTab === 'login' ? 'Citizen Sign In' : 'Create Account'}
              </h3>
              <p className={styles.subtitle}>RevenueGov — Government Services, Simplified</p>
            </div>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${activeTab === 'login' ? styles.active : ''}`}
            onClick={() => { setActiveTab('login'); setError(''); }}
          >
            Sign In
          </button>
          <button
            className={`${styles.tab} ${activeTab === 'register' ? styles.active : ''}`}
            onClick={() => { setActiveTab('register'); setError(''); }}
          >
            Register
          </button>
        </div>

        <div className={styles.body}>
          {error && (
            <div className={styles.errorBanner}>
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>error</span>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {activeTab === 'register' && (
              <div className={styles.formGroup}>
                <label className={styles.label}>Full Name</label>
                <input
                  type="text"
                  className={styles.input}
                  placeholder="Enter your full name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
            )}

            <div className={styles.formGroup}>
              <label className={styles.label}>Email or Phone Number</label>
              <input
                type="text"
                className={styles.input}
                placeholder="citizen@example.com or +919999999999"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label}>Password</label>
              <input
                type="password"
                className={styles.input}
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {activeTab === 'register' && (
              <div className={styles.formGroup}>
                <label className={styles.label}>Residential Address (Optional)</label>
                <input
                  type="text"
                  className={styles.input}
                  placeholder="Street, City, State"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                />
              </div>
            )}

            <button type="submit" className={styles.submitBtn} disabled={loading}>
              {loading
                ? 'Processing...'
                : activeTab === 'login'
                ? 'Sign In to Citizen Dashboard'
                : 'Create Permanent Citizen Account'}
            </button>
          </form>

          <p className={styles.footerNote}>
            Your persistent citizen ID remains unified across Web, WhatsApp, and IVR helpline services.
          </p>
        </div>
      </div>
    </div>
  )
}
