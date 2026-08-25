import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { applicationsApi } from '../../api/applications'
import useAuthStore from '../../store/authStore'
import styles from './MyApplicationsPage.module.css'

const STATUS_CONFIG = {
  SUBMITTED:                   { label: 'Submitted',       cls: 'progress', accent: '#006b55' },
  SUBMITTED_FOR_VERIFICATION:  { label: 'In Verification', cls: 'progress', accent: '#006b55' },
  PENDING_OFFICER_PRE_APPROVAL:{ label: 'Under Review',    cls: 'progress', accent: '#006b55' },
  UNDER_REVIEW:                { label: 'Under Review',    cls: 'progress', accent: '#006b55' },
  CLARIFICATION_REQUIRED:      { label: 'Action Required', cls: 'warning',  accent: '#D99A00' },
  PAYMENT_PENDING:             { label: 'Action Required', cls: 'warning',  accent: '#D99A00' },
  APPROVED:                    { label: 'Approved',        cls: 'success',  accent: '#198754' },
  CERTIFICATE_READY:           { label: 'Ready',           cls: 'success',  accent: '#198754' },
  COMPLETED:                   { label: 'Completed',       cls: 'success',  accent: '#198754' },
  REJECTED:                    { label: 'Rejected',        cls: 'rejected', accent: '#D64545' },
}

const FILTERS = ['All', 'In Progress', 'Completed', 'Rejected']

const SERVICE_ICONS = {
  income_certificate:   'badge',
  caste_certificate:    'verified',
  obc_ncl_certificate:  'groups',
  domicile_certificate: 'home_work',
}

function getFilteredApps(apps, filter) {
  if (filter === 'All') return apps
  if (filter === 'In Progress') return apps.filter(a =>
    ['SUBMITTED','SUBMITTED_FOR_VERIFICATION','PENDING_OFFICER_PRE_APPROVAL','UNDER_REVIEW','PAYMENT_PENDING','CLARIFICATION_REQUIRED'].includes(a.status)
  )
  if (filter === 'Completed') return apps.filter(a =>
    ['APPROVED','CERTIFICATE_READY','COMPLETED'].includes(a.status)
  )
  if (filter === 'Rejected') return apps.filter(a => a.status === 'REJECTED')
  return apps
}

