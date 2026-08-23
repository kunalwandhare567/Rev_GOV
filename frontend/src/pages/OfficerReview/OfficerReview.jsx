import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { ArrowLeft, CheckCircle, XCircle, AlertTriangle, MessageSquare, RefreshCw } from 'lucide-react'
import { applicationsApi } from '../../api/applications'
import { STATUS_CONFIG } from '../../utils/constants'
import styles from './OfficerReview.module.css'

const TABS = ['details', 'eligibility', 'documents', 'payment', 'conversation']

export default function OfficerReview() {
  const { appNumber } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('details')
  const [rejectReason, setRejectReason] = useState('')
  const [notes, setNotes] = useState('')
  const [confirmAction, setConfirmAction] = useState(null)

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

  const app = data?.application
  const slots = app?.slots_data || {}
  const docs = app?.documents || []
  const eligibility = app?.eligibility_result || {}

  if (isLoading) return <div className={styles.loadBox}><RefreshCw size={24} className="anim-spin"/> Loading application…</div>
  if (error || !app) return (
    <div className={styles.errorBox}>
      <XCircle size={48} style={{color:'var(--clr-danger-400)'}}/><p>{error?.message || 'Application not found'}</p>
      <button className={styles.backBtn} onClick={()=>navigate(-1)}>Go Back</button>
    </div>
  )

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <button className={styles.backBtn} onClick={()=>navigate(-1)}><ArrowLeft size={16}/> Back</button>
          <div>
            <h1 className={styles.title}>{app.application_number}</h1>
            <p className={styles.sub}>{app.service_type?.replace(/_/g,' ').toUpperCase()} · {new Date(app.created_at).toLocaleDateString()}</p>
          </div>
        </div>
        <div className={styles.headerRight}>
          <span className={styles.statusBadge} style={{background:STATUS_CONFIG[app.status]?.bg, color:STATUS_CONFIG[app.status]?.color}}>
            <span className={styles.statusDot} style={{background:STATUS_CONFIG[app.status]?.dot}}/>{app.status}
          </span>
          <span className={styles.scoreTag} style={{color: app.anomaly_score>0.7?'var(--clr-danger-400)':app.anomaly_score>0.4?'var(--clr-warning-400)':'var(--clr-success-400)'}}>
            Risk: {(app.anomaly_score||0).toFixed(2)}
          </span>
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
          {activeTab === 'details' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Application Details</h3>
              <div className={styles.detailGrid}>
                {[
                  ['Service', app.service_type?.replace(/_/g,' ')],
                  ['Channel', app.channel],
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
              {Object.keys(slots).length > 0 && (
                <>
                  <h3 className={styles.sectionTitle} style={{marginTop:'var(--sp-6)'}}>Collected Data</h3>
                  <div className={styles.detailGrid}>
                    {Object.entries(slots).map(([k,v]) => (
                      <div key={k} className={styles.detailItem}>
                        <span className={styles.detailKey}>{k.replace(/_/g,' ')}</span>
                        <span className={styles.detailVal}>{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === 'eligibility' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Eligibility Check Results</h3>
              {eligibility.eligible !== undefined ? (
                <>
                  <div className={`${styles.eligResult} ${eligibility.eligible?styles.eligible:styles.ineligible}`}>
                    {eligibility.eligible ? <CheckCircle size={24}/> : <XCircle size={24}/>}
                    <span>{eligibility.eligible ? 'Eligible' : 'Not Eligible'}</span>
                  </div>
                </>
              ) : <p className={styles.noData}>Eligibility not yet checked.</p>}
            </div>
          )}

          {activeTab === 'documents' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Submitted Documents</h3>
              {docs.length === 0 ? <p className={styles.noData}>No documents uploaded yet.</p> : (
                <div className={styles.docList}>
                  {docs.map((doc,i)=>(
                    <div key={i} className={styles.docRow}>
                      <span className={styles.docIcon}>📄</span>
                      <div>
                        <p className={styles.docType}>{doc.doc_type?.replace(/_/g,' ')}</p>
                        <p className={styles.docMeta}>{doc.filename || 'document'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
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

          {activeTab === 'conversation' && (
            <div className={styles.detailsCard}>
              <h3 className={styles.sectionTitle}>Conversation Transcript</h3>
              <p className={styles.noData}>No conversation log recorded.</p>
            </div>
          )}
        </div>

        <div className={styles.actionPanel}>
          <h3 className={styles.sectionTitle}>Officer Actions</h3>
          {['SUBMITTED','UNDER_REVIEW'].includes(app.status) && (
            <div className={styles.actionBtns}>
              <button className={`${styles.actionBtn} ${styles.approveBtn}`}
                onClick={()=>setConfirmAction('APPROVED')} disabled={mutation.isPending}>
                <CheckCircle size={16}/> Approve
              </button>
              <button className={`${styles.actionBtn} ${styles.rejectBtn}`}
                onClick={()=>setConfirmAction('REJECTED')} disabled={mutation.isPending}>
                <XCircle size={16}/> Reject
              </button>
              <button className={`${styles.actionBtn} ${styles.escalateBtn}`}
                onClick={()=>handleAction('ESCALATED')} disabled={mutation.isPending}>
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
            <div className={styles.confirmBox + ' ' + styles.rejectBox}>
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
