import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { UserCheck, Eye, EyeOff } from 'lucide-react'
import { login } from '../../api/auth'
import useAuthStore from '../../store/authStore'
import styles from '../AdminLogin/AdminLogin.module.css'

export default function OfficerLogin() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd,  setShowPwd]  = useState(false)
  const [loading,  setLoading]  = useState(false)
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await login(username, password)
      if (!['ADMIN', 'OFFICER'].includes(data.role)) {
        toast.error('Officer access required')
        setLoading(false)
        return
      }
      setAuth(data.access_token, { username: data.username, role: data.role })
      toast.success(`Welcome, ${data.username}`)
      navigate('/admin/dashboard')
    } catch (err) {
      toast.error(err.message || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.icon}><UserCheck size={36} /></div>
        <h1 className={styles.title}>Officer Login</h1>
        <p className={styles.subtitle}>Revenue Services Platform — Officer Portal</p>
        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="officer-username">Username</label>
            <input id="officer-username" className={styles.input} type="text" value={username}
              onChange={e => setUsername(e.target.value)} placeholder="officer" autoComplete="username" required />
          </div>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="officer-password">Password</label>
            <div className={styles.passwordWrap}>
              <input id="officer-password" className={styles.input} type={showPwd ? 'text' : 'password'}
                value={password} onChange={e => setPassword(e.target.value)}
                placeholder="••••••••" autoComplete="current-password" required />
              <button type="button" className={styles.eyeBtn} onClick={() => setShowPwd(v => !v)}>
                {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
          <button className={styles.submitBtn} type="submit" disabled={loading}>
            {loading ? 'Logging in…' : 'Login as Officer'}
          </button>
        </form>
        <div className={styles.divider} />
        <Link to="/admin/login" className={styles.switchLink}>Admin login →</Link>
        <Link to="/" className={styles.homeLink}>← Back to citizen portal</Link>
      </div>
    </div>
  )
}
