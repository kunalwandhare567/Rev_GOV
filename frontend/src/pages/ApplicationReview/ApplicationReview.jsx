import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  CheckCircle, AlertCircle, XCircle, FileText, User,
  CreditCard, ChevronRight, Edit2, RefreshCw, Download,
  Shield, Clock, Phone, MessageSquare, Globe
} from 'lucide-react'
import toast from 'react-hot-toast'
import styles from './ApplicationReview.module.css'

const API = 'http://localhost:8000/api/v1'

const STATUS_CONFIG = {
  DRAFT:                      { color: '#94a3b8', icon: '📝', label: 'Draft' },
  INFORMATION_COLLECTION:     { color: '#f59e0b', icon: '📋', label: 'Collecting Info' },
  DOCUMENT_COLLECTION:        { color: '#f59e0b', icon: '📁', label: 'Collecting Docs' },
  OCR_VALIDATION:             { color: '#6366f1', icon: '🔍', label: 'Validating Docs' },
  FINAL_REVIEW:               { color: '#06b6d4', icon: '👁️', label: 'Ready for Review' },
  SUBMITTED_FOR_VERIFICATION: { color: '#8b5cf6', icon: '📤', label: 'Submitted' },
  UNDER_REVIEW:               { color: '#f59e0b', icon: '⚖️', label: 'Government Review' },
  CLARIFICATION_REQUIRED:     { color: '#ef4444', icon: '⚠️', label: 'Clarification Needed' },
  APPROVED:                   { color: '#10b981', icon: '✅', label: 'Approved' },
  PAYMENT_REQUIRED:           { color: '#f59e0b', icon: '💳', label: 'Payment Required' },
  PAYMENT_COMPLETED:          { color: '#06b6d4', icon: '💰', label: 'Payment Done' },
  COMPLETED:                  { color: '#22c55e', icon: '🏆', label: 'Completed' },
  REJECTED:                   { color: '#ef4444', icon: '❌', label: 'Rejected' },
}

const CHANNEL_ICONS = { WHATSAPP: '💬', WEB: '🌐', MOBILE: '📱', IVR: '📞', SYSTEM: '⚙️' }

function getScoreColor(score) {
  if (score >= 90) return '#22c55e'
  if (score >= 70) return '#f59e0b'
  return '#ef4444'
}

function ScoreRing({ score, size = 64 }) {
  const r = size / 2 - 6
  const circumference = 2 * Math.PI * r
  const progress = circumference - (score / 100) * circumference
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={5} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={getScoreColor(score)} strokeWidth={5}
        strokeDasharray={circumference} strokeDashoffset={progress}
        strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
      <text x={size / 2} y={size / 2 + 5} textAnchor="middle" fill={getScoreColor(score)} fontSize={14} fontWeight="700">
        {score}%
      </text>
    </svg>
  )
}

