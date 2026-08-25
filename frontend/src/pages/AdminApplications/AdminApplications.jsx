import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Search,
  Filter,
  ArrowUpDown,
  FileCheck,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  ExternalLink,
  ShieldAlert,
} from 'lucide-react'
import { applicationsApi } from '../../api/applications'
import { STATUS_CONFIG } from '../../utils/constants'
import styles from './AdminApplications.module.css'

const formatServiceName = (name, id = '') => {
  if (!name) return (id || '').replace(/_/g, ' ')
  if (typeof name === 'object') return name.en || Object.values(name)[0] || id
  return String(name).replace(/_/g, ' ')
}

const STATUS_FILTERS = [
  { id: 'SUBMITTED_FOR_VERIFICATION', label: 'Submitted (Queue)' },
  { id: 'UNDER_REVIEW', label: 'Under Review' },
  { id: 'CLARIFICATION_REQUIRED', label: 'Clarification Required' },
  { id: 'APPROVED', label: 'Approved' },
  { id: 'PAYMENT_REQUIRED', label: 'Payment Required' },
  { id: 'COMPLETED', label: 'Completed' },
  { id: 'REJECTED', label: 'Rejected' },
  { id: 'ALL', label: 'All Applications' },
]

export default function AdminApplications() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialStatus = searchParams.get('status') || 'SUBMITTED_FOR_VERIFICATION'

  const [statusFilter, setStatusFilter] = useState(initialStatus)
  const [searchTerm, setSearchTerm] = useState('')
  const [serviceFilter, setServiceFilter] = useState('ALL')
  const [sortBy, setSortBy] = useState('newest')
  const [page, setPage] = useState(1)
  const limit = 15

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['admin-apps-list', statusFilter, serviceFilter, searchTerm, sortBy, page],
    queryFn: () =>
      applicationsApi.getAdminList({
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        service_id: serviceFilter !== 'ALL' ? serviceFilter : undefined,
        search: searchTerm.trim() || undefined,
        sort_by: sortBy,
        page,
        limit,
      }),
    refetchInterval: 10000,
  })

  const { data: servicesData } = useQuery({
    queryKey: ['services-list'],
    queryFn: applicationsApi.listServices,
  })

  const applications = data?.applications || []
  const total = data?.total || 0
  const totalPages = data?.total_pages || 1

  const handleStatusChange = (st) => {
    setStatusFilter(st)
    setPage(1)
    if (st === 'ALL') {
      searchParams.delete('status')
    } else {
      searchParams.set('status', st)
    }
    setSearchParams(searchParams)
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Application Queue</h1>
          <p className={styles.subtitle}>
            Authoritative officer registry of citizen applications, verification readiness & decisions.
          </p>
        </div>
        <button
          className={styles.refreshBtn}
          onClick={() => refetch()}
          disabled={isFetching}
          title="Refresh applications"
        >
          <RefreshCw size={16} className={isFetching ? styles.spin : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className={styles.filterTabs}>
        {STATUS_FILTERS.map((tab) => (
          <button
            key={tab.id}
            className={`${styles.tabBtn} ${statusFilter === tab.id ? styles.activeTab : ''}`}
            onClick={() => handleStatusChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search & Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.searchBox}>
          <Search size={18} className={styles.searchIcon} />
          <input
            type="text"
            placeholder="Search by Tracking ID, App Number, or Citizen..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value)
              setPage(1)
            }}
            className={styles.searchInput}
          />
        </div>

        <div className={styles.toolGroup}>
          <div className={styles.selectWrapper}>
            <Filter size={15} className={styles.selectIcon} />
            <select
              value={serviceFilter}
              onChange={(e) => {
                setServiceFilter(e.target.value)
                setPage(1)
              }}
              className={styles.select}
            >
              <option value="ALL">All Services</option>
              {servicesData?.services?.map((s) => (
                <option key={s.id} value={s.id}>
                  {formatServiceName(s.name, s.id)}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.selectWrapper}>
            <ArrowUpDown size={15} className={styles.selectIcon} />
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value)
                setPage(1)
              }}
              className={styles.select}
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="updated">Last Updated</option>
              <option value="readiness">Highest Readiness</option>
            </select>
          </div>
        </div>
      </div>

      {/* Applications Table Card */}
      <div className={styles.card}>
        {isLoading ? (
          <div className={styles.loadingState}>
            <div className={styles.spinner} />
            <p>Loading application records from SQLite...</p>
          </div>
        ) : applications.length === 0 ? (
          <div className={styles.emptyState}>
            <FileCheck size={48} className={styles.emptyIcon} />
            <h3>No applications found</h3>
            <p>
              {searchTerm || statusFilter !== 'ALL'
                ? 'Try adjusting your filters or search criteria.'
                : 'There are currently no applications matching this view in the database.'}
            </p>
          </div>
        ) : (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Tracking / App Number</th>
                  <th>Citizen / Applicant</th>
                  <th>Service</th>
                  <th>Submitted / Created</th>
                  <th>Status</th>
                  <th>Readiness</th>
                  <th>Match</th>
                  <th>Risk</th>
                  <th style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => {
                  const statusCfg = STATUS_CONFIG[app.status] || {
                    label: app.status,
                    color: '#64748b',
                    bg: '#f1f5f9',
                    dot: '#94a3b8',
                  }
                  const readinessScore = app.readiness_score != null
                    ? Math.round(app.readiness_score)
                    : (app.progress_percent != null ? Math.round(app.progress_percent) : null)

                  const matchScore = app.match_score != null
                    ? Math.round(app.match_score)
                    : null

                  const riskLevel = app.risk_level || (app.anomaly_score != null
                    ? (app.anomaly_score >= 0.7 ? 'HIGH' : app.anomaly_score >= 0.4 ? 'MEDIUM' : 'LOW')
                    : null)

                  return (
                    <tr key={app.id}>
                      <td>
                        <div className={styles.idGroup}>
                          <span className={styles.trackingId}>{app.tracking_id || app.application_number}</span>
                          <span className={styles.appNumber}>{app.application_number}</span>
                        </div>
                      </td>
                      <td>
                        <div className={styles.citizenGroup}>
                          <span className={styles.citizenName}>{app.applicant_name || app.citizen_name}</span>
                          <span className={styles.citizenRef}>{app.citizen_ref}</span>
                        </div>
                      </td>
                      <td>
                        <span className={styles.serviceName}>{formatServiceName(app.service_name, app.service_id)}</span>
                      </td>
                      <td>
                        <span className={styles.dateText}>
                          {app.submitted_at
                            ? new Date(app.submitted_at).toLocaleDateString()
                            : new Date(app.created_at).toLocaleDateString()}
                        </span>
                      </td>
                      <td>
                        <span
                          className={styles.statusPill}
                          style={{
                            color: statusCfg.color,
                            backgroundColor: statusCfg.bg,
                            borderColor: statusCfg.dot,
                          }}
                        >
                          <span
                            className={styles.statusDot}
                            style={{ backgroundColor: statusCfg.dot }}
                          />
                          {statusCfg.label || app.status}
                        </span>
                      </td>
                      <td>
                        {readinessScore !== null ? (
                          <span
                            className={styles.scoreBadge}
                            style={{
                              color: readinessScore >= 75 ? '#15803d' : '#b45309',
                              backgroundColor: readinessScore >= 75 ? '#dcfce7' : '#fef3c7',
                            }}
                          >
                            {readinessScore}%
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8' }}>—</span>
                        )}
                      </td>
                      <td>
                        {matchScore !== null ? (
                          <span
                            className={styles.scoreBadge}
                            style={{
                              color: matchScore >= 80 ? '#15803d' : '#b45309',
                              backgroundColor: matchScore >= 80 ? '#dcfce7' : '#fef3c7',
                            }}
                          >
                            {matchScore}%
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8' }}>—</span>
                        )}
                      </td>
                      <td>
                        {riskLevel ? (
                          <span
                            className={styles.riskBadge}
                            style={{
                              color:
                                riskLevel === 'HIGH'
                                  ? '#b91c1c'
                                  : riskLevel === 'MEDIUM'
                                  ? '#b45309'
                                  : '#15803d',
                              backgroundColor:
                                riskLevel === 'HIGH'
                                  ? '#fee2e2'
                                  : riskLevel === 'MEDIUM'
                                  ? '#fef3c7'
                                  : '#dcfce7',
                            }}
                          >
                            {riskLevel}
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8' }}>—</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <Link
                          to={`/admin/review/${app.id || app.application_number}`}
                          className={styles.reviewBtn}
                        >
                          Review
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div className={styles.pagination}>
          <span className={styles.pageInfo}>
            Showing <strong>{applications.length}</strong> of <strong>{total}</strong> applications
          </span>
          <div className={styles.pageBtns}>
            <button
              className={styles.pageBtn}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              <ChevronLeft size={16} /> Prev
            </button>
            <span className={styles.pageNumber}>
              Page {page} of {totalPages}
            </span>
            <button
              className={styles.pageBtn}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
