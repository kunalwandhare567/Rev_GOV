import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, RefreshCw, Filter } from 'lucide-react'
import { dashboardApi } from '../../api/dashboard'
import { EVENT_TYPE_CONFIG, POLL_INTERVALS } from '../../utils/constants'
import styles from './AuditLog.module.css'

const EVENT_TYPES = ['DATA_GUARD','CONSENT','SUBMISSION','PAYMENT','ESCALATION','STATUS_UPDATE','FRAUD_REJECT']

export default function AuditLog() {
  const [filterType, setFilterType] = useState('')
  const [limit, setLimit] = useState(50)

  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ['audit-log', filterType, limit],
    queryFn: () => dashboardApi.getAuditLog(limit, filterType || null),
    refetchInterval: POLL_INTERVALS.LIVE_FEED,
  })

  const events = data?.events || []
  const lastUpdated = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : ''

  const exportCSV = () => {
    const headers = ['id','timestamp','event_type','actor_type','action','outcome','application_number','payload_hash']
    const rows = events.map(e => headers.map(h => JSON.stringify(e[h] ?? '')).join(','))
    const blob = new Blob([[headers.join(','), ...rows].join('\n')], {type:'text/csv'})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `audit_log_${Date.now()}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.title}>Audit Log</h1>
          <p className={styles.sub}>Immutable chain-of-custody event log · {events.length} events · Last: {lastUpdated}</p>
        </div>
        <div className={styles.headerActions}>
          <button className={styles.iconBtn} onClick={() => refetch()}><RefreshCw size={16}/> Refresh</button>
          <button className={styles.iconBtn} onClick={exportCSV}><Download size={16}/> Export CSV</button>
        </div>
      </div>

      <div className={styles.filterBar}>
        <Filter size={16} style={{color:'var(--admin-muted)'}}/>
        <button className={`${styles.filterChip} ${!filterType?styles.chipActive:''}`} onClick={()=>setFilterType('')}>All</button>
        {EVENT_TYPES.map(t=>(
          <button key={t} className={`${styles.filterChip} ${filterType===t?styles.chipActive:''}`}
            onClick={()=>setFilterType(filterType===t?'':t)}
            style={filterType===t?{background:EVENT_TYPE_CONFIG[t]?.color,borderColor:EVENT_TYPE_CONFIG[t]?.color}:{}}>
            {t.replace('_',' ')}
          </button>
        ))}
        <select className={styles.limitSel} value={limit} onChange={e=>setLimit(+e.target.value)}>
          {[25,50,100,200].map(n=><option key={n} value={n}>Show {n}</option>)}
        </select>
      </div>

      {isLoading ? (
        <div className={styles.loadBox}><RefreshCw size={24} className="anim-spin"/> Loading audit log…</div>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                {['#','Timestamp','Event Type','Actor','Action','Outcome','Application','Hash'].map(h=>(
                  <th key={h} className={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {events.map((ev,i) => {
                const cfg = EVENT_TYPE_CONFIG[ev.event_type] || {}
                return (
                  <tr key={ev.id||i} className={styles.tr}>
                    <td className={styles.td}><code className={styles.idCell}>{ev.id}</code></td>
                    <td className={styles.td}>{new Date(ev.created_at||Date.now()).toLocaleString()}</td>
                    <td className={styles.td}>
                      <span className={styles.typeBadge} style={{background:cfg.bg,color:cfg.color}}>{ev.event_type}</span>
                    </td>
                    <td className={styles.td}>{ev.actor_type||'—'}</td>
                    <td className={styles.td} title={ev.action}>{(ev.action||'').substring(0,50)}{ev.action?.length>50?'…':''}</td>
                    <td className={styles.td}>
                      <span className={styles.outcome} style={{color:ev.outcome==='SUCCESS'?'var(--clr-success-400)':ev.outcome==='BLOCKED'?'var(--clr-danger-400)':'var(--admin-muted)'}}>
                        {ev.outcome||'—'}
                      </span>
                    </td>
                    <td className={styles.td}><code className={styles.appCell}>{ev.application_number||'—'}</code></td>
                    <td className={styles.td}><code className={styles.hashCell} title={ev.payload_hash}>{(ev.payload_hash||'').substring(0,12)}{ev.payload_hash?'…':''}</code></td>
                  </tr>
                )
              })}
              {events.length === 0 && (
                <tr><td colSpan={8} className={styles.empty}>No audit events found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
