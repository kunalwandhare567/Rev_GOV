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
  DRAFT:        { color: '#6b7280', bg: '#f3f4f6', dot: '#9ca3af' },
  SUBMITTED:    { color: '#4338ca', bg: '#eef2ff', dot: '#6366f1' },
  UNDER_REVIEW: { color: '#b45309', bg: '#fffbeb', dot: '#f59e0b' },
  APPROVED:     { color: '#15803d', bg: '#f0fdf4', dot: '#22c55e' },
  REJECTED:     { color: '#b91c1c', bg: '#fef2f2', dot: '#ef4444' },
  ESCALATED:    { color: '#7e22ce', bg: '#fdf4ff', dot: '#a855f7' },
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
