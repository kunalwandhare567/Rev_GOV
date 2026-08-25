/**
 * statusMap.js — Single source of truth for frontend application status translation.
 * Maps backend status values to citizen-friendly labels, colors, and icons.
 * Backend status values are NEVER renamed here — only mapped to UI equivalents.
 */

export const STATUS_UI_MAP = {
  DRAFT:                       { label: 'Draft',                    group: 'in_progress', color: 'neutral', icon: 'draft',             progress: 5   },
  INITIATED:                   { label: 'Initiated',                group: 'in_progress', color: 'neutral', icon: 'edit_note',         progress: 10  },
  CONSENT_GIVEN:               { label: 'Consent Given',            group: 'in_progress', color: 'info',    icon: 'check',             progress: 15  },
  SERVICE_SELECTED:            { label: 'Service Selected',         group: 'in_progress', color: 'info',    icon: 'list_alt',          progress: 20  },
  INFORMATION_COLLECTION:      { label: 'Filling Information',      group: 'in_progress', color: 'info',    icon: 'edit_note',          progress: 30  },
  DOCUMENT_COLLECTION:         { label: 'Documents Pending',        group: 'in_progress', color: 'warning', icon: 'upload_file',        progress: 45  },
  OCR_PROCESSING:              { label: 'Analysing Documents',      group: 'in_progress', color: 'info',    icon: 'document_scanner',   progress: 55  },
  OCR_VALIDATION:              { label: 'Analysing Documents',      group: 'in_progress', color: 'info',    icon: 'document_scanner',   progress: 55  },
  VALIDATION_COMPLETED:        { label: 'Validation Completed',     group: 'in_progress', color: 'info',    icon: 'verified',           progress: 60  },
  READINESS_CHECK:             { label: 'Readiness Check',          group: 'in_progress', color: 'info',    icon: 'fact_check',         progress: 65  },
  FIX_REQUIRED:                { label: 'Correction Required',      group: 'action',      color: 'warning', icon: 'warning',            progress: 50  },
  READY_FOR_REVIEW:            { label: 'Ready for Review',         group: 'in_progress', color: 'primary', icon: 'rate_review',        progress: 70  },
  FINAL_REVIEW:                { label: 'Ready to Submit',          group: 'in_progress', color: 'primary', icon: 'rate_review',        progress: 72  },
  CONSENT_CONFIRMED:           { label: 'Consent Confirmed',        group: 'in_progress', color: 'primary', icon: 'check_circle',       progress: 75  },
  SUBMITTED_FOR_VERIFICATION:  { label: 'Submitted for Review',     group: 'in_progress', color: 'primary', icon: 'send',               progress: 78  },
  SUBMITTED:                   { label: 'Submitted for Review',     group: 'in_progress', color: 'primary', icon: 'send',               progress: 78  },
  UNDER_REVIEW:                { label: 'Officer Review',           group: 'in_progress', color: 'info',    icon: 'gavel',              progress: 83  },
  PENDING_OFFICER_PRE_APPROVAL:{ label: 'Officer Review',           group: 'in_progress', color: 'info',    icon: 'gavel',              progress: 83  },
  CLARIFICATION_REQUIRED:      { label: 'Action Required',          group: 'action',      color: 'warning', icon: 'warning',            progress: 50  },
  APPROVED:                    { label: 'Approved',                 group: 'in_progress', color: 'success', icon: 'task_alt',           progress: 88  },
  PAYMENT_REQUIRED:            { label: 'Payment Required',         group: 'action',      color: 'warning', icon: 'payments',           progress: 90  },
  PAYMENT_PENDING:             { label: 'Payment Required',         group: 'action',      color: 'warning', icon: 'payments',           progress: 90  },
  PAYMENT_COMPLETED:           { label: 'Payment Confirmed',        group: 'in_progress', color: 'success', icon: 'check_circle',       progress: 93  },
  CERTIFICATE_GENERATION:      { label: 'Generating Certificate',   group: 'in_progress', color: 'info',    icon: 'sync',               progress: 96  },
  CERTIFICATE_READY:           { label: 'Certificate Ready',        group: 'completed',   color: 'success', icon: 'workspace_premium',  progress: 99  },
  COMPLETED:                   { label: 'Completed',                group: 'completed',   color: 'success', icon: 'verified',           progress: 100 },
  REJECTED:                    { label: 'Rejected',                 group: 'rejected',    color: 'error',   icon: 'cancel',             progress: 100 },
  ESCALATED:                   { label: 'Escalated',                group: 'in_progress', color: 'warning', icon: 'priority_high',      progress: 75  },
}

/**
 * Get UI config for a given backend status. Falls back gracefully.
 */
export const getStatusUI = (backendStatus) =>
  STATUS_UI_MAP[backendStatus] || {
    label:    backendStatus?.replace(/_/g, ' ') || 'Unknown',
    group:    'in_progress',
    color:    'neutral',
    icon:     'info',
    progress: 50,
  }

