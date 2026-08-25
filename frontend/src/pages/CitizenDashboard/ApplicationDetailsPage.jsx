import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { applicationsApi } from '../../api/applications'
import styles from './ApplicationDetailsPage.module.css'

const DOC_STATUS_ICON = {
  VERIFIED: 'task_alt',
  MATCHED:  'task_alt',
  MISMATCH: 'error',
  PENDING:  'schedule',
  REJECTED: 'cancel',
}
const DOC_STATUS_COLOR = {
  VERIFIED: 'var(--rg-success)',
  MATCHED:  'var(--rg-success)',
  MISMATCH: 'var(--rg-warning)',
  PENDING:  'var(--rg-warning)',
  REJECTED: 'var(--rg-error)',
}

function formatKey(k) {
  return k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function ApplicationDetailsPage() {
  const { id } = useParams()
  const [app, setApp]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  useEffect(() => { fetchApp() }, [id])

  const fetchApp = async () => {
    setLoading(true)
    try {
      const res = await applicationsApi.getStatus(id)
      setApp(res.application)
    } catch (err) {
      setError(err.message || 'Failed to load application.')
    } finally {
      setLoading(false)
    }
  }

  if (loading) return (
    <div className={styles.page}>
      <div className={styles.centerLoader}>
        <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'var(--rg-outline-variant)', animation: 'spin 1s linear infinite' }}>progress_activity</span>
      </div>
    </div>
  )

  if (error) return (
    <div className={styles.page}>
      <Link to="/applications" className={styles.backBtn}>
        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_back</span>
        My Applications
      </Link>
      <div className={styles.errorBox}>{error}</div>
    </div>
  )

  const serviceLabel = (app?.service_name || (app?.service_type || '').replace(/_/g, ' '))
    .split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ')

  const applicantName = app?.slots_data?.applicant_name || '—'

  return (
    <div className={styles.page}>
      {/* ── Center column ── */}
      <div className={styles.centerCol}>
        <Link to="/applications" className={styles.backBtn}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_back</span>
          My Applications
        </Link>

        {/* Page title */}
        <header className={styles.pageHeader}>
          <div>
            <h2 className={styles.pageTitle}>{serviceLabel}</h2>
            <p className={styles.pageSub}>#{app?.application_number}</p>
          </div>
          <button className={styles.moreBtn}>
            <span className="material-symbols-outlined">more_vert</span>
          </button>
        </header>

        <hr className={styles.divider} />

        {/* ── Vertical Timeline ── */}
        <div className={styles.timeline}>
          {[
            { label: 'Application Submitted',  sub: 'Received securely by RevenueGov.', date: formatDate(app?.created_at), done: true },
            { label: 'Documents Verified',     sub: 'All required proofs accepted.',    date: formatDate(app?.submitted_at),
              done: ['SUBMITTED_FOR_VERIFICATION','PENDING_OFFICER_PRE_APPROVAL','UNDER_REVIEW','APPROVED','CERTIFICATE_READY','COMPLETED'].includes(app?.status) },
            { label: 'Officer Review',         sub: 'Currently under evaluation.', date: 'Current',
              current: ['PENDING_OFFICER_PRE_APPROVAL','UNDER_REVIEW'].includes(app?.status),
              done: ['APPROVED','CERTIFICATE_READY','COMPLETED'].includes(app?.status) },
            { label: 'Final Approval & Issuance', sub: 'Certificate generation pending.', date: '',
              done: ['APPROVED','CERTIFICATE_READY','COMPLETED'].includes(app?.status) },
          ].map((step, i, arr) => (
            <div key={step.label} className={styles.tStep}>
              {i < arr.length - 1 && (
                <div className={`${styles.tLine} ${step.done ? styles.tLineActive : ''}`} />
              )}
              <div className={`${styles.tDot} ${step.done ? styles.tDotDone : step.current ? styles.tDotCurrent : styles.tDotPending}`}>
                {step.done
                  ? <span className="material-symbols-outlined" style={{ fontSize: 18, fontVariationSettings: "'FILL' 1" }}>check</span>
                  : step.current
                  ? <div className={styles.tPulse} />
                  : <span className="material-symbols-outlined" style={{ fontSize: 16 }}>hourglass_empty</span>
                }
              </div>
              <div className={styles.tContent}>
                <h4 className={`${styles.tLabel} ${step.current ? styles.tLabelCurrent : step.done ? '' : styles.tLabelPending}`}>
                  {step.label}
                </h4>
                <p className={styles.tSub}>{step.sub}</p>
              </div>
              {step.date && (
                <div className={`${styles.tDate} ${step.current ? styles.tDateCurrent : ''}`}>
                  {step.date}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Right Context Panel ── */}
      <aside className={styles.rightPanel}>
        <div className={styles.rightHeader}>
          <h3 className={styles.rightTitle}>Application Details</h3>
          <p className={styles.rightSub}>Context for #{app?.application_number}</p>
        </div>

        {/* Bento Grid */}
        <div className={styles.bentoGrid}>
          <div className={styles.bentoCell}>
            <p className={styles.bentoCellLabel}>Applicant Name</p>
            <p className={styles.bentoCellValue}>{applicantName}</p>
          </div>
          <div className={styles.bentoCell}>
            <p className={styles.bentoCellLabel}>Channel</p>
            <p className={styles.bentoCellValue}>{app?.channel || 'WEB'}</p>
          </div>
          {app?.slots_data?.annual_income && (
            <div className={`${styles.bentoCell} ${styles.bentoCellFull}`}>
              <p className={styles.bentoCellLabel}>Declared Annual Income</p>
              <p className={styles.bentoCellValueLg}>
                ₹{Number(app.slots_data.annual_income).toLocaleString('en-IN')}
              </p>
            </div>
          )}
          {app?.slots_data?.address && (
            <div className={`${styles.bentoCell} ${styles.bentoCellFull}`}>
              <p className={styles.bentoCellLabel}>Address</p>
              <p className={styles.bentoCellValue}>{app.slots_data.address}</p>
            </div>
          )}
        </div>

        <hr className={styles.divider} />

        {/* Required Documents */}
        <div>
          <h3 className={styles.sectionTitle}>Required Documents</h3>
          <ul className={styles.docList}>
            {app?.documents && app.documents.length > 0 ? app.documents.map(doc => {
              const vstatus = doc.verification_status || 'PENDING'
              const icon  = DOC_STATUS_ICON[vstatus] || 'schedule'
              const color = DOC_STATUS_COLOR[vstatus] || 'var(--rg-warning)'
              const isWarn = vstatus === 'MISMATCH' || vstatus === 'PENDING'
              return (
                <li
                  key={doc.id}
                  className={`${styles.docItem} ${isWarn ? styles.docItemWarn : ''}`}
                >
                  {isWarn && <div className={styles.docAccent} style={{ background: isWarn ? 'var(--rg-warning)' : 'transparent' }} />}
                  <div className={`${styles.docItemInner} ${isWarn ? styles.docItemInnerWarn : ''}`}>
                    <span className="material-symbols-outlined" style={{ color, fontSize: 22, fontVariationSettings: vstatus === 'VERIFIED' ? "'FILL' 1" : '' }}>
                      {icon}
                    </span>
                    <div>
                      <p className={styles.docName}>{formatKey(doc.doc_type)}</p>
                      <p className={styles.docFile}>{doc.filename || 'Document uploaded'}</p>
                    </div>
                  </div>
                  <button className={styles.docViewBtn}>
                    <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
                      {isWarn ? 'upload_file' : 'visibility'}
                    </span>
                  </button>
                </li>
              )
            }) : (
              <li className={styles.docItem} style={{ border: '1px dashed var(--rg-outline-variant)', opacity: 0.7 }}>
                <div className={styles.docItemInner}>
                  <span className="material-symbols-outlined" style={{ color: 'var(--rg-outline)', fontSize: 22 }}>upload_file</span>
                  <div>
                    <p className={styles.docName}>No documents yet</p>
                    <p className={styles.docFile}>Upload via the AI Assistant</p>
                  </div>
                </div>
              </li>
            )}
          </ul>
        </div>

        {/* Bottom actions */}
        <div className={styles.bottomActions}>
          <div className={styles.assistCard}>
            <span className="material-symbols-outlined" style={{ color: 'var(--rg-primary)', marginTop: 2 }}>support_agent</span>
            <div>
              <p className={styles.assistTitle}>Need assistance?</p>
              <p className={styles.assistDesc}>Chat with our AI assistant regarding this specific application.</p>
            </div>
          </div>
          <Link to="/assistant" className={styles.uploadBtn}>
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>cloud_upload</span>
            Upload Additional Files
          </Link>
        </div>
      </aside>
    </div>
  )
}
