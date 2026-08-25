import { useState, useCallback } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, Clock, CheckCircle2, XCircle, AlertCircle, RefreshCw } from 'lucide-react'
import useChatStore from '../../store/chatStore'
import { applicationsApi } from '../../api/applications'
import { t } from '../../i18n'
import { STATUS_CONFIG, STORAGE_KEYS } from '../../utils/constants'
import styles from './StatusTracker.module.css'

const STATUS_STEPS = ['submitted','received','doc_check','eligibility','approved','issued']
const APP_STATUS_TO_STEP = { SUBMITTED: 1, UNDER_REVIEW: 2, APPROVED: 4, REJECTED: 2, ESCALATED: 2 }

function getRecent() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEYS.RECENT_SEARCHES) || '[]') } catch { return [] }
}
function saveRecent(appNum) {
  const list = [appNum, ...getRecent().filter(x => x !== appNum)].slice(0, 5)
  localStorage.setItem(STORAGE_KEYS.RECENT_SEARCHES, JSON.stringify(list))
}

export default function StatusTracker() {
  const { language } = useChatStore()
  const [searchParams] = useSearchParams()
  const [query, setQuery]   = useState(searchParams.get('app') || '')
  const [searched, setSearched] = useState(!!searchParams.get('app'))

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['app-status', query],
    queryFn:  () => applicationsApi.getStatus(query),
    enabled:  searched && !!query,
    retry: false,
  })

  const handleSearch = useCallback((e) => {
    e?.preventDefault()
    if (!query.trim()) return
    saveRecent(query.trim())
    setSearched(true)
    refetch()
  }, [query, refetch])

  const app = data?.application
  const stepIdx = app ? (APP_STATUS_TO_STEP[app.status] ?? 0) : 0

  return (
    <div className={styles.page}>
      <div className={styles.inner}>
        <div className={styles.pageHeader}>
          <h1 className={styles.title}>{t(language,'status.title')}</h1>
          <p className={styles.subtitle}>{t(language,'status.subtitle')}</p>
        </div>

        <form className={styles.searchBox} onSubmit={handleSearch}>
          <div className={styles.searchInput}>
            <Search size={18} className={styles.searchIcon}/>
            <input className={styles.input} value={query} onChange={e => setQuery(e.target.value)}
              placeholder={t(language,'status.placeholder')} />
          </div>
          <button type="submit" className={styles.searchBtn}>{t(language,'status.searchBtn')}</button>
        </form>

        {getRecent().length > 0 && (
          <div className={styles.recentRow}>
            <span className={styles.recentLabel}><Clock size={14}/> {t(language,'status.recentSearches')}:</span>
            {getRecent().map(r => (
              <button key={r} className={styles.recentChip} onClick={() => { setQuery(r); setSearched(true); }}>
                {r}
              </button>
            ))}
          </div>
        )}

        {isLoading && <div className={styles.loadBox}><RefreshCw size={24} className="anim-spin"/> Loading…</div>}

        {error && searched && (
          <div className={styles.notFound}>
            <XCircle size={48} style={{color:'var(--clr-danger-400)'}}/>
            <h3>{t(language,'status.notFound')}</h3>
            <p>Application <b>{query}</b> was not found.</p>
            <Link to="/chat" className={styles.helpBtn}>{t(language,'status.chatHelp')}</Link>
          </div>
        )}

        {app && (
          <div className={styles.resultCard}>
            <div className={styles.resultHeader}>
              <div>
                <h2 className={styles.resultService}>
                  {typeof app.service_name === 'object'
                    ? (app.service_name?.en || Object.values(app.service_name || {})[0] || app.service_type)
                    : (app.service_name || app.service_type)}
                </h2>
                <p className={styles.resultId}>{app.application_number} · {new Date(app.created_at).toLocaleDateString()}</p>
              </div>
              <div className={styles.statusBadge} style={{
                background: STATUS_CONFIG[app.status]?.bg,
                color:      STATUS_CONFIG[app.status]?.color,
              }}>
                <span className={styles.statusDot} style={{background: STATUS_CONFIG[app.status]?.dot}}/>
                {t(language, `statuses.${app.status}`)}
              </div>
            </div>

            <div className={styles.timeline}>
              {STATUS_STEPS.map((step, i) => {
                const done   = i < stepIdx
                const active = i === stepIdx
                const fail   = app.status === 'REJECTED' && i === stepIdx
                return (
                  <div key={step} className={styles.timelineStep}>
                    <div className={`${styles.tlDot} ${done?styles.tlDone:''} ${active?styles.tlActive:''} ${fail?styles.tlFail:''}`}>
                      {done ? <CheckCircle2 size={16}/> : fail ? <XCircle size={16}/> : active ? <AlertCircle size={16}/> : null}
                    </div>
                    {i < STATUS_STEPS.length - 1 && (
                      <div className={`${styles.tlLine} ${done?styles.tlLineDone:''}`}/>
                    )}
                    <span className={styles.tlLabel}>{t(language, `status.steps.${step}`)}</span>
                  </div>
                )
              })}
            </div>

            <div className={styles.metaRow}>
              {app.fee_paid_amount !== undefined && (
                <div className={styles.metaItem}>
                  <span className={styles.metaKey}>{t(language,'status.feePaid')}</span>
                  <span className={styles.metaVal}>₹{app.fee_paid_amount} · {app.payment_reference || 'N/A'}</span>
                </div>
              )}
              <div className={styles.metaItem}>
                <span className={styles.metaKey}>Channel</span>
                <span className={styles.metaVal}>{app.channel} · {app.language?.toUpperCase()}</span>
              </div>
              {app.sla_days && (
                <div className={styles.metaItem}>
                  <span className={styles.metaKey}>{t(language,'status.estCompletion')}</span>
                  <span className={styles.metaVal}>{app.sla_days} {t(language,'common.days')}</span>
                </div>
              )}
            </div>

            <div className={styles.actions}>
              <Link to="/chat" className={styles.actionBtn}>{t(language,'status.chatHelp')}</Link>
              {app.status === 'DRAFT' && (
                <Link to={`/chat?service=${app.service_type}`} className={`${styles.actionBtn} ${styles.primaryBtn}`}>
                  Continue Application
                </Link>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
