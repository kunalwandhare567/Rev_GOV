/**
 * Phase 11 — ApplicationReviewPage.jsx
 * 4-Section Citizen Application Review Form
 *
 * Sections:
 *   1. Basic / Application Details
 *   2. Personal & Family Details
 *   3. Documents & Validation (OCR status + match scores + mismatch resolution)
 *   4. Final Review (Readiness Score + Consent + Submit)
 *
 * Rules:
 * - All data loaded from backend API (never computed in frontend)
 * - Submit button disabled until readiness ≥ 75 AND consent checked
 * - Readiness score fetched from GET /api/v1/applications/{id}/readiness
 * - Submit triggers POST /api/v1/mock-government/submit
 */

import { useState, useEffect, useCallback } from 'react'
import styles from './ApplicationReviewPage.module.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// ─── Field Label Map ───────────────────────────────────────────────────────────
const FIELD_LABELS = {
  applicant_name: 'Full Name',
  applicant_dob: 'Date of Birth',
  gender: 'Gender',
  mobile_number: 'Mobile Number',
  email: 'Email Address',
  father_name: "Father's Name",
  mother_name: "Mother's Name",
  aadhaar_number: 'Aadhaar Number',
  address: 'Address',
  district: 'District',
  taluka: 'Taluka',
  village: 'Village/Ward',
  occupation: 'Occupation',
  annual_income: 'Annual Income (₹)',
  family_member_count: 'Family Members',
  earning_family_members: 'Earning Members',
  annual_family_income: 'Annual Family Income (₹)',
  purpose: 'Purpose',
}

const SECTION_1_FIELDS = ['applicant_name', 'applicant_dob', 'gender', 'mobile_number', 'email', 'purpose']
const SECTION_2_FIELDS = ['father_name', 'mother_name', 'aadhaar_number', 'address', 'district', 'taluka', 'village', 'occupation', 'annual_income', 'family_member_count', 'earning_family_members', 'annual_family_income']

