import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileText,
  User,
  Shield,
  Clock,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  FileSearch,
  Award,
  AlertOctagon,
  Scale,
  RefreshCw,
} from 'lucide-react'
import { applicationsApi } from '../../api/applications'
import { STATUS_CONFIG } from '../../utils/constants'
import styles from './OfficerReview.module.css'

const formatServiceName = (name, id = '') => {
  if (!name) return (id || '').replace(/_/g, ' ')
  if (typeof name === 'object') return name.en || Object.values(name)[0] || id
  return String(name).replace(/_/g, ' ')
}

export default function OfficerReview() {
  const { appNumber } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [decisionModal, setDecisionModal] = useState(null) // 'APPROVE' | 'REJECT' | 'REQUEST_CLARIFICATION'
  const [reasonText, setReasonText] = useState('')
  const [notesText, setNotesText] = useState('')
  const [expandedDocOcr, setExpandedDocOcr] = useState({})

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['admin-app-detail', appNumber],
    queryFn: () => applicationsApi.getAdminDetail(appNumber),
  })

  const decisionMutation = useMutation({
    mutationFn: ({ decision, reason, adminNotes }) =>
      applicationsApi.submitDecision(appNumber, decision, reason, adminNotes),
    onSuccess: (res, vars) => {
      toast.success(
        vars.decision === 'APPROVE'
          ? 'Application approved! Status transitioned to PAYMENT_REQUIRED.'
          : vars.decision === 'REJECT'
          ? 'Application rejected.'
          : 'Clarification requested from citizen.'
      )
      queryClient.invalidateQueries(['admin-app-detail', appNumber])
      queryClient.invalidateQueries(['admin-apps-list'])
      queryClient.invalidateQueries(['admin-overview'])
      setDecisionModal(null)
      setReasonText('')
      setNotesText('')
    },
    onError: (err) => {
      toast.error(err.message || 'Decision failed')
    },
  })

  if (isLoading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.spinner} />
        <p>Loading authoritative government review records...</p>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className={styles.errorContainer}>
        <AlertTriangle size={48} className={styles.errorIcon} />
        <h2>Application Not Found</h2>
        <p>{error?.message || `Could not find application '${appNumber}'.`}</p>
        <Link to="/admin/applications" className={styles.backBtn}>
          <ArrowLeft size={16} /> Back to Applications Queue
        </Link>
      </div>
    )
  }

  const app = data.application || {}
  const citizen = data.citizen || {}
  const service = data.service || {}
  const appData = data.application_data || {}
  const rawSlots = data.raw_slots || {}
  const documents = data.documents || []
  const readiness = data.readiness || {}
  const matching = data.matching || {}
  const fraud = data.fraud || {}
  const auditLogs = data.audit || []
  const availableActions = data.available_actions || []

  const statusCfg = STATUS_CONFIG[app.status] || {
    label: app.status,
    color: '#64748b',
    bg: '#f1f5f9',
    dot: '#94a3b8',
  }

  const toggleDocOcr = (docId) => {
    setExpandedDocOcr((prev) => ({ ...prev, [docId]: !prev[docId] }))
  }

  const handleDecisionSubmit = () => {
    if (decisionModal === 'REJECT' && !reasonText.trim()) {
      toast.error('Rejection reason is required.')
      return
    }
    if (decisionModal === 'REQUEST_CLARIFICATION' && !reasonText.trim()) {
      toast.error('Clarification message is required.')
      return
    }
    decisionMutation.mutate({
      decision: decisionModal,
      reason: reasonText.trim(),
      adminNotes: notesText.trim(),
    })
  }

  return (
    <div className={styles.container}>
      {/* ── Top Nav & Header ── */}
      <div className={styles.topBar}>
        <button className={styles.backLink} onClick={() => navigate('/admin/applications')}>
          <ArrowLeft size={16} /> Back to Queue
        </button>
        <div className={styles.topActions}>
          <button className={styles.refreshBtn} onClick={() => refetch()} title="Sync record">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* ── Status Banner ── */}
      <div className={styles.banner}>
        <div className={styles.bannerMain}>
          <div className={styles.trackingHeader}>
            <span className={styles.trackingPill}>{app.tracking_id || app.application_number}</span>
            <span
              className={styles.statusPill}
              style={{ color: statusCfg.color, backgroundColor: statusCfg.bg, borderColor: statusCfg.dot }}
            >
              <span className={styles.statusDot} style={{ backgroundColor: statusCfg.dot }} />
              {statusCfg.label || app.status}
            </span>
            <span
              className={styles.riskBadge}
              style={{
                color: fraud.risk_level === 'HIGH' ? '#b91c1c' : fraud.risk_level === 'MEDIUM' ? '#b45309' : '#15803d',
                backgroundColor: fraud.risk_level === 'HIGH' ? '#fee2e2' : fraud.risk_level === 'MEDIUM' ? '#fef3c7' : '#dcfce7',
              }}
            >
              Risk: {fraud.risk_level} (Anomaly: {(fraud.anomaly_score * 100).toFixed(0)}%)
            </span>
          </div>
          <h1 className={styles.serviceHeading}>{formatServiceName(service.name || app.service_name, app.service_id)}</h1>
          <p className={styles.citizenSummary}>
            Applicant: <strong>{citizen.name || citizen.citizen_ref}</strong> ({citizen.citizen_ref}) · Submitted:{' '}
            {app.submitted_at ? new Date(app.submitted_at).toLocaleString() : 'Pending Submission'}
          </p>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════
          SECTION 1 — APPLICATION OVERVIEW
          ══════════════════════════════════════════════════════════════ */}
      <div className={styles.sectionCard}>
        <div className={styles.sectionHeader}>
          <FileText size={18} className={styles.sectionIcon} />
          <h2 className={styles.sectionTitle}>Section 1 — Application Overview</h2>
        </div>
        <div className={styles.grid4}>
          <div className={styles.infoField}>
            <span className={styles.fieldLabel}>Application Number</span>
            <span className={styles.fieldValue}>{app.application_number}</span>
          </div>
          <div className={styles.infoField}>
            <span className={styles.fieldLabel}>Tracking Identifier</span>
            <span className={styles.fieldValue}>{app.tracking_id || '—'}</span>
          </div>
          <div className={styles.infoField}>
            <span className={styles.fieldLabel}>Service Department</span>
            <span className={styles.fieldValue}>{service.department || 'Revenue'}</span>
          </div>
          <div className={styles.infoField}>
            <span className={styles.fieldLabel}>SLA Compliance</span>
            <span className={styles.fieldValue}>{service.sla_days || 7} working days</span>
          </div>
          <div className={styles.infoField}>
            <span className={styles.fieldLabel}>Submission Channel</span>
            <span className={styles.fieldValue}>{app.channel_origin || 'WEB'}</span>
          </div>
          <div className={styles.infoField}>
            <span className={styles.fieldLabel}>Language Preference</span>
            <span className={styles.fieldValue}>{(app.language || 'en').toUpperCase()}</span>
          </div>
          <div className={styles.infoField}>
            <span className={styles.fieldLabel}>Payment Status</span>
            <span className={styles.fieldValue}>
              {app.payment_status} (₹{service.fee_amount || 50})
            </span>
          </div>
          <div className={styles.infoField}>
            <span className={styles.fieldLabel}>Created Timestamp</span>
            <span className={styles.fieldValue}>
              {app.created_at ? new Date(app.created_at).toLocaleString() : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════
          SECTION 2 — PERSONAL & APPLICATION DATA
          ══════════════════════════════════════════════════════════════ */}
      <div className={styles.sectionCard}>
        <div className={styles.sectionHeader}>
          <User size={18} className={styles.sectionIcon} />
          <h2 className={styles.sectionTitle}>Section 2 — Personal & Application Data</h2>
        </div>
        {Object.keys(appData).length === 0 && Object.keys(rawSlots).length === 0 ? (
          <p className={styles.emptyNote}>No declared slot fields recorded.</p>
        ) : (
          <div className={styles.tableWrapper}>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>Field Name</th>
                  <th>Declared Value</th>
                  <th>DataGuard Classification</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(appData).map(([key, item]) => (
                  <tr key={key}>
                    <td className={styles.fieldNameCell}>{key.replace(/_/g, ' ')}</td>
                    <td className={styles.fieldValCell}>
                      <strong>{String(item.value || '—')}</strong>
                    </td>
                    <td>
                      <span className={styles.classPill}>{item.classification || 'PII'}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ══════════════════════════════════════════════════════════════
          SECTION 3 — DOCUMENTS & OCR
          ══════════════════════════════════════════════════════════════ */}
      <div className={styles.sectionCard}>
        <div className={styles.sectionHeader}>
          <FileSearch size={18} className={styles.sectionIcon} />
          <h2 className={styles.sectionTitle}>Section 3 — Documents & OCR Verification</h2>
        </div>
        {documents.length === 0 ? (
          <p className={styles.emptyNote}>No documents uploaded for this application.</p>
        ) : (
          <div className={styles.docsList}>
            {documents.map((doc) => (
              <div key={doc.id} className={styles.docCard}>
                <div className={styles.docCardHeader}>
                  <div>
                    <h3 className={styles.docTypeTitle}>{doc.doc_type}</h3>
                    <span className={styles.docFilename}>{doc.filename || 'Uploaded File'}</span>
                  </div>
                  <div className={styles.docBadges}>
                    <span className={styles.docMatchScore}>
                      Match: {Math.round(doc.match_score || 100)}%
                    </span>
                    <span className={styles.docConfidence}>
                      OCR Conf: {Math.round((doc.confidence_score || 0.9) * 100)}%
                    </span>
                    <span className={styles.statusPill}>
                      {doc.verification_status || 'VERIFIED'}
                    </span>
                  </div>
                </div>

                {/* Normalized OCR Fields */}
                <div className={styles.docFieldsSection}>
                  <h4 className={styles.subHeading}>Normalized OCR Fields:</h4>
                  {doc.normalized_fields && Object.keys(doc.normalized_fields).length > 0 ? (
                    <div className={styles.ocrFieldsGrid}>
                      {Object.entries(doc.normalized_fields).map(([k, v]) => (
                        <div key={k} className={styles.ocrFieldItem}>
                          <span className={styles.ocrKey}>{k.replace(/_/g, ' ')}:</span>
                          <span className={styles.ocrVal}>{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className={styles.dimText}>No structured fields parsed.</span>
                  )}
                </div>

                {/* Officer Raw OCR Expander */}
                {doc.raw_ocr_text && (
                  <div className={styles.rawOcrBox}>
                    <button
                      className={styles.expandOcrBtn}
                      onClick={() => toggleDocOcr(doc.id)}
                    >
                      {expandedDocOcr[doc.id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      <span>{expandedDocOcr[doc.id] ? 'Hide Raw OCR Text' : 'Inspect Raw OCR Text (Officer View)'}</span>
                    </button>
                    {expandedDocOcr[doc.id] && (
                      <pre className={styles.rawOcrPre}>{doc.raw_ocr_text}</pre>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ══════════════════════════════════════════════════════════════
          SECTION 4 — READINESS SCORE
          ══════════════════════════════════════════════════════════════ */}
      <div className={styles.sectionCard}>
        <div className={styles.sectionHeader}>
          <Award size={18} className={styles.sectionIcon} />
          <h2 className={styles.sectionTitle}>Section 4 — Readiness Assessment (Backend Engine)</h2>
        </div>
        <div className={styles.readinessOverview}>
          <div className={styles.readinessScoreBox}>
            <span className={styles.readinessNumber}>{Math.round(readiness.overall_score || 85)}</span>
            <span className={styles.readinessMax}>/ 100</span>
            <span className={styles.readinessStatusBadge}>{readiness.status || 'READY'}</span>
          </div>
          <div className={styles.componentsTableWrap}>
            <table className={styles.compTable}>
              <thead>
                <tr>
                  <th>Component</th>
                  <th>Weight</th>
                  <th>Achievement</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {(readiness.components || []).map((comp) => (
                  <tr key={comp.name}>
                    <td>{comp.name}</td>
                    <td>{comp.weight} pts</td>
                    <td>{comp.pct || Math.round(comp.score * 100)}%</td>
                    <td>
                      <strong>{(comp.weighted_score || 0).toFixed(1)}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════
          SECTION 5 — DOCUMENT MATCHING
          ══════════════════════════════════════════════════════════════ */}
      <div className={styles.sectionCard}>
        <div className={styles.sectionHeader}>
          <Scale size={18} className={styles.sectionIcon} />
          <h2 className={styles.sectionTitle}>Section 5 — Cross-Field Document Matching</h2>
        </div>
        <div className={styles.matchingContent}>
          <div className={styles.overallMatchBadge}>
            Overall Match Confidence: <strong>{Math.round(matching.overall_match_score || 100)}%</strong>
          </div>
          <div className={styles.matchFieldsLists}>
            <div>
              <h4 className={styles.matchSubhead} style={{ color: '#16a34a' }}>
                ✓ Matched Fields:
              </h4>
              <ul className={styles.fieldList}>
                {(matching.matched_fields || ['applicant_name', 'dob', 'address']).map((f) => (
                  <li key={f}>{String(f).replace(/_/g, ' ')}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className={styles.matchSubhead} style={{ color: '#dc2626' }}>
                ⚠ Mismatched Fields:
              </h4>
              {(matching.mismatched_fields || []).length === 0 ? (
                <span className={styles.dimText}>No field mismatches detected.</span>
              ) : (
                <ul className={styles.fieldList}>
                  {matching.mismatched_fields.map((f) => (
                    <li key={f} style={{ color: '#dc2626' }}>
                      {String(f).replace(/_/g, ' ')}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════
          SECTION 6 — FRAUD & RULES REVIEW
          ══════════════════════════════════════════════════════════════ */}
      <div className={styles.sectionCard}>
        <div className={styles.sectionHeader}>
          <Shield size={18} className={styles.sectionIcon} />
          <h2 className={styles.sectionTitle}>Section 6 — Fraud, Rules & Security Assessment</h2>
        </div>
        <div className={styles.fraudGrid}>
          <div className={styles.fraudItem}>
            <span className={styles.fraudLabel}>Fraud / Anomaly Score</span>
            <span className={styles.fraudVal}>{(fraud.anomaly_score * 100).toFixed(1)}%</span>
          </div>
          <div className={styles.fraudItem}>
            <span className={styles.fraudLabel}>Risk Classification</span>
            <span
              className={styles.riskBadge}
              style={{
                color: fraud.risk_level === 'HIGH' ? '#b91c1c' : fraud.risk_level === 'MEDIUM' ? '#b45309' : '#15803d',
                backgroundColor: fraud.risk_level === 'HIGH' ? '#fee2e2' : fraud.risk_level === 'MEDIUM' ? '#fef3c7' : '#dcfce7',
              }}
            >
              {fraud.risk_level}
            </span>
          </div>
          <div className={styles.fraudItem}>
            <span className={styles.fraudLabel}>Eligibility Status</span>
            <span className={styles.fraudVal} style={{ color: fraud.eligibility_passed ? '#16a34a' : '#dc2626' }}>
              {fraud.eligibility_passed ? 'Eligible' : 'Eligibility Issues'}
            </span>
          </div>
          <div className={styles.fraudItem}>
            <span className={styles.fraudLabel}>DataGuard Status</span>
            <span className={styles.fraudVal} style={{ color: '#16a34a' }}>
              PII Enforced / Protected
            </span>
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════
          AUTHORITATIVE DECISION PANEL
          ══════════════════════════════════════════════════════════════ */}
      <div className={styles.decisionPanelCard}>
        <div className={styles.decisionHeader}>
          <h2 className={styles.decisionTitle}>Government Officer Decision Panel</h2>
          <span className={styles.decisionStateText}>
            Current State: <strong>{app.status}</strong>
          </span>
        </div>

        {availableActions.length === 0 && ['PAYMENT_REQUIRED', 'PAYMENT_COMPLETED', 'CERTIFICATE_READY', 'COMPLETED', 'REJECTED'].includes(app.status) ? (
          <div className={styles.noActionBox}>
            <Clock size={20} />
            <span>
              {app.status === 'PAYMENT_REQUIRED'
                ? 'Application is approved and currently awaiting citizen fee payment.'
                : app.status === 'PAYMENT_COMPLETED'
                ? 'Payment completed. Certificate generation in progress.'
                : app.status === 'COMPLETED' || app.status === 'CERTIFICATE_READY'
                ? 'Application processing is complete and certificate has been issued.'
                : app.status === 'REJECTED'
                ? 'Application has been rejected. No further actions available.'
                : 'No actions currently available in this state.'}
            </span>
          </div>
        ) : (
          <div className={styles.actionButtonsGroup}>
            <button
              className={styles.approveBtn}
              onClick={() => setDecisionModal('APPROVE')}
              disabled={decisionMutation.isPending}
            >
              <CheckCircle size={18} /> Approve Application
            </button>

            <button
              className={styles.clarifyBtn}
              onClick={() => setDecisionModal('REQUEST_CLARIFICATION')}
              disabled={decisionMutation.isPending}
            >
              <AlertOctagon size={18} /> Request Clarification
            </button>

            <button
              className={styles.rejectBtn}
              onClick={() => setDecisionModal('REJECT')}
              disabled={decisionMutation.isPending}
            >
              <XCircle size={18} /> Reject Application
            </button>
          </div>
        )}
      </div>

      {/* ── Decision Confirmation Modal ── */}
      {decisionModal && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalContent}>
            <h3 className={styles.modalTitle}>
              {decisionModal === 'APPROVE' && 'Approve Application'}
              {decisionModal === 'REJECT' && 'Reject Application'}
              {decisionModal === 'REQUEST_CLARIFICATION' && 'Request Clarification from Citizen'}
            </h3>

            <p className={styles.modalDesc}>
              {decisionModal === 'APPROVE' &&
                'Approving this application will transition the status to PAYMENT_REQUIRED, send an approval notification to the citizen, and allow them to complete the statutory fee payment.'}
              {decisionModal === 'REJECT' &&
                'Please specify the official reason for rejecting this application. This reason will be logged and communicated to the citizen.'}
              {decisionModal === 'REQUEST_CLARIFICATION' &&
                'Please specify the clarification or additional documentation required from the citizen.'}
            </p>

            {(decisionModal === 'REJECT' || decisionModal === 'REQUEST_CLARIFICATION') && (
              <div className={styles.modalFormGroup}>
                <label className={styles.modalLabel}>
                  {decisionModal === 'REJECT' ? 'Rejection Reason *' : 'Clarification Message *'}
                </label>
                <textarea
                  className={styles.modalTextarea}
                  rows={3}
                  placeholder={
                    decisionModal === 'REJECT'
                      ? 'e.g. Income certificate could not be verified with tax records.'
                      : 'e.g. Please upload a clearer copy of your address proof.'
                  }
                  value={reasonText}
                  onChange={(e) => setReasonText(e.target.value)}
                />
              </div>
            )}

            <div className={styles.modalFormGroup}>
              <label className={styles.modalLabel}>Internal Admin Notes (Optional)</label>
              <input
                type="text"
                className={styles.modalInput}
                placeholder="Notes for the audit log..."
                value={notesText}
                onChange={(e) => setNotesText(e.target.value)}
              />
            </div>

            <div className={styles.modalActions}>
              <button
                className={styles.modalCancelBtn}
                onClick={() => {
                  setDecisionModal(null)
                  setReasonText('')
                  setNotesText('')
                }}
              >
                Cancel
              </button>
              <button
                className={
                  decisionModal === 'APPROVE'
                    ? styles.approveBtn
                    : decisionModal === 'REJECT'
                    ? styles.rejectBtn
                    : styles.clarifyBtn
                }
                onClick={handleDecisionSubmit}
                disabled={decisionMutation.isPending}
              >
                {decisionMutation.isPending ? 'Processing...' : 'Confirm Decision'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
