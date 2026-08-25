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

  // ── Authoritative Admin APIs ──
  getAdminList: (params = {}) => client.get('/applications/admin/list', { params }),
  getAdminDetail: (idOrNumber) => client.get(`/applications/admin/${idOrNumber}`),
  submitDecision: (idOrNumber, decision, reason = '', adminNotes = '') =>
    client.post(`/applications/admin/${idOrNumber}/decision`, {
      decision,
      reason: reason || null,
      admin_notes: adminNotes || null,
    }),
  submitForVerification: (idOrNumber) => client.post(`/applications/${idOrNumber}/submit`),

  // ── Citizen Payment & Certificate APIs ──
  initiatePayment: (applicationId, citizenIdentifier, amount = 50.0) =>
    client.post('/payment/initiate', {
      application_id: applicationId,
      citizen_identifier: citizenIdentifier,
      amount,
      channel: 'WEB',
      mode: 'MOCK_AUTO',
    }),
}

