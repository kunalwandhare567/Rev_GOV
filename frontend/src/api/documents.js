import client from './client'

export const documentsApi = {
  /** Get all documents for an application with OCR scores */
  getDocuments: (appId) =>
    client.get(`/applications/${appId}/documents`),

  /** Get all fields with provenance metadata */
  getFields: (appId) =>
    client.get(`/applications/${appId}/fields`),

  /** Update a single declared field */
  updateField: (appId, fieldName, value, reason = null) =>
    client.put(`/applications/${appId}/fields/${fieldName}`, {
      value,
      source: 'WEB_EDIT',
      override_reason: reason,
    }),

  /** Resolve OCR mismatch between declared data and OCR extracted value */
  resolveMismatch: (appId, docId, field, resolution, manualValue = null) =>
    client.post(`/applications/${appId}/documents/${docId}/resolve`, {
      field,
      resolution,
      manual_value: manualValue,
    }),

  /** Submit application for admin verification */
  submitForVerification: (appId) =>
    client.post(`/applications/${appId}/submit`),

  /** Update a specific OCR field value for a document */
  updateOcrField: (appId, docId, fieldName, newValue) =>
    client.post(`/applications/${appId}/documents/${docId}/update-ocr-field`, {
      field_name: fieldName,
      new_value: newValue,
    }),

  /** Get application readiness score (0–100) */
  getReadiness: (appNumber) =>
    client.get(`/applications/${appNumber}/readiness`),

  /** Get document image URL for preview */
  getDocumentImageUrl: (appId, docId) =>
    `${client.defaults.baseURL}/applications/${appId}/documents/${docId}/image`,
}
