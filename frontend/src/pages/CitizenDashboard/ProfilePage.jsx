import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import { getCitizenProfile, updateCitizenProfile } from '../../api/auth'
import styles from './ProfilePage.module.css'

function initials(name, id) {
  if (name) return name.trim().split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
  if (id)   return id.replace('CIT-', '').slice(0, 2)
  return 'C'
}

export default function ProfilePage() {
  const { citizenUser, updateCitizenUser } = useAuthStore()
  const [profile, setProfile]   = useState(null)
  const [loading, setLoading]   = useState(true)
  const [editing, setEditing]   = useState(false)
  const [name, setName]         = useState('')
  const [phone, setPhone]       = useState('')
  const [email, setEmail]       = useState('')
  const [address, setAddress]   = useState('')
  const [statusMsg, setStatusMsg] = useState({ type: '', text: '' })

  useEffect(() => { fetchProfile() }, [])

  const fetchProfile = async () => {
    setLoading(true)
    try {
      const data = await getCitizenProfile()
      setProfile(data)
      setName(data.name || '')
      setPhone(data.phone || '')
      setEmail(data.email || '')
      setAddress(data.address || '')
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message || 'Failed to load profile.' })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setStatusMsg({ type: '', text: '' })
    try {
      const updated = await updateCitizenProfile({ name, phone, email, address })
      setProfile(updated)
      updateCitizenUser({ name: updated.name, phone: updated.phone, email: updated.email, address: updated.address })
      setEditing(false)
      setStatusMsg({ type: 'success', text: 'Profile updated successfully.' })
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message || 'Failed to update profile.' })
    }
  }

  const cid = profile?.citizen_id || citizenUser?.citizen_id || ''

  return (
    <div className={styles.page}>

      {/* Page header */}
      <header className={styles.pageHeader}>
        <h2 className={styles.pageTitle}>Citizen Account</h2>
        <p className={styles.pageSubtitle}>Manage your profile and preferences.</p>
      </header>

      <div className={styles.content}>
        {/* ── Profile card ── */}
        <div className={styles.profileCard}>

          {/* Avatar + identity */}
          <div className={styles.avatarRow}>
            <div className={styles.avatarLg}>
              {loading ? '…' : initials(profile?.name, cid)}
            </div>
            <div>
              <h3 className={styles.profileName}>{profile?.name || 'Citizen Account'}</h3>
              <div className={styles.citizenIdBadge}>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>verified_user</span>
                {cid}
              </div>
            </div>
          </div>

          {/* Status message */}
          {statusMsg.text && (
            <div className={`${styles.statusMsg} ${statusMsg.type === 'success' ? styles.statusSuccess : styles.statusError}`}>
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                {statusMsg.type === 'success' ? 'check_circle' : 'error'}
              </span>
              {statusMsg.text}
            </div>
          )}

          {loading ? (
            <div className={styles.loadingRow}>
              <span className="material-symbols-outlined" style={{ fontSize: 32, color: 'var(--rg-outline-variant)' }}>progress_activity</span>
            </div>
          ) : !editing ? (
            <>
              {/* Info bento grid */}
              <div className={styles.bentoGrid}>
                {[
                  { icon: 'badge',        label: 'Citizen ID',        value: cid },
                  { icon: 'language',     label: 'Preferred Language', value: (profile?.preferred_language || 'en').toUpperCase() },
                  { icon: 'call',         label: 'Phone Number',       value: profile?.phone || 'Not provided' },
                  { icon: 'email',        label: 'Email Address',      value: profile?.email || 'Not provided' },
                  { icon: 'home',         label: 'Address',            value: profile?.address || 'Not provided', full: true },
                ].map(({ icon, label, value, full }) => (
                  <div key={label} className={`${styles.bentoCell} ${full ? styles.bentoCellFull : ''}`}>
                    <div className={styles.bentoCellHeader}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--rg-primary)' }}>{icon}</span>
                      <span className={styles.bentoCellLabel}>{label}</span>
                    </div>
                    <span className={styles.bentoCellValue}>{value}</span>
                  </div>
                ))}
              </div>

              <div className={styles.actions}>
                <button className={styles.editBtn} onClick={() => setEditing(true)}>
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>edit</span>
                  Edit Profile
                </button>
                <Link to="/applications" className={styles.appsBtn}>
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>assignment</span>
                  My Applications
                </Link>
              </div>
            </>
          ) : (
            <form onSubmit={handleSave} className={styles.editForm}>
              {[
                { label: 'Full Name',     val: name,    set: setName,    type: 'text',  ph: 'Your full name' },
                { label: 'Phone Number',  val: phone,   set: setPhone,   type: 'tel',   ph: '+91 XXXXXXXXXX' },
                { label: 'Email Address', val: email,   set: setEmail,   type: 'email', ph: 'citizen@example.com' },
                { label: 'Address',       val: address, set: setAddress, type: 'text',  ph: 'Residential address' },
              ].map(({ label, val, set, type, ph }) => (
                <div key={label} className={styles.formField}>
                  <label className={styles.formLabel}>{label}</label>
                  <input
                    type={type}
                    className={styles.formInput}
                    value={val}
                    onChange={e => set(e.target.value)}
                    placeholder={ph}
                  />
                </div>
              ))}
              <div className={styles.actions}>
                <button type="button" className={styles.cancelBtn} onClick={() => setEditing(false)}>Cancel</button>
                <button type="submit" className={styles.editBtn}>
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>save</span>
                  Save Changes
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Channel identities card */}
        {profile?.identities && profile.identities.length > 0 && (
          <div className={styles.identitiesCard}>
            <h3 className={styles.sectionTitle}>Connected Channels</h3>
            <ul className={styles.identityList}>
              {profile.identities.map((ident, i) => (
                <li key={i} className={styles.identityItem}>
                  <div className={styles.identityIcon}>
                    <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                      {ident.channel === 'WHATSAPP' ? 'chat' : ident.channel === 'IVR' ? 'call' : 'public'}
                    </span>
                  </div>
                  <div>
                    <div className={styles.identityChannel}>{ident.channel}</div>
                    <div className={styles.identityType}>{ident.identifier_type}</div>
                  </div>
                  <span className="material-symbols-outlined" style={{ marginLeft: 'auto', fontSize: 16, color: ident.verified ? 'var(--rg-success)' : 'var(--rg-warning)' }}>
                    {ident.verified ? 'verified' : 'schedule'}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
