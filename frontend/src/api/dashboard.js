import client from './client'

export const dashboardApi = {
  getOverview:      ()          => client.get('/dashboard/overview'),
  getAuditLog:      (limit = 50, eventType = null) =>
    client.get(`/dashboard/audit-log?limit=${limit}${eventType ? `&event_type=${eventType}` : ''}`),
  getDataGuardStats:()          => client.get('/dashboard/data-guard-stats'),
  getEscalations:   ()          => client.get('/dashboard/escalations'),
  getServiceHealth: ()          => client.get('/dashboard/service-health'),
}
