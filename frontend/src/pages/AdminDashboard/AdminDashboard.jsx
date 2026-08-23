import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { RefreshCw, ExternalLink, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { dashboardApi } from '../../api/dashboard'
import { applicationsApi } from '../../api/applications'
import { STATUS_CONFIG, EVENT_TYPE_CONFIG, POLL_INTERVALS } from '../../utils/constants'
import styles from './AdminDashboard.module.css'

const RADIAN = Math.PI / 180
const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.05) return null
  const r = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + r * Math.cos(-midAngle * RADIAN)
  const y = cy + r * Math.sin(-midAngle * RADIAN)
  return <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11}>{`${(percent*100).toFixed(0)}%`}</text>
}

function MetricCard({ label, value, trend, trendVal, color, sub }) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = trend === 'up' ? 'var(--clr-success-400)' : trend === 'down' ? 'var(--clr-danger-400)' : 'var(--clr-gray-400)'
  return (
    <div className={styles.metricCard}>
      <div className={styles.metricLabel}>{label}</div>
      <div className={styles.metricValue} style={{color: color || 'var(--admin-text)'}}>{value ?? '—'}</div>
      {sub && <div className={styles.metricSub}>{sub}</div>}
      {trendVal !== undefined && (
        <div className={styles.metricTrend} style={{color: trendColor}}>
          <TrendIcon size={14}/> {trendVal}
        </div>
      )}
    </div>
  )
}