function TimelineSteps({ status }) {
  const steps = [
    { key: 'submitted', label: 'Application Submitted', done: true },
    { key: 'verified',  label: 'Documents Verified',
      done: ['SUBMITTED_FOR_VERIFICATION','PENDING_OFFICER_PRE_APPROVAL','UNDER_REVIEW','APPROVED','CERTIFICATE_READY','COMPLETED'].includes(status) },
    { key: 'review',    label: 'Officer Review',
      current: ['PENDING_OFFICER_PRE_APPROVAL','UNDER_REVIEW'].includes(status),
      done: ['APPROVED','CERTIFICATE_READY','COMPLETED'].includes(status) },
    { key: 'approval',  label: 'Final Approval',
      done: ['APPROVED','CERTIFICATE_READY','COMPLETED'].includes(status) },
  ]
  return (
    <div className={styles.timeline}>
      {steps.map((step, i) => (
        <div key={step.key} className={styles.timelineStep}>
          {i < steps.length - 1 && (
            <div className={`${styles.timelineLine} ${step.done ? styles.lineActive : ''}`} />
          )}
          <div className={`${styles.timelineDot} ${step.done ? styles.dotDone : step.current ? styles.dotCurrent : styles.dotPending}`}>
            {step.done
              ? <span className="material-symbols-outlined" style={{ fontSize: '16px', fontVariationSettings: "'FILL' 1" }}>check</span>
              : step.current
              ? <div className={styles.dotPulse} />
              : <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>hourglass_empty</span>
            }
          </div>
          <div className={styles.timelineLabel}>
            <span className={`${styles.timelineLabelText} ${step.current ? styles.labelCurrent : step.done ? styles.labelDone : styles.labelPending}`}>
              {step.label}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function MyApplicationsPage() {
  const navigate  = useNavigate()
  const { citizenUser } = useAuthStore()
  const [applications, setApplications] = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [filter, setFilter]       = useState('All')
  const [expanded, setExpanded]   = useState(null)

  useEffect(() => { fetchApps() }, [])

  const fetchApps = async () => {
    setLoading(true)
    try {
      const res = await applicationsApi.getMyApplications()
      setApplications(res.applications || [])
    } catch (err) {
      setError(err.message || 'Failed to load applications.')
    } finally {
      setLoading(false)
    }
  }

  const filtered = getFilteredApps(applications, filter)
  const inProgressCount = applications.filter(a =>
    ['SUBMITTED','SUBMITTED_FOR_VERIFICATION','PENDING_OFFICER_PRE_APPROVAL','UNDER_REVIEW','PAYMENT_PENDING'].includes(a.status)
  ).length

  const formatService = (app) =>
    (app.service_name || (app.service_type || app.service_id || '').replace(/_/g, ' '))
      .split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ')

  const formatDate = (d) => d ? new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

  return (
    <div className={styles.page}>
      {/* ── Page Header ── */}
      <header className={styles.pageHeader}>
        <div>
          <h2 className={styles.pageTitle}>My Applications</h2>
          <p className={styles.pageSubtitle}>Track and manage your ongoing requests.</p>
        </div>
      </header>

      {/* ── Filter Pills ── */}
      <div className={styles.filterBar}>
        {FILTERS.map(f => (
          <button
            key={f}
            className={`${styles.filterPill} ${filter === f ? styles.pillActive : ''}`}
            onClick={() => setFilter(f)}
          >
            {f}
            {f === 'In Progress' && inProgressCount > 0 && (
              <span className={styles.pillBadge}>{inProgressCount}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Content ── */}
      {error && (
        <div className={styles.errorBox}>
          <span className="material-symbols-outlined">error</span>
          {error}
        </div>
      )}

      {loading ? (
        <div className={styles.cardList}>
          {[1,2,3].map(i => <div key={i} className={`${styles.card} skeleton`} style={{ height: 80 }} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className={styles.emptyState}>
          <span className="material-symbols-outlined" style={{ fontSize: 48, color: 'var(--rg-outline-variant)' }}>assignment</span>
          <h4 className={styles.emptyTitle}>No Applications Found</h4>
          <p className={styles.emptyDesc}>Start a new application via the AI Assistant.</p>
          <Link to="/assistant" className={styles.startBtn}>
            <span className="material-symbols-outlined">add</span>
            Start New Application
          </Link>
        </div>
      ) : (
        <div className={styles.cardList}>
          {/* First card: expanded with full timeline (like Stitch reference) */}
          {filtered.map((app, idx) => {
            const sc = STATUS_CONFIG[app.status] || { label: app.status, cls: 'progress', accent: '#006b55' }
            const isExp = expanded === app.id || (expanded === null && idx === 0)
            const icon = SERVICE_ICONS[app.service_type || app.service_id] || 'description'

            return isExp ? (
              /* ── EXPANDED card ── */
              <div key={app.id} className={styles.cardExpanded} onClick={() => setExpanded(isExp ? -1 : app.id)}>
                <div className={styles.cardAccent} style={{ background: sc.accent }} />
                <div className={styles.cardExpandedInner}>
                  <div className={styles.cardTopRow}>
                    <div>
                      <div className={styles.cardMeta}>
                        <span className={`${styles.statusBadge} ${styles[sc.cls]}`}>{sc.label}</span>
                        <span className={styles.appNum}>#{app.application_number}</span>
                      </div>
                      <h3 className={styles.cardTitle}>{formatService(app)}</h3>
                      <p className={styles.cardDate}>Submitted on {formatDate(app.created_at || app.submitted_at)}</p>
                    </div>
                    <button className={styles.moreBtn} onClick={(e) => { e.stopPropagation(); navigate(`/applications/${app.application_number}`) }}>
                      <span className="material-symbols-outlined">more_vert</span>
                    </button>
                  </div>
                  <hr className={styles.divider} />
                  <TimelineSteps status={app.status} />
                </div>
              </div>
            ) : (
              /* ── COLLAPSED card ── */
              <div
                key={app.id}
                className={styles.cardCollapsed}
                onClick={() => setExpanded(app.id)}
              >
                <div className={styles.cardCollapsedLeft}>
                  <div className={styles.cardIcon}>
                    <span className="material-symbols-outlined" style={{ fontSize: 22 }}>{icon}</span>
                  </div>
                  <div>
                    <h3 className={styles.cardCollapsedTitle}>{formatService(app)}</h3>
                    <p className={styles.cardCollapsedSub}>#{app.application_number} • {sc.label}</p>
                  </div>
                </div>
                <div className={styles.cardCollapsedRight}>
                  <span className={`${styles.statusBadge} ${styles[sc.cls]}`} style={{ display: 'none' }}>{sc.label}</span>
                  <span
                    className={styles.statusChip}
                    style={{ background: sc.cls === 'warning' ? 'rgba(217,154,0,0.12)' : sc.cls === 'success' ? 'rgba(25,135,84,0.10)' : sc.cls === 'rejected' ? 'rgba(214,69,69,0.10)' : 'rgba(0,107,85,0.10)',
                              color: sc.accent }}
                  >
                    {sc.label}
                  </span>
                  <span className="material-symbols-outlined" style={{ color: 'var(--rg-outline)', fontSize: 20 }}>chevron_right</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Right context panel placeholder ── */}
      <aside className={styles.rightPanel}>
        <div className={styles.rightPanelHeader}>
          <h3 className={styles.rightPanelTitle}>Application Details</h3>
          {expanded !== null && filtered[0] && (
            <p className={styles.rightPanelSub}>Context for #{filtered.find(a => a.id === expanded)?.application_number || filtered[0]?.application_number}</p>
          )}
        </div>

        {/* Need Assistance */}
        <div className={styles.assistCard}>
          <span className="material-symbols-outlined" style={{ color: 'var(--rg-primary)', marginTop: 2 }}>support_agent</span>
          <div>
            <p className={styles.assistTitle}>Need assistance?</p>
            <p className={styles.assistDesc}>Chat with our AI assistant regarding a specific application.</p>
          </div>
        </div>

        {/* Upload button */}
        <Link to="/assistant" className={styles.uploadBtn}>
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>cloud_upload</span>
          Upload Additional Files
        </Link>
      </aside>
    </div>
  )
}
