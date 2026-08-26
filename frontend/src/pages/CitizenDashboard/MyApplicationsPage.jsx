import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { applicationsApi } from '../../api/applications'
import { documentsApi } from '../../api/documents'
import useAuthStore from '../../store/authStore'
import useChatStore from '../../store/chatStore'
import { useRightPanel } from '../../layouts/RightPanelContext'
import {
  getStatusUI, FILTER_GROUPS, TIMELINE_STAGES, getTimelineState, SERVICE_ICONS
} from '../../utils/statusMap'
import styles from './MyApplicationsPage.module.css'

/* ── Timeline Steps (horizontal, scrollable on mobile) ── */
function TimelineSteps({ status }) {
  return (
    <div className={styles.timeline}>
      {TIMELINE_STAGES.map((stage, i) => {
        const state = getTimelineState(stage, status)
        return (
          <div key={stage.key} className={styles.timelineItem}>
            <div className={`${styles.timelineDot} ${styles[`dot_${state}`]}`}>
              {state === 'done' ? (
                <span className="material-symbols-outlined" style={{ fontSize: 14, fontVariationSettings: "'FILL' 1" }}>check</span>
              ) : state === 'active' ? (
                <div className={styles.dotPulse} />
              ) : (
                <div className={styles.dotEmpty} />
              )}
            </div>
            <div className={styles.timelineLabel}>
              <span className={`${styles.timelineLabelText} ${styles[`lbl_${state}`]}`}>{stage.label}</span>
            </div>
            {i < TIMELINE_STAGES.length - 1 && (
              <div className={`${styles.timelineLine} ${state === 'done' ? styles.lineActive : ''}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ── Application Detail Right Panel ── */
function ApplicationDetailPanel({ app, onViewDocs, onSubmit, submitting, onPayFee, paying }) {
  const navigate = useNavigate()

  const { data: fields = {}, isLoading: fieldsLoading } = useQuery({
    queryKey: ['fields', app.id],
    queryFn:  () => documentsApi.getFields(app.id),
    enabled:  !!app.id,
  })
  const { data: documents = [], isLoading: docsLoading } = useQuery({
    queryKey: ['documents', app.id],
    queryFn:  () => documentsApi.getDocuments(app.id),
    enabled:  !!app.id,
  })
  const { data: readiness } = useQuery({
    queryKey: ['readiness', app.application_number],
    queryFn:  () => documentsApi.getReadiness(app.application_number),
    enabled:  !!app.application_number,
  })

  const statusUI = getStatusUI(app.status)
  const progressVal = (app.progress_percent != null && app.progress_percent > 0) ? app.progress_percent : statusUI.progress
  const hasMismatches = documents.some(d => d.mismatch_fields?.length > 0)
  const allResolved   = documents.every(d => !d.mismatch_fields?.length || d.mismatch_fields.every(f => d.mismatch_resolutions?.[f]))
  const canSubmit     = app.status === 'FINAL_REVIEW' && allResolved && (readiness?.can_submit || readiness?.score >= 65)

  return (
    <div className={styles.detailPanel}>
      {/* Header */}
      <div className={styles.detailPanelHead}>
        <div className={styles.detailPanelService}>{app.service_name || app.service_id}</div>
        <span className={`status-chip chip-${statusUI.color}`}>
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{statusUI.icon}</span>
          {statusUI.label}
        </span>
        <div className={styles.detailPanelNum}>#{app.application_number}</div>
      </div>

      {/* Progress bar */}
      {progressVal != null && (
        <div className={styles.detailProgress}>
          <div className={styles.detailProgressBar}>
            <div className={styles.detailProgressFill} style={{ width: `${progressVal}%` }} />
          </div>
          <span className={styles.detailProgressLabel}>{progressVal}% complete</span>
        </div>
      )}

      {/* Readiness score */}
      {readiness && (
        <div className={styles.readinessBox}>
          <div className={styles.readinessScore} style={{
            color: readiness.score >= 75 ? 'var(--rg-success)' : readiness.score >= 50 ? 'var(--rg-warning)' : 'var(--rg-error)'
          }}>
            {readiness.score}/100
          </div>
          <div className={styles.readinessLabel}>Readiness Score</div>
          {readiness.blocking_issues?.length > 0 && (
            <div className={styles.readinessIssues}>
              {readiness.blocking_issues.slice(0, 2).map((issue, i) => (
                <div key={i} className={styles.readinessIssue}>
                  <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--rg-error)' }}>error</span>
                  {issue}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Applicant fields */}
      <div className={styles.detailSection}>
        <div className={styles.detailSectionTitle}>Applicant Information</div>
        {fieldsLoading ? (
          <div className={styles.detailLoading}>Loading fields…</div>
        ) : Object.keys(fields).length === 0 ? (
          <p className={styles.detailEmpty}>No fields collected yet. Continue in the Assistant.</p>
        ) : (
          <div className={styles.detailFields}>
            {Object.entries(fields).slice(0, 6).map(([name, data]) => {
              const val = typeof data === 'object' ? data.value : data
              const isSensitive = ['aadhaar', 'pan', 'account'].some(k => name.toLowerCase().includes(k))
              return (
                <div key={name} className={styles.detailField}>
                  <span className={styles.detailFieldLabel}>{name.replace(/_/g, ' ')}</span>
                  <span className={styles.detailFieldValue}>
                    {isSensitive ? `${String(val || '').slice(0, 4)}••••` : (val || '—')}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Documents summary */}
      <div className={styles.detailSection}>
        <div className={styles.detailSectionTitle}>Required Documents</div>
        {docsLoading ? (
          <div className={styles.detailLoading}>Loading documents…</div>
        ) : documents.length === 0 ? (
          <p className={styles.detailEmpty}>No documents uploaded yet.</p>
        ) : (
          <div className={styles.detailDocs}>
            {documents.map(doc => {
              const hasMismatch = doc.mismatch_fields?.length > 0
              const resolved    = hasMismatch && doc.mismatch_fields.every(f => doc.mismatch_resolutions?.[f])
              return (
                <div key={doc.id} className={styles.detailDoc}>
                  <span className="material-symbols-outlined" style={{
                    fontSize: 18,
                    color: doc.verification_status === 'VERIFIED' ? 'var(--rg-success)'
                         : hasMismatch && !resolved ? 'var(--rg-warning)'
                         : 'var(--rg-outline)',
                    fontVariationSettings: "'FILL' 1",
                  }}>
                    {doc.verification_status === 'VERIFIED' ? 'check_circle'
                     : hasMismatch && !resolved ? 'warning'
                     : 'description'}
                  </span>
                  <div className={styles.detailDocInfo}>
                    <span className={styles.detailDocName}>{doc.doc_type?.replace(/_/g, ' ')}</span>
                    {doc.overall_match_score != null && (
                      <span className={styles.detailDocScore}>OCR: {Math.round(doc.overall_match_score)}%</span>
                    )}
                  </div>
                  <button
                    className={styles.viewOCRBtn}
                    onClick={() => onViewDocs(app.id, doc.id)}
                  >
                    View →
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className={styles.detailActions}>
        {(app.status === 'PAYMENT_REQUIRED' || app.status === 'PAYMENT_PENDING') && (
          <button
            className={styles.submitBtn}
            style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)' }}
            onClick={onPayFee}
            disabled={paying}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>payments</span>
            {paying ? 'Processing Payment…' : 'Pay Statutory Fee (₹50)'}
          </button>
        )}
        {canSubmit && (
          <button
            className={styles.submitBtn}
            onClick={onSubmit}
            disabled={submitting}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>send</span>
            {submitting ? 'Submitting…' : 'Send for Verification'}
          </button>
        )}
        {(app.status === 'APPROVED' || app.status === 'PAYMENT_COMPLETED' || app.status === 'CERTIFICATE_READY' || app.status === 'COMPLETED') && (
          <button
            className={styles.downloadBtn}
            onClick={() => {
              window.open(`/api/v1/applications/${app.application_number}/certificate`, '_blank')
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>download</span>
            Download Certificate
          </button>
        )}
        <button
          className={styles.assistBtn}
          onClick={() => navigate('/assistant')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>smart_toy</span>
          Continue in Assistant
        </button>
      </div>
    </div>
  )
}

/* ── Main Page ── */
export default function MyApplicationsPage() {
  const navigate     = useNavigate()
  const queryClient  = useQueryClient()
  const { citizenUser } = useAuthStore()
  const citizenIdentifier = useChatStore(s => s.citizenIdentifier) || citizenUser?.citizen_ref || localStorage.getItem('citizen_identifier')
  const { setRightPanel, clearRightPanel } = useRightPanel()

  const [filter,       setFilter]       = useState('All Applications')
  const [selectedId,   setSelectedId]   = useState(null)
  const [submitting,   setSubmitting]   = useState(false)
  const [paying,       setPaying]       = useState(false)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['myApplications', citizenIdentifier],
    queryFn:  () => applicationsApi.getMyApplications(citizenIdentifier),
    enabled:  true,
  })

  const applications = data?.applications || []

  // Apply filter
  const activeGroups = FILTER_GROUPS[filter]
  const filtered = activeGroups
    ? applications.filter(a => {
        const ui = getStatusUI(a.status)
        return activeGroups.includes(ui.group)
      })
    : applications

  // Count in-progress
  const inProgressCount = applications.filter(a =>
    ['in_progress', 'action'].includes(getStatusUI(a.status).group)
  ).length

  // Auto-select first application
  useEffect(() => {
    if (applications.length > 0 && !selectedId) {
      setSelectedId(applications[0].id)
    }
  }, [applications])

  const selectedApp = filtered.find(a => a.id === selectedId) || filtered[0] || null

  // View docs navigation
  const handleViewDocs = useCallback((appId, docId) => {
    navigate(`/documents?appId=${appId}&docId=${docId}`)
  }, [navigate])

  // Submit for verification
  const handleSubmit = useCallback(async () => {
    if (!selectedApp) return
    setSubmitting(true)
    try {
      await documentsApi.submitForVerification(selectedApp.id)
      toast.success('Application submitted for verification!')
      queryClient.invalidateQueries(['myApplications'])
      queryClient.invalidateQueries(['documents', selectedApp.id])
      refetch()
    } catch (err) {
      toast.error(err.message || 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }, [selectedApp, queryClient, refetch])

  // Pay fee
  const handlePayFee = useCallback(async () => {
    if (!selectedApp) return
    setPaying(true)
    try {
      const citizenId = citizenUser?.phone || citizenUser?.identifier || selectedApp.citizen_ref || 'CITIZEN'
      await applicationsApi.initiatePayment(selectedApp.id, citizenId, 50.0)
      toast.success('Payment completed successfully! Certificate generated.')
      queryClient.invalidateQueries(['myApplications'])
      queryClient.invalidateQueries(['documents', selectedApp.id])
      refetch()
    } catch (err) {
      toast.error(err.message || 'Payment failed')
    } finally {
      setPaying(false)
    }
  }, [selectedApp, citizenUser, queryClient, refetch])

  // Inject right panel
  useEffect(() => {
    if (selectedApp) {
      setRightPanel(
        'Application Details',
        <ApplicationDetailPanel
          app={selectedApp}
          onViewDocs={handleViewDocs}
          onSubmit={handleSubmit}
          submitting={submitting}
          onPayFee={handlePayFee}
          paying={paying}
        />
      )
    } else {
      clearRightPanel()
    }
  }, [selectedApp?.id, submitting, paying, handlePayFee])

  useEffect(() => () => clearRightPanel(), [])

  const formatDate = d => d
    ? new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : '—'

  const formatService = app => {
    const raw = typeof app.service_name === 'object'
      ? (app.service_name?.en || Object.values(app.service_name || {})[0] || app.service_id || '')
      : (app.service_name || (app.service_id || '').replace(/_/g, ' '))
    return String(raw)
      .split(' ')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(' ')
  }

  return (
    <div className={styles.page}>
      {/* Page Header */}
      <header className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>My Applications</h1>
          <p className={styles.pageSub}>Track and manage your ongoing service requests</p>
        </div>
        <Link to="/assistant" className={styles.newAppBtn}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
          New Application
        </Link>
      </header>

      {/* Filter Pills */}
      <div className={styles.filterBar}>
        {Object.keys(FILTER_GROUPS).map(f => (
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

      {/* Error */}
      {error && (
        <div className={styles.errorBox}>
          <span className="material-symbols-outlined">error</span>
          {error.message || 'Failed to load applications.'}
          <button onClick={() => refetch()}>Retry</button>
        </div>
      )}

      {/* Application List */}
      {isLoading ? (
        <div className={styles.cardList}>
          {[1,2,3].map(i => (
            <div key={i} className="skeleton" style={{ height: 120, borderRadius: 20 }} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className={styles.emptyState}>
          <span className="material-symbols-outlined" style={{ fontSize: 56, color: 'var(--rg-outline-variant)' }}>
            assignment
          </span>
          <h3 className={styles.emptyTitle}>No Applications Found</h3>
          <p className={styles.emptyDesc}>Start a new application via the AI Assistant.</p>
          <Link to="/assistant" className={styles.startBtn}>
            <span className="material-symbols-outlined">add</span>
            Start New Application
          </Link>
        </div>
      ) : (
        <div className={styles.cardList}>
          {filtered.map(app => {
            const statusUI  = getStatusUI(app.status)
            const progressVal = (app.progress_percent != null && app.progress_percent > 0) ? app.progress_percent : statusUI.progress
            const icon      = SERVICE_ICONS[app.service_id] || 'description'
            const isSelected = app.id === selectedId

            return (
              <div
                key={app.id}
                className={`${styles.card} ${isSelected ? styles.cardSelected : ''}`}
                onClick={() => setSelectedId(app.id)}
              >
                {/* Card top */}
                <div className={styles.cardTop}>
                  <div className={styles.cardIconWrap}>
                    <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
                      {icon}
                    </span>
                  </div>
                  <div className={styles.cardInfo}>
                    <div className={styles.cardTitle}>{formatService(app)}</div>
                    <div className={styles.cardMeta}>
                      #{app.application_number}
                      {app.submitted_at && ` · Submitted ${formatDate(app.submitted_at)}`}
                    </div>
                  </div>
                  <span className={`status-chip chip-${statusUI.color}`}>
                    {statusUI.label}
                  </span>
                </div>

                {/* Progress bar */}
                {progressVal != null && (
                  <div className={styles.cardProgressWrap}>
                    <div className={styles.cardProgressBar}>
                      <div
                        className={styles.cardProgressFill}
                        style={{
                          width: `${progressVal}%`,
                          background: statusUI.color === 'success' ? 'var(--rg-success)'
                            : statusUI.color === 'warning'  ? 'var(--rg-warning)'
                            : statusUI.color === 'error'    ? 'var(--rg-error)'
                            : 'var(--rg-primary)',
                        }}
                      />
                    </div>
                    <span className={styles.cardProgressPct}>{progressVal}%</span>
                  </div>
                )}

                {/* Timeline */}
                <TimelineSteps status={app.status} />

                {/* Action notice */}
                {(app.status === 'PAYMENT_REQUIRED' || app.status === 'PAYMENT_PENDING') && (
                  <div
                    className={styles.actionNotice}
                    style={{ background: '#ecfdf5', borderColor: '#10b981', cursor: 'pointer' }}
                    onClick={(e) => { e.stopPropagation(); setSelectedId(app.id) }}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 18, color: '#059669' }}>
                      payments
                    </span>
                    <span style={{ color: '#065f46', fontWeight: 600 }}>
                      🎉 Application Approved! Click to pay statutory fee (₹50) & download certificate
                    </span>
                  </div>
                )}
                {app.status === 'CLARIFICATION_REQUIRED' && (
                  <div className={styles.actionNotice}>
                    <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--rg-warning)' }}>
                      warning
                    </span>
                    <span>Clarification required from officer review</span>
                  </div>
                )}
                {(app.status === 'CERTIFICATE_READY' || app.status === 'COMPLETED') && (
                  <div className={styles.actionNotice} style={{ background: '#ecfdf5', borderColor: '#10b981' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: 16, color: '#059669' }}>
                      verified
                    </span>
                    <span style={{ color: '#065f46', fontWeight: 600 }}>
                      Official Certificate Issued & Ready for Download
                    </span>
                  </div>
                )}

                {/* View details */}
                <div className={styles.cardFooter}>
                  <button className={styles.viewBtn} onClick={e => { e.stopPropagation(); setSelectedId(app.id) }}>
                    View Details
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>chevron_right</span>
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
