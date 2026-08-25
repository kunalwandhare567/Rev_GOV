export const SERVICE_IDS = {
  INCOME:  'income_certificate',
  CASTE:   'caste_certificate',
  OBC_NCL: 'obc_ncl_certificate',
  DOMICILE:'domicile_certificate',
}

export const CONV_NODES = {
  INIT:             'INIT',
  CONSENT:          'CONSENT',
  INTENT_DETECTION: 'INTENT_DETECTION',
  SLOT_FILLING:     'SLOT_FILLING',
  DOCUMENT_CAPTURE: 'DOCUMENT_CAPTURE',
  VALIDATION:       'VALIDATION',
  PAYMENT:          'PAYMENT',
  SUBMITTED:        'SUBMITTED',
  ESCALATED:        'ESCALATED',
}

export const NODE_STEPS = [
  CONV_NODES.CONSENT,
  CONV_NODES.INTENT_DETECTION,
  CONV_NODES.SLOT_FILLING,
  CONV_NODES.DOCUMENT_CAPTURE,
  CONV_NODES.VALIDATION,
  CONV_NODES.PAYMENT,
  CONV_NODES.SUBMITTED,
]

export const APP_STATUS = {
  DRAFT:        'DRAFT',
  SUBMITTED:    'SUBMITTED',
  UNDER_REVIEW: 'UNDER_REVIEW',
  APPROVED:     'APPROVED',
  REJECTED:     'REJECTED',
  ESCALATED:    'ESCALATED',
}

export const STATUS_CONFIG = {
  DRAFT:                      { label: 'Draft', color: '#64748b', bg: '#f1f5f9', dot: '#94a3b8' },
  INITIATED:                  { label: 'Initiated', color: '#64748b', bg: '#f1f5f9', dot: '#94a3b8' },
  INFORMATION_COLLECTION:     { label: 'Collecting Info', color: '#d97706', bg: '#fef3c7', dot: '#f59e0b' },
  DOCUMENT_COLLECTION:        { label: 'Collecting Docs', color: '#d97706', bg: '#fef3c7', dot: '#f59e0b' },
  OCR_PROCESSING:             { label: 'Processing OCR', color: '#2563eb', bg: '#eff6ff', dot: '#3b82f6' },
  VALIDATION_COMPLETED:       { label: 'Validated', color: '#0284c7', bg: '#e0f2fe', dot: '#0ea5e9' },
  READY_FOR_REVIEW:           { label: 'Ready for Review', color: '#0284c7', bg: '#e0f2fe', dot: '#0ea5e9' },
  FINAL_REVIEW:               { label: 'Final Review', color: '#0284c7', bg: '#e0f2fe', dot: '#0ea5e9' },
  CONSENT_CONFIRMED:          { label: 'Consent Confirmed', color: '#0284c7', bg: '#e0f2fe', dot: '#0ea5e9' },
  SUBMITTED:                  { label: 'Submitted', color: '#4f46e5', bg: '#eef2ff', dot: '#6366f1' },
  SUBMITTED_FOR_VERIFICATION: { label: 'Submitted', color: '#4f46e5', bg: '#eef2ff', dot: '#6366f1' },
  UNDER_REVIEW:               { label: 'Under Review', color: '#b45309', bg: '#fef3c7', dot: '#f59e0b' },
  CLARIFICATION_REQUIRED:     { label: 'Clarification Required', color: '#dc2626', bg: '#fee2e2', dot: '#ef4444' },
  APPROVED:                   { label: 'Approved', color: '#16a34a', bg: '#dcfce7', dot: '#22c55e' },
  PAYMENT_REQUIRED:           { label: 'Payment Required', color: '#ea580c', bg: '#ffedd5', dot: '#f97316' },
  PAYMENT_COMPLETED:          { label: 'Payment Completed', color: '#0891b2', bg: '#cffafe', dot: '#06b6d4' },
  CERTIFICATE_GENERATION:     { label: 'Generating Cert', color: '#0891b2', bg: '#cffafe', dot: '#06b6d4' },
  CERTIFICATE_READY:          { label: 'Certificate Ready', color: '#16a34a', bg: '#dcfce7', dot: '#22c55e' },
  COMPLETED:                  { label: 'Completed', color: '#15803d', bg: '#dcfce7', dot: '#16a34a' },
  REJECTED:                   { label: 'Rejected', color: '#b91c1c', bg: '#fee2e2', dot: '#ef4444' },
  ESCALATED:                  { label: 'Escalated', color: '#7e22ce', bg: '#f3e8ff', dot: '#a855f7' },
}

export const CHANNELS = ['WEB', 'WHATSAPP', 'IVR', 'MOBILE']
export const SUPPORTED_LANGS = ['en','hi','mr']

export const FRAUD_THRESHOLDS = {
  PASS_MAX:   0.40,
  REVIEW_MAX: 0.70,
}

export const EVENT_TYPE_CONFIG = {
  DATA_GUARD:    { color: '#ef4444', bg: '#fef2f2' },
  CONSENT:       { color: '#6366f1', bg: '#eef2ff' },
  SUBMISSION:    { color: '#22c55e', bg: '#f0fdf4' },
  PAYMENT:       { color: '#f59e0b', bg: '#fffbeb' },
  ESCALATION:    { color: '#a855f7', bg: '#fdf4ff' },
  STATUS_UPDATE: { color: '#0ea5e9', bg: '#f0f9ff' },
  FRAUD_REJECT:  { color: '#dc2626', bg: '#fef2f2' },
}

export const PRIORITY_CONFIG = {
  HIGH:   { color: '#ef4444', bg: '#fef2f2' },
  MEDIUM: { color: '#f59e0b', bg: '#fffbeb' },
  LOW:    { color: '#22c55e', bg: '#f0fdf4' },
}

export const ROLES = { ADMIN: 'ADMIN', OFFICER: 'OFFICER' }

export const STORAGE_KEYS = {
  AUTH_TOKEN:          'rsp_auth_token',
  AUTH_USER:           'rsp_auth_user',
  CITIZEN_IDENTIFIER:  'rsp_citizen_id',
  SESSION_ID:          'rsp_session_id',
  PREFERRED_LANG:      'rsp_lang',
  RECENT_SEARCHES:     'rsp_recent_searches',
}

export const POLL_INTERVALS = {
  DASHBOARD:     5000,
  LIVE_FEED:     3000,
  SERVICE_HEALTH:10000,
  ESCALATIONS:   10000,
}