/**
 * Filter groups for the My Applications tab filter pills.
 * null means "show all"
 */
export const FILTER_GROUPS = {
  'All Applications': null,
  'In Progress':      ['in_progress', 'action'],
  'Completed':        ['completed'],
  'Rejected':         ['rejected'],
}

/**
 * 4-stage visual application timeline (used in application cards).
 * Each stage checks the current status against doneStatuses and activeStatuses.
 */
export const TIMELINE_STAGES = [
  {
    key:           'submitted',
    label:         'Application Submitted',
    icon:          'assignment_turned_in',
    doneStatuses:  [
      'DOCUMENT_COLLECTION','OCR_PROCESSING','OCR_VALIDATION','VALIDATION_COMPLETED',
      'READINESS_CHECK','READY_FOR_REVIEW','FINAL_REVIEW','CONSENT_CONFIRMED',
      'SUBMITTED_FOR_VERIFICATION','SUBMITTED','UNDER_REVIEW','PENDING_OFFICER_PRE_APPROVAL',
      'APPROVED','PAYMENT_REQUIRED','PAYMENT_PENDING','PAYMENT_COMPLETED',
      'CERTIFICATE_GENERATION','CERTIFICATE_READY','COMPLETED','CLARIFICATION_REQUIRED',
    ],
    activeStatuses:['INITIATED','CONSENT_GIVEN','SERVICE_SELECTED','INFORMATION_COLLECTION'],
  },
  {
    key:           'docs',
    label:         'Documents Verified',
    icon:          'verified',
    doneStatuses:  [
      'READINESS_CHECK','READY_FOR_REVIEW','FINAL_REVIEW','CONSENT_CONFIRMED',
      'SUBMITTED_FOR_VERIFICATION','SUBMITTED','UNDER_REVIEW','PENDING_OFFICER_PRE_APPROVAL',
      'APPROVED','PAYMENT_REQUIRED','PAYMENT_PENDING','PAYMENT_COMPLETED',
      'CERTIFICATE_GENERATION','CERTIFICATE_READY','COMPLETED',
    ],
    activeStatuses:['DOCUMENT_COLLECTION','OCR_PROCESSING','OCR_VALIDATION','VALIDATION_COMPLETED','FIX_REQUIRED','CLARIFICATION_REQUIRED'],
  },
  {
    key:           'review',
    label:         'Officer Review',
    icon:          'gavel',
    doneStatuses:  ['APPROVED','PAYMENT_REQUIRED','PAYMENT_PENDING','PAYMENT_COMPLETED','CERTIFICATE_GENERATION','CERTIFICATE_READY','COMPLETED'],
    activeStatuses:['SUBMITTED_FOR_VERIFICATION','SUBMITTED','UNDER_REVIEW','PENDING_OFFICER_PRE_APPROVAL','CLARIFICATION_REQUIRED'],
  },
  {
    key:           'approval',
    label:         'Final Approval',
    icon:          'workspace_premium',
    doneStatuses:  ['APPROVED','PAYMENT_REQUIRED','PAYMENT_PENDING','PAYMENT_COMPLETED','CERTIFICATE_GENERATION','CERTIFICATE_READY','COMPLETED'],
    activeStatuses:['UNDER_REVIEW'],
  },
]

/**
 * Compute OCR score category and human-friendly explanation.
 */
export const getOCRCategory = (score) => {
  if (score == null) return { label: 'Not processed', color: 'var(--rg-text-body)', cls: 'ocr-neutral', explanation: 'Document has not been processed yet.' }
  if (score >= 90) return { label: 'Excellent',          color: 'var(--rg-success)',  cls: 'ocr-excellent', explanation: 'All fields were clearly read from the document.' }
  if (score >= 75) return { label: 'Good',               color: '#16a34a',            cls: 'ocr-good',      explanation: 'Most fields were read correctly with minor issues.' }
  if (score >= 60) return { label: 'Fair — needs attention', color: 'var(--rg-warning)', cls: 'ocr-fair',   explanation: 'Some text was difficult to read. Please review the highlighted fields.' }
  return                 { label: 'Poor — re-upload required', color: 'var(--rg-error)', cls: 'ocr-poor',   explanation: 'The document image is unclear or partially obscured. Uploading a clearer scan will improve your verification score.' }
}

/**
 * Map of service IDs to Material Symbol icons.
 */
export const SERVICE_ICONS = {
  income_certificate:   'badge',
  caste_certificate:    'verified',
  obc_ncl_certificate:  'groups',
  domicile_certificate: 'home_work',
}

/**
 * Map timeline stage state for a given status.
 */
export const getTimelineState = (stage, status) => {
  if (stage.doneStatuses.includes(status))   return 'done'
  if (stage.activeStatuses?.includes(status)) return 'active'
  if (status === 'REJECTED')                  return 'rejected'
  return 'pending'
}