export default function ApplicationReview() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [app, setApp] = useState(null)
  const [fields, setFields] = useState({})
  const [documents, setDocuments] = useState([])
  const [timeline, setTimeline] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeSection, setActiveSection] = useState('overview')
  const [editingField, setEditingField] = useState(null)
  const [editValue, setEditValue] = useState('')

  useEffect(() => { loadApplication() }, [id])

  const loadApplication = async () => {
    setLoading(true)
    try {
      // Fetch by tracking ID (public endpoint) or by application ID
      const endpoint = id.startsWith('APP-') || id.match(/^[A-Z]+-\d+-\d+$/)
        ? `${API}/tracking/${id}`
        : `${API}/applications/${id}`

      const res = await fetch(endpoint)
      if (!res.ok) throw new Error('Not found')
      const data = await res.json()

      setApp(data)
      setTimeline(data.timeline || [])

      // Fetch full fields if we have application_id
      if (data.id || id) {
        const appId = data.id || id
        const fieldsRes = await fetch(`${API}/applications/${appId}/fields`)
        if (fieldsRes.ok) setFields(await fieldsRes.json())

        const docsRes = await fetch(`${API}/applications/${appId}/documents`)
        if (docsRes.ok) setDocuments(await docsRes.json())
      }
    } catch (err) {
      toast.error('Application not found')
    } finally {
      setLoading(false)
    }
  }

  const handleEditField = async (fieldName) => {
    try {
      const res = await fetch(`${API}/applications/${app.id}/fields/${fieldName}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: editValue, source: 'WEB_EDIT' }),
      })
      if (res.ok) {
        setFields(prev => ({ ...prev, [fieldName]: { ...prev[fieldName], value: editValue } }))
        toast.success(`${fieldName.replace(/_/g, ' ')} updated`)
      }
    } catch { toast.error('Update failed') }
    setEditingField(null)
  }

  const handleResolveMismatch = async (docId, fieldName, resolution) => {
    try {
      const res = await fetch(`${API}/applications/${app.id}/documents/${docId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field: fieldName, resolution }),
      })
      if (res.ok) {
        toast.success('Mismatch resolved!')
        loadApplication()
      }
    } catch { toast.error('Failed to resolve') }
  }

  const handleSubmitForVerification = async () => {
    const confirm = window.confirm('Submit this application for government verification? This cannot be undone.')
    if (!confirm) return
    try {
      const res = await fetch(`${API}/applications/${app.id}/submit`, { method: 'POST' })
      if (res.ok) { toast.success('Application submitted for verification!'); loadApplication() }
      else toast.error('Submission failed')
    } catch { toast.error('Server error') }
  }

  if (loading) {
    return (
      <div className={styles.loading}>
        <div className={styles.loadingSpinner} />
        <p>Loading application…</p>
      </div>
    )
  }

  if (!app) {
    return (
      <div className={styles.notFound}>
        <div style={{ fontSize: 64, marginBottom: 16 }}>🔍</div>
        <h2>Application not found</h2>
        <p>The application ID or tracking ID you entered does not exist.</p>
        <button className={styles.primaryBtn} onClick={() => navigate('/')}>Go Home</button>
      </div>
    )
  }

  const statusCfg = STATUS_CONFIG[app.status] || { color: '#94a3b8', icon: '📋', label: app.status }
  const hasMismatches = documents.some(d => d.mismatch_fields?.length > 0)
  const allResolved = documents.every(d =>
    !d.mismatch_fields?.length ||
    d.mismatch_fields.every(f => d.mismatch_resolutions?.[f])
  )

  return (
    <div className={styles.shell}>

      {/* ── TOP HERO BANNER ── */}
      <div className={styles.heroBanner}>
        <div className={styles.heroLeft}>
          <div className={styles.heroIcon}>{statusCfg.icon}</div>
          <div>
            <h1 className={styles.heroTitle}>
              {app.service?.en || app.service_name || 'Certificate Application'}
            </h1>
            <div className={styles.heroMeta}>
              <span className={styles.trackingBadge}>{app.tracking_id || app.application_number}</span>
              <span className={styles.channelBadge}>
                {CHANNEL_ICONS[app.channel_origin]} {app.channel_origin}
              </span>
              {app.last_channel && app.last_channel !== app.channel_origin && (
                <span className={styles.channelBadge}>
                  Last: {CHANNEL_ICONS[app.last_channel]} {app.last_channel}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className={styles.heroRight}>
          <div className={styles.statusPill} style={{ background: `${statusCfg.color}20`, borderColor: `${statusCfg.color}40`, color: statusCfg.color }}>
            {statusCfg.label}
          </div>
          {app.overall_match_score !== undefined && app.overall_match_score !== null && (
            <div className={styles.matchScoreBox}>
              <ScoreRing score={Math.round(app.overall_match_score)} />
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginTop: 4, textAlign: 'center' }}>Match Score</div>
            </div>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className={styles.progressBar}>
        <div className={styles.progressFill} style={{ width: `${app.progress_percent || 0}%` }} />
      </div>

      {/* ── 4 SECTION TABS ── */}
      <div className={styles.sectionTabs}>
        {[
          { id: 'overview', icon: '📊', label: 'Overview' },
          { id: 'fields', icon: '📋', label: 'Application Fields' },
          { id: 'documents', icon: '📁', label: `Documents ${hasMismatches && !allResolved ? '⚠️' : ''}` },
          { id: 'timeline', icon: '🕒', label: 'Timeline' },
        ].map(tab => (
          <button key={tab.id}
            className={`${styles.sectionTab} ${activeSection === tab.id ? styles.active : ''}`}
            onClick={() => setActiveSection(tab.id)}>
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── SECTION CONTENT ── */}
      <div className={styles.sectionContent}>

        {/* SECTION 1: OVERVIEW */}
        {activeSection === 'overview' && (
          <div className={styles.overviewGrid}>

            {/* Status Card */}
            <div className={styles.card}>
              <div className={styles.cardTitle}>Current Status</div>
              <div className={styles.statusDisplay}>
                <div style={{ fontSize: 48 }}>{statusCfg.icon}</div>
                <div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: statusCfg.color }}>{statusCfg.label}</div>
                  <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', marginTop: 4 }}>
                    {app.current_step || 'Processing'}
                  </div>
                </div>
              </div>
              {/* Submit button if ready */}
              {app.status === 'FINAL_REVIEW' && allResolved && (
                <button className={styles.primaryBtn} onClick={handleSubmitForVerification}
                  style={{ marginTop: 16, width: '100%' }}>
                  📤 Submit for Government Verification
                </button>
              )}
            </div>

            {/* Channels Card */}
            <div className={styles.card}>
              <div className={styles.cardTitle}>Channel Journey</div>
              <div className={styles.channelJourney}>
                {[
                  { label: 'Started on', channel: app.channel_origin },
                  { label: 'Last active', channel: app.last_channel },
                ].map((item, i) => item.channel && (
                  <div key={i} className={styles.channelItem}>
                    <div className={styles.channelItemIcon}>{CHANNEL_ICONS[item.channel]}</div>
                    <div>
                      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>{item.label}</div>
                      <div style={{ fontSize: 14, color: '#fff', fontWeight: 500 }}>{item.channel}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div className={styles.channelLinks}>
                <a href="/whatsapp" className={styles.channelLink}><span>💬</span> WhatsApp Chat</a>
                <a href="/ivr" className={styles.channelLink}><span>📞</span> Phone IVR</a>
              </div>
            </div>

            {/* Match Score Card */}
            {app.validation_summary && (
              <div className={styles.card}>
                <div className={styles.cardTitle}>OCR Verification Summary</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                  <ScoreRing score={Math.round(app.overall_match_score || 0)} size={72} />
                  <div>
                    <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.7)' }}>Overall Match</div>
                    <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', marginTop: 4 }}>
                      This is a data match score only.<br />It does not verify authenticity.
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Dates Card */}
            <div className={styles.card}>
              <div className={styles.cardTitle}>Important Dates</div>
              {[
                { label: 'Created', value: app.created_at },
                { label: 'Submitted', value: app.submitted_at },
                { label: 'Approved', value: app.approved_at },
                { label: 'Completed', value: app.completed_at },
              ].filter(d => d.value).map(d => (
                <div key={d.label} className={styles.dateRow}>
                  <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: 13 }}>{d.label}</span>
                  <span style={{ color: '#e2e8f0', fontSize: 13, fontWeight: 500 }}>
                    {new Date(d.value).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SECTION 2: APPLICATION FIELDS */}
        {activeSection === 'fields' && (
          <div className={styles.fieldsGrid}>
            {Object.keys(fields).length === 0 ? (
              <div className={styles.emptyState}>
                <div style={{ fontSize: 48 }}>📋</div>
                <p>No fields collected yet. Continue your conversation in WhatsApp or Web chat.</p>
                <a href="/whatsapp" className={styles.primaryBtn}>Continue in WhatsApp →</a>
              </div>
            ) : (
              Object.entries(fields).map(([fieldName, fieldData]) => {
                const value = typeof fieldData === 'object' ? fieldData.value : fieldData
                const source = typeof fieldData === 'object' ? fieldData.source : 'SYSTEM'
                const confirmed = typeof fieldData === 'object' ? fieldData.confirmed : false
                const isEditing = editingField === fieldName

                return (
                  <div key={fieldName} className={styles.fieldCard}>
                    <div className={styles.fieldHeader}>
                      <div className={styles.fieldLabel}>{fieldName.replace(/_/g, ' ').toUpperCase()}</div>
                      <div className={styles.fieldMeta}>
                        <span className={`${styles.sourceBadge} ${styles[source?.toLowerCase()]}`}>
                          {CHANNEL_ICONS[source] || '⚙️'} {source}
                        </span>
                        {confirmed && <CheckCircle size={14} color="#22c55e" />}
                      </div>
                    </div>

                    {isEditing ? (
                      <div className={styles.fieldEditRow}>
                        <input className={styles.fieldEditInput} value={editValue}
                          onChange={e => setEditValue(e.target.value)} autoFocus />
                        <button className={styles.editSaveBtn} onClick={() => handleEditField(fieldName)}>Save</button>
                        <button className={styles.editCancelBtn} onClick={() => setEditingField(null)}>Cancel</button>
                      </div>
                    ) : (
                      <div className={styles.fieldValueRow}>
                        <span className={styles.fieldValue}>{value || '—'}</span>
                        <button className={styles.editBtn} onClick={() => { setEditingField(fieldName); setEditValue(value || '') }}>
                          <Edit2 size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        )}

        {/* SECTION 3: DOCUMENTS */}
        {activeSection === 'documents' && (
          <div>
            {hasMismatches && !allResolved && (
              <div className={styles.mismatchBanner}>
                <AlertCircle size={20} />
                <div>
                  <div style={{ fontWeight: 600 }}>Action Required: Resolve Document Mismatches</div>
                  <div style={{ fontSize: 13, opacity: 0.8, marginTop: 2 }}>
                    Some fields in your documents don't match your application. Review and resolve each one below.
                  </div>
                </div>
              </div>
            )}

            {documents.length === 0 ? (
              <div className={styles.emptyState}>
                <div style={{ fontSize: 48 }}>📁</div>
                <p>No documents uploaded yet. Upload using the WhatsApp chat or Web chat.</p>
              </div>
            ) : (
              <div className={styles.docsGrid}>
                {documents.map(doc => {
                  const hasMismatch = doc.mismatch_fields?.length > 0
                  return (
                    <div key={doc.id} className={`${styles.docCard} ${hasMismatch ? styles.mismatch : ''}`}>
                      <div className={styles.docCardHeader}>
                        <div className={styles.docTypeIcon}>📄</div>
                        <div style={{ flex: 1 }}>
                          <div className={styles.docTypeName}>{doc.doc_type?.replace(/_/g, ' ')}</div>
                          <div className={styles.docUploadInfo}>
                            {CHANNEL_ICONS[doc.upload_channel]} Uploaded via {doc.upload_channel}
                          </div>
                        </div>
                        {doc.overall_match_score !== undefined && (
                          <ScoreRing score={Math.round(doc.overall_match_score || 0)} size={52} />
                        )}
                      </div>

                      {/* OCR Field Scores */}
                      {doc.field_match_scores && Object.keys(doc.field_match_scores).length > 0 && (
                        <div className={styles.ocrScoreList}>
                          <div className={styles.ocrScoreTitle}>Field Match Scores</div>
                          {Object.entries(doc.field_match_scores).map(([field, data]) => (
                            <div key={field} className={styles.ocrScoreRow}>
                              <span className={styles.ocrField}>{field.replace(/_/g, ' ')}</span>
                              <div className={styles.ocrBarWrap}>
                                <div className={styles.ocrBarTrack}>
                                  <div className={styles.ocrBarFill}
                                    style={{ width: `${data.score}%`, background: getScoreColor(data.score) }} />
                                </div>
                                <span className={styles.ocrScore} style={{ color: getScoreColor(data.score) }}>
                                  {data.score}%
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Mismatch Resolver */}
                      {hasMismatch && doc.mismatch_fields.map(field => {
                        const fieldData = doc.field_match_scores?.[field] || {}
                        const alreadyResolved = doc.mismatch_resolutions?.[field]
                        return (
                          <div key={field} className={`${styles.mismatchResolver} ${alreadyResolved ? styles.resolved : ''}`}>
                            <div className={styles.mismatchHeader}>
                              {alreadyResolved ? <CheckCircle size={14} color="#22c55e" /> : <AlertCircle size={14} color="#ef4444" />}
                              <span>{field.replace(/_/g, ' ').toUpperCase()}</span>
                              {alreadyResolved && <span className={styles.resolvedBadge}>Resolved: {alreadyResolved}</span>}
                            </div>

                            {!alreadyResolved && (
                              <>
                                <div className={styles.mismatchCompare}>
                                  <div className={styles.mismatchSide}>
                                    <div className={styles.mismatchSideLabel}>Your Application</div>
                                    <div className={styles.mismatchSideValue}>{fieldData.app_value || '—'}</div>
                                  </div>
                                  <div className={styles.mismatchDivider}>vs</div>
                                  <div className={styles.mismatchSide}>
                                    <div className={styles.mismatchSideLabel}>Document (OCR)</div>
                                    <div className={styles.mismatchSideValue} style={{ color: '#f87171' }}>{fieldData.ocr_value || '—'}</div>
                                  </div>
                                </div>
                                <div className={styles.mismatchActions}>
                                  <button className={styles.useDocBtn} onClick={() => handleResolveMismatch(doc.id, field, 'USE_OCR')}>
                                    Use Document Value
                                  </button>
                                  <button className={styles.useAppBtn} onClick={() => handleResolveMismatch(doc.id, field, 'USE_APPLICATION')}>
                                    Keep My Value
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        )
                      })}

                      {/* Status badge */}
                      <div className={styles.docStatusRow}>
                        <span className={`${styles.docStatusBadge} ${styles[doc.verification_status?.toLowerCase()]}`}>
                          {doc.verification_status}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* SECTION 4: TIMELINE */}
        {activeSection === 'timeline' && (
          <div className={styles.timelineSection}>
            {timeline.length === 0 ? (
              <div className={styles.emptyState}>
                <div style={{ fontSize: 48 }}>🕒</div>
                <p>No events recorded yet.</p>
              </div>
            ) : (
              <div className={styles.timeline}>
                {timeline.map((event, idx) => (
                  <div key={idx} className={styles.timelineItem}>
                    <div className={styles.timelineDot}>
                      {CHANNEL_ICONS[event.source_channel] || '⚙️'}
                    </div>
                    <div className={styles.timelineContent}>
                      <div className={styles.timelineEvent}>{event.event_type.replace(/_/g, ' ')}</div>
                      <div className={styles.timelineMeta}>
                        <span>{CHANNEL_ICONS[event.source_channel]} {event.source_channel}</span>
                        <span>{new Date(event.timestamp).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── BOTTOM ACTION BAR ── */}
      <div className={styles.actionBar}>
        <div className={styles.actionBarLeft}>
          <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)' }}>
            Last updated: {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        <div className={styles.actionBarRight}>
          <button className={styles.secondaryBtn} onClick={loadApplication}>
            <RefreshCw size={14} /> Refresh
          </button>
          {app.status === 'FINAL_REVIEW' && allResolved && (
            <button className={styles.primaryBtn} onClick={handleSubmitForVerification}>
              📤 Submit for Verification
            </button>
          )}
          {app.status === 'COMPLETED' && (
            <button className={styles.primaryBtn}>
              <Download size={14} /> Download Certificate
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
