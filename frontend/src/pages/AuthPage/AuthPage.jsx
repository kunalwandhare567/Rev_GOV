import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import { loginCitizen, registerCitizen } from '../../api/auth'
import styles from './AuthPage.module.css'

export default function AuthPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { setCitizenAuth, isCitizenAuthenticated, citizenUser } = useAuthStore()

  const [tab, setTab]             = useState(searchParams.get('tab') === 'register' ? 'register' : 'login')
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword]   = useState('')
  const [name, setName]           = useState('')
  const [address, setAddress]     = useState('')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')

  // Redirect if already authenticated
  useEffect(() => {
    if (isCitizenAuthenticated) {
      navigate('/assistant', { replace: true })
    }
  }, [isCitizenAuthenticated])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (tab === 'login') {
        const res = await loginCitizen({ identifier, password })
        setCitizenAuth(res.access_token, {
          citizen_id: res.citizen_id,
          name:       res.name,
          email:      res.email,
          phone:      res.phone,
          role:       'CITIZEN',
        })
      } else {
        const res = await registerCitizen({
          identifier,
          password,
          name:    name    || undefined,
          address: address || undefined,
        })
        setCitizenAuth(res.access_token, {
          citizen_id: res.citizen_id,
          name:       res.name,
          email:      res.email,
          phone:      res.phone,
          role:       'CITIZEN',
        })
      }
      navigate('/assistant', { replace: true })
    } catch (err) {
      setError(err.message || 'Authentication failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        {/* Header */}
        <div className={styles.cardHeader}>
          <div className={styles.logoIcon}>
            <span className="material-symbols-outlined">account_balance</span>
          </div>
          <div>
            <h1 className={styles.title}>RevenueGov</h1>
            <p className={styles.subtitle}>Government Services, Simplified</p>
          </div>
        </div>

        {/* Role Selector — only Admin path shown here */}
        <div className={styles.portalNote}>
          <span className="material-symbols-outlined" style={{ fontSize: '16px', color: 'var(--rg-text-body)' }}>info</span>
          <span>
            For officers and administrators, use the{' '}
            <Link to="/admin/login" className={styles.adminLink}>Admin Portal</Link>.
          </span>
        </div>

        {/* Tabs */}
        <div className={styles.tabs}>
          <button
            className={`${styles.tabBtn} ${tab === 'login' ? styles.tabActive : ''}`}
            onClick={() => { setTab('login'); setError('') }}
          >
            Sign In
          </button>
          <button
            className={`${styles.tabBtn} ${tab === 'register' ? styles.tabActive : ''}`}
            onClick={() => { setTab('register'); setError('') }}
          >
            Register
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className={styles.errorBanner}>
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>error</span>
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className={styles.form}>
          {tab === 'register' && (
            <div className={styles.field}>
              <label className={styles.label}>Full Name</label>
              <input
                type="text"
                className={styles.input}
                placeholder="Your full name"
                value={name}
                onChange={e => setName(e.target.value)}
              />
            </div>
          )}

          <div className={styles.field}>
            <label className={styles.label}>Email or Mobile Number</label>
            <input
              type="text"
              className={styles.input}
              placeholder="citizen@example.com or +91XXXXXXXXXX"
              value={identifier}
              onChange={e => setIdentifier(e.target.value)}
              required
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Password</label>
            <input
              type="password"
              className={styles.input}
              placeholder="Enter password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          {tab === 'register' && (
            <div className={styles.field}>
              <label className={styles.label}>Residential Address (Optional)</label>
              <input
                type="text"
                className={styles.input}
                placeholder="Street, City, State"
                value={address}
                onChange={e => setAddress(e.target.value)}
              />
            </div>
          )}

          <button type="submit" className={styles.submitBtn} disabled={loading}>
            {loading
              ? 'Processing...'
              : tab === 'login'
              ? 'Sign In to Citizen Dashboard'
              : 'Create Permanent Citizen Account'}
          </button>
        </form>

        {/* Footer note */}
        <p className={styles.footerNote}>
          Your permanent Citizen ID works across Web, WhatsApp, and IVR helpline.
        </p>
      </div>
    </div>
  )
}
