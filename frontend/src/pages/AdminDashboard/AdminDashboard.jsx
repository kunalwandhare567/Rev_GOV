import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  FileText,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  CreditCard,
  Award,
  RefreshCw,
  ArrowRight,
  TrendingUp,
  Activity,
  ShieldCheck,
} from 'lucide-react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { dashboardApi } from '../../api/dashboard'
import { applicationsApi } from '../../api/applications'
import { STATUS_CONFIG } from '../../utils/constants'
import styles from './AdminDashboard.module.css'

const formatServiceName = (name, id = '') => {
  if (!name) return (id || '').replace(/_/g, ' ')
  if (typeof name === 'object') return name.en || Object.values(name)[0] || id
  return String(name).replace(/_/g, ' ')
}

function MetricCard({ title, count, icon: Icon, color, bg, linkTo }) {
  return (
    <Link to={linkTo} className={styles.metricCard}>
      <div className={styles.metricHeader}>
        <span className={styles.metricTitle}>{title}</span>
        <div className={styles.metricIconWrap} style={{ color, backgroundColor: bg }}>
          <Icon size={20} />
        </div>
      </div>
      <div className={styles.metricCount} style={{ color }}>
        {count ?? 0}
      </div>
      <div className={styles.metricFooter}>
        <span>View applications</span>
        <ArrowRight size={14} />
      </div>
    </Link>
  )
}

