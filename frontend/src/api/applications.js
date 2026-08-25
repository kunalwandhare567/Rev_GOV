import client from './client'

export const applicationsApi = {
  listServices: ()           => client.get('/applications/services'),
  getService:   (id)         => client.get(`/applications/services/${id}`),
  getStatus:    (appNum)     => client.get(`/applications/status/${appNum}`),
  getMyApplications: ()      => client.get('/applications/my-applications'),
  getCitizenApps: (id)       => client.get(`/applications/citizen/${id}`),
  getRecent:    (limit = 20) => client.get(`/applications/recent?limit=${limit}`),
  getById:      (id)         => client.get(`/applications/${id}`),
  updateStatus: (appNum, status, note = '') =>
    client.patch(`/applications/status/${appNum}`, { status, note }),
  validateEligibility: (serviceId, slots) =>
    client.post('/applications/validate-eligibility', { service_id: serviceId, slots }),
}