// ─── Status Color Helper ───────────────────────────────────────────────────────
function statusColor(status) {
  if (!status) return '#6b7280'
  const s = status.toUpperCase()
  if (['COMPLETED', 'VALIDATED', 'MISMATCH_RESOLVED'].includes(s)) return '#10b981'
  if (s === 'MISMATCH') return '#f59e0b'
  if (['FAILED', 'ERROR'].includes(s)) return '#ef4444'
  return '#6b7280'
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function ApplicationReviewPage({ applicationNumber, onSubmitSuccess }) {
  const [activeSection, setActiveSection] = useState(1)
  const [application, setApplication] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [evidenceGraph, setEvidenceGraph] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [consentChecked, setConsentChecked] = useState(false)
  const [error, setError] = useState(null)
  const [submitSuccess, setSubmitSuccess] = useState(false)
  const [mismatchChoices, setMismatchChoices] = useState({}) // fieldName → 'declared' | 'doc'

  // ─── Load Application Data ────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    if (!applicationNumber) return
    setLoading(true)
    setError(null)

    try {
      const [appRes, readinessRes, graphRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/applications/status/${applicationNumber}`),
        fetch(`${API_BASE}/api/v1/applications/${applicationNumber}/readiness`),
        fetch(`${API_BASE}/api/v1/applications/${applicationNumber}/evidence-graph`),
      ])

      if (!appRes.ok) throw new Error(`Application not found (${appRes.status})`)

      const appData = await appRes.json()
      const readinessData = readinessRes.ok ? await readinessRes.json() : null
      const graphData = graphRes.ok ? await graphRes.json() : null

      setApplication(appData)
      setReadiness(readinessData)
      setEvidenceGraph(graphData)
    } catch (err) {
      console.error('Failed to load application:', err)
      setError(err.message || 'Failed to load application data.')
    } finally {
      setLoading(false)
    }
  }, [applicationNumber])

  useEffect(() => { loadData() }, [loadData])

  // ─── Submit Application ───────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!readiness?.can_submit || !consentChecked) return
    setSubmitting(true)
    setError(null)

    try {
      const trackingId = application?.tracking_id || applicationNumber
      const citizenRef = application?.citizen_identifier || ''

      const res = await fetch(`${API_BASE}/api/v1/mock-government/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tracking_id: trackingId,
          citizen_ref: citizenRef,
        }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Submission failed (${res.status})`)
      }

      const data = await res.json()
      setSubmitSuccess(true)
      if (onSubmitSuccess) onSubmitSuccess(data)
    } catch (err) {
      console.error('Submit error:', err)
      setError(err.message || 'Submission failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  // ─── Render Helpers ───────────────────────────────────────────────────────
  const filledSlots = application?.submitted_data || application?.filled_slots || {}
  const documents = application?.documents || []
  const serviceName = application?.service_name || application?.service_id?.replace(/_/g, ' ') || 'Certificate'

  const readinessScore = readiness?.overall_score ?? null
  const canSubmit = readiness?.can_submit && consentChecked
  const blockingIssues = readiness?.blocking_issues || []

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.spinner} />
        <p>Loading your application…</p>
      </div>
    )
  }

  if (error && !application) {
    return (
      <div className={styles.errorContainer}>
        <div className={styles.errorIcon}>⚠️</div>
        <h3>Could not load application</h3>
        <p>{error}</p>
        <button className={styles.retryBtn} onClick={loadData}>Retry</button>
      </div>
    )
  }

  if (submitSuccess) {
    return (
      <div className={styles.successContainer}>
        <div className={styles.successIcon}>🎉</div>
        <h2>Application Submitted!</h2>
        <p>Your application has been submitted to the Revenue Department.</p>
        <p className={styles.trackingId}>
          Tracking ID: <strong>{application?.tracking_id || applicationNumber}</strong>
        </p>
        <p>You will receive a notification when it is reviewed.</p>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      {/* ── Header ── */}
      <div className={styles.header}>
        <div className={styles.serviceTitle}>
          {serviceName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
        </div>
        <div className={styles.trackingBadge}>
          {application?.tracking_id && <>Tracking: <strong>{application.tracking_id}</strong></>}
        </div>
        {readinessScore !== null && (
          <div className={styles.readinessBadge}
            style={{ background: readinessScore >= 90 ? '#10b981' : readinessScore >= 75 ? '#f59e0b' : '#ef4444' }}>
            Readiness: {readinessScore}/100
          </div>
        )}
      </div>

      {/* ── Section Tabs ── */}
      <div className={styles.tabs}>
        {[
          { n: 1, label: '① Basic Details' },
          { n: 2, label: '② Personal & Family' },
          { n: 3, label: '③ Documents' },
          { n: 4, label: '④ Final Review' },
        ].map(({ n, label }) => (
          <button
            key={n}
            className={`${styles.tab} ${activeSection === n ? styles.tabActive : ''}`}
            onClick={() => setActiveSection(n)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ─────────────── SECTION 1: Basic Details ─────────────── */}
      {activeSection === 1 && (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>Application Details</h2>
          <p className={styles.sectionSubtitle}>
            Review your basic application information. These details will appear on your certificate.
          </p>
          <div className={styles.fieldGrid}>
            {SECTION_1_FIELDS.map(field => (
              <div key={field} className={styles.fieldCard}>
                <div className={styles.fieldLabel}>{FIELD_LABELS[field] || field}</div>
                <div className={styles.fieldValue}>
                  {filledSlots[field]
                    ? String(filledSlots[field])
                    : <span className={styles.missingValue}>Not provided</span>
                  }
                </div>
                {evidenceGraph?.fields?.[field] && (
                  <div className={styles.fieldVerification}>
                    {evidenceGraph.fields[field].verified
                      ? <span className={styles.verified}>✓ Verified by document</span>
                      : evidenceGraph.fields[field].conflicting
                        ? <span className={styles.conflict}>⚠ Mismatch with document</span>
                        : <span className={styles.noEvidence}>○ No document evidence</span>
                    }
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className={styles.navBtns}>
            <button className={styles.nextBtn} onClick={() => setActiveSection(2)}>
              Next: Personal & Family Details →
            </button>
          </div>
        </div>
      )}

      {/* ─────────────── SECTION 2: Personal & Family ─────────────── */}
      {activeSection === 2 && (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>Personal & Family Details</h2>
          <p className={styles.sectionSubtitle}>
            Family and income information used for eligibility determination.
          </p>
          <div className={styles.fieldGrid}>
            {SECTION_2_FIELDS.map(field => (
              <div key={field} className={styles.fieldCard}>
                <div className={styles.fieldLabel}>{FIELD_LABELS[field] || field}</div>
                <div className={styles.fieldValue}>
                  {filledSlots[field]
                    ? field.includes('income') || field.includes('Income')
                      ? `₹${Number(filledSlots[field]).toLocaleString('en-IN')}`
                      : String(filledSlots[field])
                    : <span className={styles.missingValue}>Not provided</span>
                  }
                </div>
                {evidenceGraph?.fields?.[field] && (
                  <div className={styles.fieldVerification}>
                    {evidenceGraph.fields[field].verified
                      ? <span className={styles.verified}>✓ Verified</span>
                      : evidenceGraph.fields[field].conflicting
                        ? <span className={styles.conflict}>⚠ Mismatch</span>
                        : <span className={styles.noEvidence}>○ Unverified</span>
                    }
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className={styles.navBtns}>
            <button className={styles.prevBtn} onClick={() => setActiveSection(1)}>← Back</button>
            <button className={styles.nextBtn} onClick={() => setActiveSection(3)}>
              Next: Documents →
            </button>
          </div>
        </div>
      )}

      {/* ─────────────── SECTION 3: Documents & Validation ─────────────── */}
      {activeSection === 3 && (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>Documents & Validation</h2>
          <p className={styles.sectionSubtitle}>
            Review your uploaded documents and OCR validation results.
          </p>

          {documents.length === 0 ? (
            <div className={styles.noDocuments}>
              <span>📄</span> No documents uploaded yet.
            </div>
          ) : (
            documents.map((doc, idx) => {
              const docType = doc.doc_type || doc.document_type || `Document ${idx + 1}`
              const status = doc.ocr_status || doc.validation_status || 'PENDING'
              const matchScore = doc.match_score || 0
              const matchResult = doc.match_result || {}
              const matchedFields = matchResult.matched_fields || []
              const mismatchedFields = matchResult.mismatched_fields || []

              return (
                <div key={idx} className={styles.docCard}>
                  <div className={styles.docHeader}>
                    <span className={styles.docType}>
                      📄 {docType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                    <span className={styles.docStatus} style={{ color: statusColor(status) }}>
                      {status}
                    </span>
                  </div>

                  {/* Match Score Bar */}
                  {matchScore > 0 && (
                    <div className={styles.matchBar}>
                      <div className={styles.matchBarLabel}>
                        Overall Match: <strong>{matchScore}%</strong>
                      </div>
                      <div className={styles.matchBarTrack}>
                        <div
                          className={styles.matchBarFill}
                          style={{
                            width: `${matchScore}%`,
                            background: matchScore >= 90 ? '#10b981' : matchScore >= 70 ? '#f59e0b' : '#ef4444'
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Matched Fields */}
                  {matchedFields.length > 0 && (
                    <div className={styles.fieldMatches}>
                      <div className={styles.matchGroupTitle}>✅ Matched Fields</div>
                      {matchedFields.map((f, i) => (
                        <div key={i} className={styles.matchedField}>
                          <span>{FIELD_LABELS[f.field] || f.field}</span>
                          <span className={styles.matchScore}>{f.score ?? 100}%</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Mismatched Fields — with resolution UI */}
                  {mismatchedFields.length > 0 && (
                    <div className={styles.fieldMismatches}>
                      <div className={styles.mismatchGroupTitle}>⚠️ Mismatched Fields</div>
                      {mismatchedFields.map((f, i) => (
                        <div key={i} className={styles.mismatchCard}>
                          <div className={styles.mismatchFieldName}>
                            {FIELD_LABELS[f.field] || f.field}
                          </div>
                          <div className={styles.mismatchValues}>
                            <div className={styles.mismatchDeclared}>
                              <span className={styles.mismatchLabel}>Declared:</span>
                              <span>{f.declared_value || '—'}</span>
                            </div>
                            <div className={styles.mismatchDoc}>
                              <span className={styles.mismatchLabel}>Document:</span>
                              <span>{f.doc_value || '—'}</span>
                            </div>
                            <div className={styles.mismatchScore}>Match: {f.score ?? 0}%</div>
                          </div>
                          <div className={styles.mismatchResolution}>
                            <span className={styles.mismatchResLabel}>Keep which value?</span>
                            <div className={styles.mismatchBtns}>
                              <button
                                className={`${styles.mismatchBtn} ${mismatchChoices[f.field] === 'declared' ? styles.mismatchBtnActive : ''}`}
                                onClick={() => setMismatchChoices(c => ({ ...c, [f.field]: 'declared' }))}
                              >
                                Keep: "{f.declared_value}"
                              </button>
                              <button
                                className={`${styles.mismatchBtn} ${mismatchChoices[f.field] === 'doc' ? styles.mismatchBtnActiveDoc : ''}`}
                                onClick={() => setMismatchChoices(c => ({ ...c, [f.field]: 'doc' }))}
                              >
                                Use document: "{f.doc_value}"
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })
          )}

          <div className={styles.navBtns}>
            <button className={styles.prevBtn} onClick={() => setActiveSection(2)}>← Back</button>
            <button className={styles.nextBtn} onClick={() => setActiveSection(4)}>
              Next: Final Review →
            </button>
          </div>
        </div>
      )}

      {/* ─────────────── SECTION 4: Final Review & Submit ─────────────── */}
      {activeSection === 4 && (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>Final Review & Submit</h2>
          <p className={styles.sectionSubtitle}>
            Review your readiness score, confirm the declaration, and submit your application.
          </p>

          {/* Readiness Score */}
          {readiness && (
            <div className={styles.readinessPanel}>
              <div className={styles.readinessHeader}>
                <div className={styles.readinessTitle}>Application Readiness</div>
                <div
                  className={styles.readinessScore}
                  style={{ color: readinessScore >= 90 ? '#10b981' : readinessScore >= 75 ? '#f59e0b' : '#ef4444' }}
                >
                  {readinessScore}/100
                </div>
                <div className={styles.readinessStatus}>
                  {readiness.status === 'READY' && '✅ Ready to Submit'}
                  {readiness.status === 'MINOR_ISSUES' && '⚡ Minor Issues — Can Still Submit'}
                  {readiness.status === 'MODERATE_ISSUES' && '⚠️ Moderate Issues — Please Fix Before Submitting'}
                  {readiness.status === 'MAJOR_ISSUES' && '❌ Major Issues — Cannot Submit Yet'}
                </div>
              </div>

              {/* Component Breakdown */}
              <div className={styles.readinessComponents}>
                {readiness.components?.map((comp, i) => (
                  <div key={i} className={styles.readinessComp}>
                    <div className={styles.readinessCompName}>{comp.name}</div>
                    <div className={styles.readinessCompBar}>
                      <div
                        className={styles.readinessCompFill}
                        style={{
                          width: `${comp.score_pct}%`,
                          background: comp.score_pct >= 90 ? '#10b981' : comp.score_pct >= 60 ? '#f59e0b' : '#ef4444'
                        }}
                      />
                    </div>
                    <div className={styles.readinessCompScore}>{comp.weighted_score}/{comp.weight}</div>
                  </div>
                ))}
              </div>

              {/* Blocking Issues */}
              {blockingIssues.length > 0 && (
                <div className={styles.blockingIssues}>
                  <div className={styles.blockingTitle}>❌ Issues to Resolve Before Submitting:</div>
                  {blockingIssues.map((issue, i) => (
                    <div key={i} className={styles.blockingIssue}>• {issue}</div>
                  ))}
                </div>
              )}

              {/* Warnings */}
              {readiness.warnings?.length > 0 && (
                <div className={styles.warnings}>
                  <div className={styles.warningsTitle}>⚠️ Warnings (non-blocking):</div>
                  {readiness.warnings.map((w, i) => (
                    <div key={i} className={styles.warning}>• {w}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Data Summary */}
          <div className={styles.summaryPanel}>
            <h3 className={styles.summaryTitle}>Your Information Summary</h3>
            <div className={styles.summaryGrid}>
              {Object.entries(filledSlots).map(([key, value]) => (
                <div key={key} className={styles.summaryField}>
                  <span className={styles.summaryKey}>{FIELD_LABELS[key] || key}:</span>
                  <span className={styles.summaryValue}>
                    {key.includes('income') ? `₹${Number(value).toLocaleString('en-IN')}` : String(value)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Consent */}
          <div className={styles.consentPanel}>
            <label className={styles.consentLabel}>
              <input
                type="checkbox"
                className={styles.consentCheckbox}
                checked={consentChecked}
                onChange={e => setConsentChecked(e.target.checked)}
                disabled={!readiness?.can_submit}
              />
              <span>
                I hereby declare that all the information provided in this application is true and correct
                to the best of my knowledge. I understand that providing false information is an offence
                under applicable law. I consent to the Revenue Department verifying and using this
                information to process my application.
              </span>
            </label>
          </div>

          {/* Error */}
          {error && (
            <div className={styles.errorBox}>⚠️ {error}</div>
          )}

          {/* Submit Button */}
          <div className={styles.submitArea}>
            <button
              className={styles.submitBtn}
              disabled={!canSubmit || submitting}
              onClick={handleSubmit}
              title={
                !readiness?.can_submit
                  ? `Readiness score too low (${readinessScore}/100 — need 75+)`
                  : !consentChecked
                    ? 'Please check the consent declaration'
                    : 'Submit your application'
              }
            >
              {submitting ? '⏳ Submitting…' : '📤 Submit Application'}
            </button>
            {!readiness?.can_submit && readinessScore !== null && (
              <p className={styles.submitHint}>
                Readiness score {readinessScore}/100. Minimum 75 required to submit.
              </p>
            )}
            {readiness?.can_submit && !consentChecked && (
              <p className={styles.submitHint}>
                Please check the consent declaration above to enable submission.
              </p>
            )}
          </div>

          <div className={styles.navBtns}>
            <button className={styles.prevBtn} onClick={() => setActiveSection(3)}>← Back to Documents</button>
          </div>
        </div>
      )}
    </div>
  )
}
