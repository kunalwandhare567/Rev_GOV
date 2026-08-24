import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { ArrowLeft, CheckCircle, XCircle, AlertTriangle, RefreshCw } from 'lucide-react'
import { applicationsApi } from '../../api/applications'
import { STATUS_CONFIG } from '../../utils/constants'
import styles from './OfficerReview.module.css'

const TABS = ['details', 'fields', 'documents', 'eligibility', 'payment', 'timeline']

const CHANNEL_META = {
  WHATSAPP: { icon: '💬', color: '#25d366', label: 'WhatsApp' },
  WEB:      { icon: '🌐', color: '#6366f1', label: 'Web Portal' },
  MOBILE:   { icon: '📱', color: '#f59e0b', label: 'Mobile App' },
  IVR:      { icon: '📞', color: '#06b6d4', label: 'Phone IVR' },
  SYSTEM:   { icon: '⚙️', color: '#94a3b8', label: 'System' },
}

function getScoreColor(score) {
  if (!score) return '#94a3b8'
  if (score >= 90) return '#22c55e'
  if (score >= 70) return '#f59e0b'
  return '#ef4444'
}

export default function OfficerReview() {
  const { appNumber } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('details')
  const [rejectReason, setRejectReason] = useState('')
  const [notes, setNotes] = useState('')
  const [confirmAction, setConfirmAction] = useState(null)
  const [sendingNotif, setSendingNotif] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['app-detail', appNumber],
    queryFn: () => applicationsApi.getStatus(appNumber),
  })

  const mutation = useMutation({
    mutationFn: ({ status, note }) => applicationsApi.updateStatus(appNumber, status, note),
    onSuccess: (_, { status }) => {
      toast.success(`Application ${status.toLowerCase()}`)
      queryClient.invalidateQueries(['app-detail', appNumber])
      queryClient.invalidateQueries(['recent-apps'])
      setConfirmAction(null)
      setRejectReason('')
    },
    onError: (err) => toast.error(err.message),
  })

  const handleAction = (action) => {
    if (action === 'REJECTED' && !rejectReason.trim()) {
      toast.error('Please enter a rejection reason')
      return
    }
    mutation.mutate({ status: action, note: action === 'REJECTED' ? rejectReason : notes })
  }

  const sendStatusNotification = async () => {
    setSendingNotif(true)
    try {
      const res = await fetch(`http://localhost:8000/api/v1/whatsapp/notify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          application_number: appNumber,
          event_type: 'STATUS_CHANGED',
          new_status: app.status,
        }),
      })
      if (res.ok) toast.success('📲 WhatsApp notification sent to citizen!')
      else toast.error('Notification failed')
    } catch { toast.error('Notification service unreachable') }
    finally { setSendingNotif(false) }
  }

  // Admin pre-payment document decision (PENDING_OFFICER_PRE_APPROVAL state)
  const adminDocDecision = async (decision) => {
    if (decision === 'REJECT' && !rejectReason.trim()) {
      toast.error('Please enter a rejection reason before rejecting documents')
      return
    }
    try {
      const res = await fetch(`http://localhost:8000/api/v1/conversation/admin-doc-decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          application_id: app?.id || appNumber,
          decision,
          reason: decision === 'REJECT' ? rejectReason : null,
          admin_identifier: 'admin',
        }),
      })
      const result = await res.json()
      if (res.ok && result.success) {
        toast.success(decision === 'APPROVE'
          ? '✅ Documents approved! Citizen notified to pay.'
          : '❌ Documents rejected. Citizen notified to re-upload.')
        queryClient.invalidateQueries(['app-detail', appNumber])
        queryClient.invalidateQueries(['recent-apps'])
        setRejectReason('')
      } else {
        toast.error(result.detail || 'Admin decision failed')
      }
    } catch { toast.error('Could not connect to server') }
  }


  const app = data?.application
  const slots = app?.slots_data || {}
  const docs = app?.documents || []

  if (isLoading) return <div className={styles.loadBox}><RefreshCw size={24} className="anim-spin"/> Loading application…</div>
  if (error || !app) return (
    <div className={styles.errorBox}>
      <XCircle size={48} style={{color:'var(--clr-danger-400)'}}/><p>{error?.message || 'Application not found'}</p>
      <button className={styles.backBtn} onClick={()=>navigate(-1)}>Go Back</button>
    </div>
  )

  const originMeta = CHANNEL_META[app.channel] || CHANNEL_META['SYSTEM']

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <button className={styles.backBtn} onClick={()=>navigate(-1)}><ArrowLeft size={16}/> Back</button>
          <div>
            <h1 className={styles.title}>{app.application_number}</h1>
            {/* Phase 13: Channel badges in header */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
              <span style={{ fontSize: 12, color: '#64748b' }}>{app.service_type?.replace(/_/g,' ').toUpperCase()}</span>
              <span style={{ background: `${originMeta.color}20`, borderRadius: 6, padding: '1px 8px', fontSize: 12, color: originMeta.color, border: `1px solid ${originMeta.color}40` }}>
                {originMeta.icon} Started: {originMeta.label}
              </span>
              {app.last_channel && app.last_channel !== app.channel && (
                <span style={{ fontSize: 12, color: '#94a3b8', background: 'rgba(148,163,184,0.1)', border: '1px solid rgba(148,163,184,0.2)', borderRadius: 6, padding: '1px 8px' }}>
                  Last: {CHANNEL_META[app.last_channel]?.icon} {app.last_channel}
                </span>
              )}
              <span style={{ fontSize: 12, color: '#64748b' }}>{new Date(app.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
        <div className={styles.headerRight}>
          <span className={styles.statusBadge} style={{background:STATUS_CONFIG[app.status]?.bg, color:STATUS_CONFIG[app.status]?.color}}>
            <span className={styles.statusDot} style={{background:STATUS_CONFIG[app.status]?.dot}}/>{app.status}
          </span>
          <span className={styles.scoreTag} style={{color: app.anomaly_score>0.7?'var(--clr-danger-400)':app.anomaly_score>0.4?'var(--clr-warning-400)':'var(--clr-success-400)'}}>
            Risk: {(app.anomaly_score||0).toFixed(2)}
          </span>
          {/* Phase 13: OCR match score in header */}
          {app.overall_match_score != null && (
            <span className={styles.scoreTag} style={{ color: getScoreColor(app.overall_match_score) }}>
              OCR: {Math.round(app.overall_match_score)}%
            </span>
          )}
        </div>
      </div>

      <div className={styles.tabs}>
        {TABS.map(tab => (
          <button key={tab} className={`${styles.tab} ${activeTab===tab?styles.tabActive:''}`}
            onClick={()=>setActiveTab(tab)}>
            {tab.charAt(0).toUpperCase()+tab.slice(1)}
          </button>
        ))}
      </div>

      <div className={styles.contentGrid}>
        <div className={styles.tabContent}>

          {/* TAB: DETAILS */}
          {activeTab === 'details' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Application Details</h3>
              <div className={styles.detailGrid}>
                {[
                  ['Service', app.service_type?.replace(/_/g,' ')],
                  ['Language', app.language?.toUpperCase()],
                  ['Citizen Ref', app.citizen_ref || '[TOKENIZED]'],
                  ['Submitted', new Date(app.created_at).toLocaleString()],
                  ['Literacy Level', app.literacy_level || '—'],
                ].map(([k,v]) => (
                  <div key={k} className={styles.detailItem}>
                    <span className={styles.detailKey}>{k}</span>
                    <span className={styles.detailVal}>{v || '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB: FIELDS — Phase 13 provenance */}
          {activeTab === 'fields' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Collected Fields <small style={{color:'#64748b',fontWeight:400,fontSize:13}}>— with channel provenance</small></h3>
              {Object.keys(slots).length === 0
                ? <p className={styles.noData}>No fields collected yet.</p>
                : (
                  <div className={styles.detailGrid}>
                    {Object.entries(slots).map(([k, v]) => {
                      const value = typeof v === 'object' ? v.value : v
                      const source = typeof v === 'object' ? v.source : 'WEB'
                      const confirmed = typeof v === 'object' ? v.confirmed : false
                      const ch = CHANNEL_META[source] || CHANNEL_META['SYSTEM']
                      return (
                        <div key={k} className={styles.detailItem}>
                          <span className={styles.detailKey}>{k.replace(/_/g,' ')}</span>
                          <div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap'}}>
                            <span className={styles.detailVal}>{String(value||'—')}</span>
                            <span style={{background:`${ch.color}15`,border:`1px solid ${ch.color}30`,color:ch.color,borderRadius:4,padding:'1px 6px',fontSize:10,fontWeight:600}}>
                              {ch.icon} {source}
                            </span>
                            {confirmed && <CheckCircle size={12} color="#22c55e"/>}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
            </div>
          )}

          {/* TAB: DOCUMENTS — Phase 13 OCR scores */}
          {activeTab === 'documents' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Documents & OCR Verification</h3>
              {docs.length === 0 ? <p className={styles.noData}>No documents uploaded yet.</p> : (
                <div className={styles.docList}>
                  {docs.map((doc, i) => (
                    <div key={i} style={{background:'var(--clr-dark-800,#1e293b)',borderRadius:8,padding:12,marginBottom:8}}>
                      <div style={{display:'flex',gap:12,alignItems:'center'}}>
                        <span style={{fontSize:24}}>📄</span>
                        <div style={{flex:1}}>
                          <p className={styles.docType}>{doc.doc_type?.replace(/_/g,' ')}</p>
                          <p className={styles.docMeta}>
                            {doc.filename || 'document'} ·
                            <span style={{marginLeft:4}}>
                              {CHANNEL_META[doc.upload_channel]?.icon || '🌐'} {doc.upload_channel || 'WEB'}
                            </span>
                          </p>
                        </div>
                        {/* Phase 13: OCR score circle */}
                        {doc.overall_match_score != null && (
                          <div style={{textAlign:'right'}}>
                            <div style={{fontSize:20,fontWeight:700,color:getScoreColor(doc.overall_match_score)}}>
                              {Math.round(doc.overall_match_score)}%
                            </div>
                            <div style={{fontSize:10,color:'#64748b'}}>OCR Match</div>
                          </div>
                        )}
                        <span style={{fontSize:11,fontWeight:600,padding:'2px 8px',borderRadius:6,
                          background:doc.verification_status==='MATCHED'?'#22c55e20':doc.verification_status==='REVIEW_REQUIRED'?'#ef444420':'#f59e0b20',
                          color:doc.verification_status==='MATCHED'?'#22c55e':doc.verification_status==='REVIEW_REQUIRED'?'#ef4444':'#f59e0b',
                        }}>
                          {doc.verification_status}
                        </span>
                      </div>

                      {/* Mismatch alert */}
                      {doc.mismatch_fields?.length > 0 && (
                        <div style={{background:'#ef444410',border:'1px solid #ef444430',borderRadius:8,padding:'8px 12px',marginTop:8}}>
                          <div style={{fontSize:12,color:'#ef4444',fontWeight:600,marginBottom:4}}>⚠️ Mismatched fields:</div>
                          {doc.mismatch_fields.map(f => (
                            <div key={f} style={{fontSize:12,color:'#94a3b8',display:'flex',justifyContent:'space-between'}}>
                              <span>{f.replace(/_/g,' ')}</span>
                              <span style={{color:'#ef4444'}}>OCR: {doc.extracted_fields?.[f] || '?'}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Field score bars */}
                      {doc.field_match_scores && Object.keys(doc.field_match_scores).length > 0 && (
                        <div style={{marginTop:8}}>
                          {Object.entries(doc.field_match_scores).map(([field, scoreData]) => {
                            const score = typeof scoreData === 'object' ? scoreData.score : scoreData
                            return (
                              <div key={field} style={{display:'flex',alignItems:'center',gap:8,marginBottom:4}}>
                                <span style={{fontSize:11,color:'#64748b',width:140,flexShrink:0}}>{field.replace(/_/g,' ')}</span>
                                <div style={{flex:1,height:6,background:'#334155',borderRadius:3,overflow:'hidden'}}>
                                  <div style={{height:'100%',width:`${score}%`,background:getScoreColor(score),borderRadius:3,transition:'width 0.5s'}}/>
                                </div>
                                <span style={{fontSize:11,fontWeight:700,color:getScoreColor(score),width:36,textAlign:'right'}}>{score}%</span>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'eligibility' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Eligibility Check Results</h3>
              <p className={styles.noData}>Eligibility evaluated automatically during submission.</p>
            </div>
          )}

          {activeTab === 'payment' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Payment Information</h3>
              <div className={styles.detailGrid}>
                {[
                  ['Payment Status', app.payment_status],
                  ['Amount Paid', app.fee_paid_amount !== undefined ? `₹${app.fee_paid_amount}` : '—'],
                  ['Transaction Ref', app.payment_reference || '—'],
                ].map(([k,v])=>(
                  <div key={k} className={styles.detailItem}>
                    <span className={styles.detailKey}>{k}</span>
                    <span className={styles.detailVal}>{String(v||'—')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'timeline' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Application Timeline</h3>
              <p className={styles.noData}>Full timeline available on citizen review page.</p>
              <a href={`/tracking/${app.application_number}`} target="_blank" rel="noopener noreferrer"
                style={{color:'var(--clr-primary-400)',fontSize:13,marginTop:8,display:'block'}}>
                View full timeline →
              </a>
            </div>
          )}
        </div>

        {/* ACTION PANEL */}
        <div className={styles.actionPanel}>
          <h3 className={styles.sectionTitle}>Officer Actions</h3>

          {/* Phase 13: Notify citizen button */}
          <button onClick={sendStatusNotification} disabled={sendingNotif}
            style={{width:'100%',background:'rgba(37,211,102,0.1)',border:'1px solid rgba(37,211,102,0.3)',
              color:'#25d366',borderRadius:8,padding:'8px 12px',fontSize:13,cursor:'pointer',
              marginBottom:12,display:'flex',alignItems:'center',gap:6,justifyContent:'center',fontFamily:'inherit'}}>
            {sendingNotif ? '⏳ Sending…' : '💬 Notify Citizen (WhatsApp)'}
          </button>

          {/* ── Admin Pre-Payment Approval (PENDING_OFFICER_PRE_APPROVAL) ── */}
          {app.status === 'PENDING_OFFICER_PRE_APPROVAL' && (
            <div style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', border: '1px solid #6366f1', borderRadius: 12, padding: 20, marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <span style={{ fontSize: 22 }}>📋</span>
                <div>
                  <div style={{ fontWeight: 700, color: '#e2e8f0', fontSize: 15 }}>Admin Document Pre-Verification</div>
                  <div style={{ fontSize: 12, color: '#94a3b8' }}>
                    This application is waiting for your document approval before the citizen can pay.
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <button
                  onClick={() => adminDocDecision('APPROVE')}
                  style={{ background: '#16a34a', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 20px', fontWeight: 700, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  <CheckCircle size={16} /> Approve Documents & Request Payment
                </button>
                <button
                  onClick={() => setConfirmAction('PRE_REJECT')}
                  style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 20px', fontWeight: 700, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  <XCircle size={16} /> Reject Documents
                </button>
              </div>
              {confirmAction === 'PRE_REJECT' && (
                <div style={{ marginTop: 14, background: '#1e293b', borderRadius: 8, padding: 14, border: '1px solid #ef444440' }}>
                  <p style={{ color: '#e2e8f0', fontSize: 13, marginBottom: 8 }}>Enter rejection reason (citizen will be notified):</p>
                  <textarea
                    className={styles.notesInput}
                    value={rejectReason}
                    onChange={e => setRejectReason(e.target.value)}
                    placeholder="e.g. Aadhaar number in document doesn't match declared value"
                    rows={3}
                    style={{ width: '100%', marginBottom: 10 }}
                  />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => adminDocDecision('REJECT')}
                      style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: 6, padding: '8px 16px', fontWeight: 600, cursor: 'pointer' }}
                    >
                      Confirm Reject
                    </button>
                    <button
                      onClick={() => { setConfirmAction(null); setRejectReason('') }}
                      style={{ background: 'rgba(255,255,255,0.1)', color: '#94a3b8', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer' }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {['SUBMITTED','UNDER_REVIEW','SUBMITTED_FOR_VERIFICATION'].includes(app.status) && (
            <div className={styles.actionBtns}>
              <button className={`${styles.actionBtn} ${styles.approveBtn}`}
                onClick={() => setConfirmAction('APPROVED')} disabled={mutation.isPending}>
                <CheckCircle size={16}/> Approve
              </button>
              <button className={`${styles.actionBtn} ${styles.rejectBtn}`}
                onClick={() => setConfirmAction('REJECTED')} disabled={mutation.isPending}>
                <XCircle size={16}/> Reject
              </button>
              <button className={`${styles.actionBtn} ${styles.escalateBtn}`}
                onClick={() => mutation.mutate({ status: 'ESCALATED', note: notes })} disabled={mutation.isPending}>
                <AlertTriangle size={16}/> Escalate
              </button>
            </div>
          )}

          {confirmAction === 'APPROVED' && (
            <div className={styles.confirmBox}>
              <p>Confirm approval of <b>{app.application_number}</b>?</p>
              <div className={styles.confirmBtns}>
                <button className={styles.confirmYes} onClick={()=>handleAction('APPROVED')} disabled={mutation.isPending}>
                  {mutation.isPending?'…':'Confirm Approve'}
                </button>
                <button className={styles.confirmNo} onClick={()=>setConfirmAction(null)}>Cancel</button>
              </div>
            </div>
          )}

          {confirmAction === 'REJECTED' && (
            <div className={`${styles.confirmBox} ${styles.rejectBox}`}>
              <p>Rejection reason (required):</p>
              <textarea className={styles.notesInput} value={rejectReason} onChange={e=>setRejectReason(e.target.value)}
                placeholder="Enter reason for rejection…" rows={3} required/>
              <div className={styles.confirmBtns}>
                <button className={styles.confirmReject} onClick={()=>handleAction('REJECTED')} disabled={mutation.isPending}>
                  {mutation.isPending?'…':'Confirm Reject'}
                </button>
                <button className={styles.confirmNo} onClick={()=>setConfirmAction(null)}>Cancel</button>
              </div>
            </div>
          )}

          <div className={styles.notesSection}>
            <label className={styles.notesLabel}>Officer Notes</label>
            <textarea className={styles.notesInput} value={notes} onChange={e=>setNotes(e.target.value)}
              placeholder="Add internal notes…" rows={4}/>
          </div>
        </div>
      </div>
    </div>
  )
}