export default function AdminDashboard() {
  const {
    data: overview,
    isLoading: overviewLoading,
    refetch: refetchOverview,
    isFetching,
  } = useQuery({
    queryKey: ['admin-overview'],
    queryFn: dashboardApi.getOverview,
    refetchInterval: 10000,
  })

  const { data: awaitingData, isLoading: awaitingLoading } = useQuery({
    queryKey: ['awaiting-review-apps'],
    queryFn: () =>
      applicationsApi.getAdminList({
        status: 'SUBMITTED_FOR_VERIFICATION',
        limit: 5,
      }),
    refetchInterval: 10000,
  })

  const { data: auditData } = useQuery({
    queryKey: ['admin-audit-feed'],
    queryFn: () => dashboardApi.getAuditLog(12),
    refetchInterval: 10000,
  })

  const byStatus = overview?.by_status || {}
  const byService = overview?.by_service || {}
  const stats = overview?.stats || {}
  const totalApps = overview?.total_applications ?? 0

  // Count cards (Authoritative from SQLite)
  const submittedCount = overview?.submitted ?? (byStatus['SUBMITTED_FOR_VERIFICATION'] || byStatus['SUBMITTED'] || 0)
  const underReviewCount = overview?.under_review ?? (byStatus['UNDER_REVIEW'] || 0)
  const clarificationCount = overview?.clarification_required ?? (byStatus['CLARIFICATION_REQUIRED'] || 0)
  const approvedCount = overview?.approved ?? (byStatus['APPROVED'] || 0)
  const rejectedCount = overview?.rejected ?? (byStatus['REJECTED'] || 0)
  const paymentRequiredCount = overview?.payment_required ?? (byStatus['PAYMENT_REQUIRED'] || 0)
  const completedCount = overview?.completed ?? (byStatus['COMPLETED'] || 0)

  // Chart data
  const statusChartData = [
    { name: 'Submitted', value: submittedCount, color: '#4f46e5' },
    { name: 'Under Review', value: underReviewCount, color: '#f59e0b' },
    { name: 'Clarification', value: clarificationCount, color: '#dc2626' },
    { name: 'Approved', value: approvedCount, color: '#16a34a' },
    { name: 'Payment Req', value: paymentRequiredCount, color: '#ea580c' },
    { name: 'Completed', value: completedCount, color: '#0284c7' },
    { name: 'Rejected', value: rejectedCount, color: '#94a3b8' },
  ].filter((item) => item.value > 0)

  const serviceChartData = Object.entries(byService).map(([svc, count]) => ({
    name: svc.replace(/_/g, ' ').replace('certificate', 'cert'),
    count,
  }))

  const awaitingApps = awaitingData?.applications || []
  const auditEvents = auditData?.events || []

  return (
    <div className={styles.container}>
      {/* ── Top Header ── */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Revenue Services Operational Dashboard</h1>
          <p className={styles.subtitle}>
            Real-time government oversight, application verification pipeline & audit logging.
          </p>
        </div>
        <button
          className={styles.refreshBtn}
          onClick={() => refetchOverview()}
          disabled={isFetching}
        >
          <RefreshCw size={16} className={isFetching ? styles.spin : ''} />
          <span>Sync Realtime</span>
        </button>
      </div>

      {/* ── Metric Cards Grid ── */}
      <div className={styles.metricsGrid}>
        <MetricCard
          title="Total Applications"
          count={totalApps}
          icon={FileText}
          color="#00355f"
          bg="#e0f2fe"
          linkTo="/admin/applications?status=ALL"
        />
        <MetricCard
          title="Submitted (Awaiting)"
          count={submittedCount}
          icon={Clock}
          color="#4f46e5"
          bg="#eef2ff"
          linkTo="/admin/applications?status=SUBMITTED_FOR_VERIFICATION"
        />
        <MetricCard
          title="Under Review"
          count={underReviewCount}
          icon={Activity}
          color="#d97706"
          bg="#fef3c7"
          linkTo="/admin/applications?status=UNDER_REVIEW"
        />
        <MetricCard
          title="Clarification Req."
          count={clarificationCount}
          icon={AlertTriangle}
          color="#dc2626"
          bg="#fee2e2"
          linkTo="/admin/applications?status=CLARIFICATION_REQUIRED"
        />
        <MetricCard
          title="Approved"
          count={approvedCount}
          icon={CheckCircle}
          color="#16a34a"
          bg="#dcfce7"
          linkTo="/admin/applications?status=APPROVED"
        />
        <MetricCard
          title="Payment Required"
          count={paymentRequiredCount}
          icon={CreditCard}
          color="#ea580c"
          bg="#ffedd5"
          linkTo="/admin/applications?status=PAYMENT_REQUIRED"
        />
        <MetricCard
          title="Completed"
          count={completedCount}
          icon={Award}
          color="#0284c7"
          bg="#e0f2fe"
          linkTo="/admin/applications?status=COMPLETED"
        />
        <MetricCard
          title="Rejected"
          count={rejectedCount}
          icon={XCircle}
          color="#b91c1c"
          bg="#fee2e2"
          linkTo="/admin/applications?status=REJECTED"
        />
      </div>

      {/* ── Mid Section: Awaiting Applications & Live Feed ── */}
      <div className={styles.midGrid}>
        {/* Awaiting Review Card */}
        <div className={styles.panelCard}>
          <div className={styles.panelHeader}>
            <div className={styles.panelTitleGroup}>
              <Clock size={18} className={styles.panelIcon} />
              <h2 className={styles.panelTitle}>Applications Awaiting Officer Review</h2>
            </div>
            <Link to="/admin/applications?status=SUBMITTED_FOR_VERIFICATION" className={styles.viewAllLink}>
              View All Queue ({submittedCount})
            </Link>
          </div>

          {awaitingLoading ? (
            <div className={styles.loadingBox}>Loading queue...</div>
          ) : awaitingApps.length === 0 ? (
            <div className={styles.emptyBox}>
              <ShieldCheck size={36} color="#16a34a" />
              <p>No applications currently awaiting verification.</p>
            </div>
          ) : (
            <div className={styles.tableWrapper}>
              <table className={styles.miniTable}>
                <thead>
                  <tr>
                    <th>Tracking ID</th>
                    <th>Applicant</th>
                    <th>Service</th>
                    <th>Readiness</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {awaitingApps.map((app) => (
                    <tr key={app.id}>
                      <td>
                        <span className={styles.trackingText}>{app.tracking_id || app.application_number}</span>
                      </td>
                      <td>
                        <span className={styles.applicantText}>{app.applicant_name || app.citizen_name}</span>
                      </td>
                      <td>
                        <span className={styles.serviceText}>{formatServiceName(app.service_name, app.service_id)}</span>
                      </td>
                      <td>
                        {app.readiness_score != null || app.progress_percent != null ? (
                          <span className={styles.readinessPill}>
                            {Math.round(app.readiness_score != null ? app.readiness_score : app.progress_percent)}%
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8' }}>—</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <Link to={`/admin/review/${app.id || app.application_number}`} className={styles.actionBtn}>
                          Review
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Live Audit & Verification Feed */}
        <div className={styles.panelCard}>
          <div className={styles.panelHeader}>
            <div className={styles.panelTitleGroup}>
              <Activity size={18} className={styles.panelIcon} />
              <h2 className={styles.panelTitle}>Real-time Verification & Event Feed</h2>
            </div>
            <Link to="/admin/audit" className={styles.viewAllLink}>
              Audit Trail
            </Link>
          </div>

          <div className={styles.feedList}>
            {auditEvents.length === 0 ? (
              <div className={styles.emptyBox}>No recent audit events logged.</div>
            ) : (
              auditEvents.map((evt, idx) => (
                <div key={evt.id || idx} className={styles.feedItem}>
                  <div className={styles.feedDot} />
                  <div className={styles.feedContent}>
                    <div className={styles.feedTop}>
                      <span className={styles.feedType}>{evt.event_type}</span>
                      <span className={styles.feedTime}>
                        {new Date(evt.timestamp || evt.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className={styles.feedAction}>{evt.action}</p>
                    <span className={styles.feedActor}>Actor: {evt.actor}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ── Charts Grid ── */}
      <div className={styles.chartsGrid}>
        {/* Status Distribution */}
        <div className={styles.panelCard}>
          <h3 className={styles.chartTitle}>Application Lifecycle Distribution</h3>
          <div className={styles.chartWrap}>
            {statusChartData.length === 0 ? (
              <div className={styles.emptyBox}>No application distribution data.</div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={statusChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {statusChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className={styles.chartLegend}>
            {statusChartData.map((entry) => (
              <div key={entry.name} className={styles.legendItem}>
                <span className={styles.legendDot} style={{ backgroundColor: entry.color }} />
                <span>{entry.name}: {entry.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Service Volume Distribution */}
        <div className={styles.panelCard}>
          <h3 className={styles.chartTitle}>Service Request Volume</h3>
          <div className={styles.chartWrap}>
            {serviceChartData.length === 0 ? (
              <div className={styles.emptyBox}>No service request data.</div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={serviceChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-15} textAnchor="end" />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#00355f" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
