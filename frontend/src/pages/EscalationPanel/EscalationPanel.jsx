import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import toast from 'react-hot-toast'
import { RefreshCw, Clock, AlertTriangle, CheckCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { dashboardApi } from '../../api/dashboard'
import { PRIORITY_CONFIG, POLL_INTERVALS } from '../../utils/constants'
import { applicationsApi } from '../../api/applications'
import styles from './EscalationPanel.module.css'

const COLS = ['open', 'assigned', 'resolved']
const COL_ICONS = { open: AlertTriangle, assigned: Clock, resolved: CheckCircle }
const COL_COLORS = { open:'var(--clr-danger-400)', assigned:'var(--clr-warning-400)', resolved:'var(--clr-success-400)' }

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff/60)}m ago`
  return `${Math.round(diff/3600)}h ago`
}

export default function EscalationPanel() {
  const queryClient = useQueryClient()
  const [resolutionNotes, setResolutionNotes] = useState({})

  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['escalations'],
    queryFn: dashboardApi.getEscalations,
    refetchInterval: POLL_INTERVALS.ESCALATIONS,
  })

  const mutation = useMutation({
    mutationFn: ({ appNumber, status, note }) => applicationsApi.updateStatus(appNumber, status, note),
    onSuccess: (_, { status }) => {
      toast.success(`Escalation ${status === 'APPROVED' ? 'resolved' : 'updated'}`)
      queryClient.invalidateQueries(['escalations'])
      queryClient.invalidateQueries(['recent-apps'])
    },
    onError: (err) => toast.error(err.message),
  })

  const allEscalations = data?.escalations || []

  const grouped = {
    open:     allEscalations.filter(e => e.escalation_state === 'OPEN'     || (!e.escalation_state && e.status === 'ESCALATED')),
    assigned: allEscalations.filter(e => e.escalation_state === 'ASSIGNED'),
    resolved: allEscalations.filter(e => e.escalation_state === 'RESOLVED'),
  }

  const lastUpdated = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : ''

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.title}>Escalation Management</h1>
          <p className={styles.sub}>{allEscalations.length} total · Auto-refresh 10s · {lastUpdated}</p>
        </div>
        <div className={styles.statsRow}>
          {COLS.map(col => (
            <div key={col} className={styles.statBadge} style={{borderColor:COL_COLORS[col]}}>
              <span style={{color:COL_COLORS[col]}}>{grouped[col].length}</span>
              <span className={styles.statLabel}>{col.charAt(0).toUpperCase()+col.slice(1)}</span>
            </div>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className={styles.loadBox}><RefreshCw size={24} className="anim-spin"/> Loading escalations…</div>
      ) : (
        <div className={styles.kanban}>
          {COLS.map(col => {
            const Icon = COL_ICONS[col]
            return (
              <div key={col} className={styles.column}>
                <div className={styles.colHeader}>
                  <Icon size={16} style={{color:COL_COLORS[col]}}/>
                  <span className={styles.colTitle}>{col.charAt(0).toUpperCase()+col.slice(1)}</span>
                  <span className={styles.colCount}>{grouped[col].length}</span>
                </div>
                <div className={styles.cards}>
                  {grouped[col].length === 0 && (
                    <div className={styles.emptyCol}>No {col} escalations</div>
                  )}
                  {grouped[col].map(esc => {
                    const priority = esc.priority || 'MEDIUM'
                    const pCfg = PRIORITY_CONFIG[priority] || PRIORITY_CONFIG.MEDIUM
                    return (
                      <div key={esc.application_number} className={styles.card}>
                        <div className={styles.cardTop}>
                          <span className={styles.priorityTag} style={{background:pCfg.bg, color:pCfg.color}}>{priority}</span>
                          <span className={styles.timeAgo}>{timeAgo(esc.escalated_at || esc.created_at)}</span>
                        </div>
                        <Link to={`/admin/review/${esc.application_number}`} className={styles.appNum}>
                          {esc.application_number}
                        </Link>
                        <p className={styles.serviceType}>{(esc.service_type||'').replace(/_/g,' ').toUpperCase()}</p>
                        {esc.escalation_reason && (
                          <p className={styles.reason}>{esc.escalation_reason}</p>
                        )}
                        <div className={styles.cardMeta}>
                          <span>{esc.channel || 'WEB'}</span>
                          <span>{(esc.language||'en').toUpperCase()}</span>
                          <span style={{color: esc.anomaly_score>0.7?'var(--clr-danger-400)':esc.anomaly_score>0.4?'var(--clr-warning-400)':'var(--clr-success-400)'}}>
                            Risk: {(esc.anomaly_score||0).toFixed(2)}
                          </span>
                        </div>

                        {col === 'open' && (
                          <div className={styles.cardActions}>
                            <textarea className={styles.resolutionInput}
                              placeholder="Resolution notes…"
                              value={resolutionNotes[esc.application_number] || ''}
                              onChange={e=>setResolutionNotes(p=>({...p,[esc.application_number]:e.target.value}))}
                              rows={2}/>
                            <div className={styles.btnRow}>
                              <button className={styles.resolveBtn}
                                onClick={()=>mutation.mutate({appNumber:esc.application_number, status:'APPROVED', note: resolutionNotes[esc.application_number]||'Resolved by officer'})}
                                disabled={mutation.isPending}>
                                Resolve → Approve
                              </button>
                              <button className={styles.rejectBtn}
                                onClick={()=>mutation.mutate({appNumber:esc.application_number, status:'REJECTED', note: resolutionNotes[esc.application_number]||'Rejected after review'})}
                                disabled={mutation.isPending}>
                                Reject
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