export default function AdminDashboard() {
  const { data: overview, dataUpdatedAt } = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: dashboardApi.getOverview,
    refetchInterval: POLL_INTERVALS.DASHBOARD,
  })

  const { data: recentData } = useQuery({
    queryKey: ['recent-apps'],
    queryFn: () => applicationsApi.getRecent(20),
    refetchInterval: POLL_INTERVALS.DASHBOARD,
  })

  const { data: auditData } = useQuery({
    queryKey: ['live-feed'],
    queryFn: () => dashboardApi.getAuditLog(10),
    refetchInterval: POLL_INTERVALS.LIVE_FEED,
  })

  const stats = overview?.stats || {}
  const byStatus   = overview?.by_status   || {}
  const byService  = overview?.by_service  || {}
  const byLanguage = overview?.by_language || {}

  const statusPieData = Object.entries(byStatus).map(([k,v]) => ({
    name: k, value: v, fill: STATUS_CONFIG[k]?.dot || '#6b7280'
  })).filter(d => d.value > 0)

  const serviceBarData = Object.entries(byService).map(([k,v]) => ({ name: k.replace('_certificate','').toUpperCase(), value: v }))
  const langBarData    = Object.entries(byLanguage).map(([k,v]) => ({ name: k.toUpperCase(), value: v })).sort((a,b) => b.value-a.value)

  const recentApps = recentData?.applications || []
  const liveEvents = auditData?.events || []
  const lastUpdated = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : ''

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.title}>Operations Dashboard</h1>
          <p className={styles.sub}>Auto-refreshing every 5s · Last updated: {lastUpdated}</p>
        </div>
        <Link to="/admin/data-guard" className={styles.guardLink}><RefreshCw size={14}/> Data Guard Live</Link>
      </div>

      <div className={styles.metricsGrid}>
        <MetricCard label="Active Sessions"   value={stats.active_sessions}   color="var(--clr-success-400)"  sub="Current"/>
        <MetricCard label="Submitted Today"   value={stats.submitted_today}   color="var(--clr-primary-400)" sub="Today"/>
        <MetricCard label="Total Approved"    value={stats.total_approved}    color="var(--clr-success-400)" sub="All time"/>
        <MetricCard label="Total Rejected"    value={stats.total_rejected}    color="var(--clr-danger-400)"  sub="All time"/>
        <MetricCard label="DG Blocks Today"   value={stats.dg_blocks_today}   color="var(--clr-warning-400)" sub="Today"/>
        <MetricCard label="Avg Anomaly Score" value={stats.avg_anomaly_score?.toFixed(3)} color="var(--clr-accent-400)" sub="Lower is better"/>
      </div>

      <div className={styles.chartsRow}>
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>By Status</h3>
          {statusPieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={statusPieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                  dataKey="value" labelLine={false} label={renderCustomLabel}>
                  {statusPieData.map((d,i) => <Cell key={i} fill={d.fill}/>)}
                </Pie>
                <Tooltip contentStyle={{background:'#1a1d2e',border:'1px solid rgba(255,255,255,.1)',borderRadius:'8px',color:'#e8eaf6'}}/>
                <Legend wrapperStyle={{fontSize:'11px',color:'#8892b0'}}/>
              </PieChart>
            </ResponsiveContainer>
          ) : <div className={styles.noData}>No data yet</div>}
        </div>

        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>By Service</h3>
          {serviceBarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={serviceBarData} margin={{top:5,right:10,left:0,bottom:5}}>
                <XAxis dataKey="name" tick={{fill:'#8892b0',fontSize:11}} axisLine={false} tickLine={false}/>
                <YAxis tick={{fill:'#8892b0',fontSize:11}} axisLine={false} tickLine={false}/>
                <Tooltip contentStyle={{background:'#1a1d2e',border:'1px solid rgba(255,255,255,.1)',borderRadius:'8px',color:'#e8eaf6'}}/>
                <Bar dataKey="value" fill="var(--clr-primary-500)" radius={[4,4,0,0]}/>
              </BarChart>
            </ResponsiveContainer>
          ) : <div className={styles.noData}>No data yet</div>}
        </div>

        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Language Distribution</h3>
          <div className={styles.langBars}>
            {langBarData.map(({name,value}) => {
              const total = langBarData.reduce((s,d)=>s+d.value,0)||1
              const pct = Math.round((value/total)*100)
              return (
                <div key={name} className={styles.langRow}>
                  <span className={styles.langName}>{name}</span>
                  <div className={styles.langBarWrap}>
                    <div className={styles.langBarFill} style={{width:`${pct}%`}}/>
                  </div>
                  <span className={styles.langPct}>{pct}%</span>
                </div>
              )
            })}
            {langBarData.length === 0 && <div className={styles.noData}>No data yet</div>}
          </div>
        </div>
      </div>

      <div className={styles.bottomRow}>
        <div className={styles.tableCard}>
          <div className={styles.tableHeader}>
            <h3 className={styles.chartTitle}>Recent Applications</h3>
            <span className={styles.tableCount}>{recentApps.length} shown</span>
          </div>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  {['Application #','Service','Language','Channel','Status','Score','Action'].map(h=>(
                    <th key={h} className={styles.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentApps.map(app => (
                  <tr key={app.application_number} className={styles.tr}>
                    <td className={styles.td}><code className={styles.appNum}>{app.application_number}</code></td>
                    <td className={styles.td}>{(app.service_type||'').replace('_certificate','').toUpperCase()}</td>
                    <td className={styles.td}>{(app.language||'').toUpperCase()}</td>
                    <td className={styles.td}>{app.channel||'WEB'}</td>
                    <td className={styles.td}>
                      <span className={styles.statusPill} style={{background:STATUS_CONFIG[app.status]?.bg,color:STATUS_CONFIG[app.status]?.color}}>
                        {app.status}
                      </span>
                    </td>
                    <td className={styles.td}>
                      <span style={{color: app.anomaly_score > 0.7 ? 'var(--clr-danger-400)' : app.anomaly_score > 0.4 ? 'var(--clr-warning-400)' : 'var(--clr-success-400)'}}>
                        {(app.anomaly_score||0).toFixed(2)}
                      </span>
                    </td>
                    <td className={styles.td}>
                      <Link to={`/admin/review/${app.application_number}`} className={styles.reviewBtn}>Review</Link>
                    </td>
                  </tr>
                ))}
                {recentApps.length === 0 && (
                  <tr><td colSpan={7} className={styles.emptyRow}>No applications yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className={styles.feedCard}>
          <div className={styles.feedHeader}>
            <h3 className={styles.chartTitle}>Live Events</h3>
            <Link to="/admin/audit" className={styles.auditLink}>View all <ExternalLink size={12}/></Link>
          </div>
          <div className={styles.feedList}>
            {liveEvents.length === 0 && <div className={styles.noData}>No events yet</div>}
            {liveEvents.map((ev,i) => {
              const cfg = EVENT_TYPE_CONFIG[ev.event_type] || {}
              return (
                <div key={ev.id||i} className={styles.feedItem}>
                  <span className={styles.feedDot} style={{background:cfg.color||'var(--clr-gray-400)'}}/>
                  <div className={styles.feedContent}>
                    <span className={styles.feedType} style={{color:cfg.color}}>{ev.event_type}</span>
                    <span className={styles.feedAction}>{ev.action?.substring(0,60)}</span>
                  </div>
                  <span className={styles.feedTime}>{new Date(ev.created_at||Date.now()).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
