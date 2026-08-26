import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { applicationsApi } from '../../api/applications'
import { documentsApi } from '../../api/documents'
import useAuthStore from '../../store/authStore'
import useChatStore from '../../store/chatStore'
import { useRightPanel } from '../../layouts/RightPanelContext'
import { getOCRCategory } from '../../utils/statusMap'
import styles from './DocumentsPage.module.css'

const CHANNEL_ICONS = { WHATSAPP: '💬', WEB: '🌐', MOBILE: '📱', IVR: '📞', SYSTEM: '⚙️' }

function DocumentImagePanel({ appId, doc }) {
  if (!doc) return (
    <div className={styles.previewEmpty}>
      <span className="material-symbols-outlined" style={{ fontSize: 48, color: 'var(--rg-outline-variant)' }}>
        image_not_supported
      </span>
      <p>Select a document to preview</p>
    </div>
  )
  const imgUrl = documentsApi.getDocumentImageUrl(appId, doc.id)
  return (
    <div className={styles.previewPanel}>
      <div className={styles.previewHeader}>
        <span className={styles.previewDocType}>{doc.doc_type?.replace(/_/g, ' ')}</span>
        <span className={styles.previewChannel}>{CHANNEL_ICONS[doc.upload_channel]} {doc.upload_channel}</span>
      </div>
      <div className={styles.previewImageWrap}>
        <img
          src={imgUrl}
          alt={doc.doc_type}
          className={styles.previewImage}
          onError={e => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex' }}
        />
        <div className={styles.previewFallback} style={{ display: 'none' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 48, color: 'var(--rg-outline-variant)' }}>
            broken_image
          </span>
          <p>Preview not available</p>
          <span style={{ fontSize: '0.75rem', color: 'var(--rg-text-body)' }}>
            {doc.upload_channel === 'WHATSAPP'
              ? 'Document was uploaded via WhatsApp'
              : 'File preview unavailable'}
          </span>
        </div>
      </div>
      <div className={styles.previewMeta}>
        <span>Uploaded {new Date(doc.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
      </div>
    </div>
  )
}

function OCRScoreBar({ score, label }) {
  const cat = getOCRCategory(score)
  return (
    <div className={styles.ocrBarRow}>
      <span className={styles.ocrBarLabel}>{label}</span>
      <div className={styles.ocrBarTrack}>
        <div
          className={styles.ocrBarFill}
          style={{ width: `${score ?? 0}%`, background: cat.color }}
        />
      </div>
      <span className={styles.ocrBarScore} style={{ color: cat.color }}>{score != null ? `${Math.round(score)}%` : '—'}</span>
    </div>
  )
}

export default function DocumentsPage() {
  const navigate      = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient   = useQueryClient()
  const { citizenUser } = useAuthStore()
  const citizenIdentifier = useChatStore(s => s.citizenIdentifier) || citizenUser?.citizen_ref || localStorage.getItem('citizen_identifier')
  const { setRightPanel, clearRightPanel } = useRightPanel()

  const urlAppId  = searchParams.get('appId')
  const urlDocId  = searchParams.get('docId')

  const [selectedAppId,  setSelectedAppId]  = useState(urlAppId  || null)
  const [selectedDocId,  setSelectedDocId]  = useState(urlDocId  || null)
  const [mobileView,     setMobileView]     = useState('list')   // 'list' | 'detail'

  // Load my applications for the selector
  const { data: appsData } = useQuery({
    queryKey: ['myApplications', citizenIdentifier],
    queryFn:  () => applicationsApi.getMyApplications(citizenIdentifier),
    enabled:  true,
  })

  const apps = appsData?.applications || []

  // Auto-select first application
  useEffect(() => {
    if (!selectedAppId && apps.length > 0) {
      setSelectedAppId(apps[0].id)
    }
  }, [apps, selectedAppId])

  // Load documents for selected application
  const { data: documents = [], isLoading: docsLoading } = useQuery({
    queryKey: ['documents', selectedAppId],
    queryFn:  () => documentsApi.getDocuments(selectedAppId),
    enabled:  !!selectedAppId,
  })

  // Load fields for comparison
  const { data: fields = {} } = useQuery({
    queryKey: ['fields', selectedAppId],
    queryFn:  () => documentsApi.getFields(selectedAppId),
    enabled:  !!selectedAppId,
  })

  // Auto-select first doc or URL-specified doc
  useEffect(() => {
    if (documents.length > 0 && !selectedDocId) {
      setSelectedDocId(urlDocId || documents[0]?.id)
    }
    if (urlDocId) setSelectedDocId(urlDocId)
  }, [documents, urlDocId])

  const selectedDoc = documents.find(d => d.id === selectedDocId) || null
  const selectedApp = apps.find(a => a.id === selectedAppId) || null

  // Resolve mismatch mutation
  const resolveMutation = useMutation({
    mutationFn: ({ docId, field, resolution, manual }) =>
      documentsApi.resolveMismatch(selectedAppId, docId, field, resolution, manual),
    onSuccess: () => {
      toast.success('Mismatch resolved successfully')
      queryClient.invalidateQueries(['documents', selectedAppId])
    },
    onError: (err) => toast.error(err.message || 'Failed to resolve'),
  })

  // Submit for verification
  const submitMutation = useMutation({
    mutationFn: () => documentsApi.submitForVerification(selectedAppId),
    onSuccess: () => {
      toast.success('Application submitted for verification!')
      queryClient.invalidateQueries(['myApplications'])
      queryClient.invalidateQueries(['documents', selectedAppId])
    },
    onError: (err) => toast.error(err.message || 'Submission failed'),
  })

  // Set right panel = document image preview
  useEffect(() => {
    if (selectedDoc) {
      setRightPanel('Document Preview', <DocumentImagePanel appId={selectedAppId} doc={selectedDoc} />)
    }
    return () => clearRightPanel()
  }, [selectedDoc, selectedAppId])

  const hasMismatches = documents.some(d => d.mismatch_fields?.length > 0)
  const allResolved   = documents.every(d =>
    !d.mismatch_fields?.length ||
    d.mismatch_fields.every(f => d.mismatch_resolutions?.[f])
  )

  return (
    <div className={styles.page}>
      {/* Page Header */}
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Your Documents</h1>
          <p className={styles.pageSub}>Review OCR analysis and manage uploaded files</p>
        </div>
        {selectedApp && hasMismatches && !allResolved && (
          <div className={`status-chip chip-warning`}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>warning</span>
            Action required
          </div>
        )}
      </div>

      {/* App Selector */}
      {apps.length > 1 && (
        <div className={styles.appSelector}>
          <label className={styles.selectorLabel}>Application</label>
          <select
            className={styles.selectorInput}
            value={selectedAppId || ''}
            onChange={e => { setSelectedAppId(e.target.value); setSelectedDocId(null) }}
          >
            {apps.map(a => (
              <option key={a.id} value={a.id}>
                {a.application_number} — {a.service_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Mobile tab switch */}
      <div className={styles.mobileTabs}>
        <button
          className={`${styles.mobileTab} ${mobileView === 'list' ? styles.mobileTabActive : ''}`}
          onClick={() => setMobileView('list')}
        >Documents</button>
        <button
          className={`${styles.mobileTab} ${mobileView === 'detail' ? styles.mobileTabActive : ''}`}
          onClick={() => setMobileView('detail')}
          disabled={!selectedDoc}
        >OCR Analysis</button>
      </div>

      <div className={styles.body}>
        {/* Left — Document List */}
        <div className={`${styles.docList} ${mobileView === 'detail' ? styles.hideMobile : ''}`}>
          <div className={styles.docListHeader}>Uploaded Documents</div>

          {docsLoading ? (
            <div className={styles.loading}>
              <div className={styles.spinner} />
              <span>Loading documents…</span>
            </div>
          ) : documents.length === 0 ? (
            <div className={styles.emptyDocs}>
              <span className="material-symbols-outlined" style={{ fontSize: 48, color: 'var(--rg-outline-variant)' }}>
                upload_file
              </span>
              <p>No documents uploaded yet.</p>
              <p className={styles.emptyDocsSub}>
                Use the AI Assistant to upload documents as part of your application.
              </p>
              <button className={styles.goAssistantBtn} onClick={() => navigate('/assistant')}>
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>smart_toy</span>
                Go to Assistant
              </button>
            </div>
          ) : (
            <ul className={styles.docListItems}>
              {documents.map(doc => {
                const cat         = getOCRCategory(doc.overall_match_score)
                const hasMismatch = doc.mismatch_fields?.length > 0
                const resolved    = hasMismatch && doc.mismatch_fields.every(f => doc.mismatch_resolutions?.[f])
                const isSelected  = doc.id === selectedDocId

                return (
                  <li
                    key={doc.id}
                    className={`${styles.docItem} ${isSelected ? styles.docItemSelected : ''} ${hasMismatch && !resolved ? styles.docItemWarning : ''}`}
                    onClick={() => { setSelectedDocId(doc.id); setMobileView('detail') }}
                  >
                    <div className={styles.docItemIconWrap}>
                      {doc.verification_status === 'VERIFIED' ? (
                        <span className="material-symbols-outlined" style={{ color: 'var(--rg-success)', fontVariationSettings: "'FILL' 1" }}>
                          check_circle
                        </span>
                      ) : hasMismatch && !resolved ? (
                        <span className="material-symbols-outlined" style={{ color: 'var(--rg-warning)', fontVariationSettings: "'FILL' 1" }}>
                          warning
                        </span>
                      ) : (
                        <span className="material-symbols-outlined" style={{ color: 'var(--rg-outline)' }}>
                          description
                        </span>
                      )}
                    </div>
                    <div className={styles.docItemInfo}>
                      <div className={styles.docItemType}>{doc.doc_type?.replace(/_/g, ' ')}</div>
                      <div className={styles.docItemMeta}>
                        {CHANNEL_ICONS[doc.upload_channel]} via {doc.upload_channel}
                      </div>
                    </div>
                    <div className={styles.docItemRight}>
                      {doc.overall_match_score != null && (
                        <span className={styles.docItemScore} style={{ color: cat.color }}>
                          {Math.round(doc.overall_match_score)}%
                        </span>
                      )}
                      <span className={`status-chip ${
                        doc.verification_status === 'VERIFIED' ? 'chip-success' :
                        hasMismatch && !resolved ? 'chip-warning' : 'chip-neutral'
                      }`} style={{ fontSize: '0.6875rem', padding: '0.2rem 0.5rem' }}>
                        {doc.verification_status === 'VERIFIED' ? 'Verified' :
                         hasMismatch && !resolved ? 'Action Required' : doc.verification_status}
                      </span>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}

          {/* Submit for verification CTA */}
          {documents.length > 0 && allResolved && selectedApp && (
            <div className={styles.submitSection}>
              <p className={styles.submitNote}>
                All document mismatches resolved. Application ready to submit.
              </p>
              <button
                className={styles.submitBtn}
                onClick={() => submitMutation.mutate()}
                disabled={submitMutation.isPending}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>send</span>
                {submitMutation.isPending ? 'Submitting…' : 'Send for Verification'}
              </button>
            </div>
          )}
        </div>

        {/* Right — OCR Detail */}
        <div className={`${styles.docDetail} ${mobileView === 'list' ? styles.hideMobile : ''}`}>
          {!selectedDoc ? (
            <div className={styles.detailEmpty}>
              <span className="material-symbols-outlined" style={{ fontSize: 56, color: 'var(--rg-outline-variant)' }}>
                document_scanner
              </span>
              <p>Select a document to view OCR analysis</p>
            </div>
          ) : (
            <>
              {/* Doc header */}
              <div className={styles.detailHeader}>
                <div className={styles.detailDocName}>{selectedDoc.doc_type?.replace(/_/g, ' ')}</div>
                <div className={styles.detailDocMeta}>
                  Uploaded {new Date(selectedDoc.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} ·
                  via {CHANNEL_ICONS[selectedDoc.upload_channel]} {selectedDoc.upload_channel}
                </div>
                {selectedDoc.overall_match_score != null && (
                  <div className={styles.overallOCRBox}>
                    <div>
                      <div className={styles.overallOCRLabel}>OCR Confidence Score</div>
                      <div className={styles.overallOCRScore} style={{ color: getOCRCategory(selectedDoc.overall_match_score).color }}>
                        {Math.round(selectedDoc.overall_match_score)}%
                      </div>
                      <div className={styles.overallOCRCat}>{getOCRCategory(selectedDoc.overall_match_score).label}</div>
                    </div>
                    <div className={styles.overallOCRExplain}>
                      {getOCRCategory(selectedDoc.overall_match_score).explanation}
                    </div>
                  </div>
                )}
              </div>

              {/* Field Match Scores */}
              {selectedDoc.field_match_scores && Object.keys(selectedDoc.field_match_scores).length > 0 && (
                <div className={styles.detailSection}>
                  <div className={styles.detailSectionTitle}>Field Match Scores</div>
                  <div className={styles.ocrBars}>
                    {Object.entries(selectedDoc.field_match_scores).map(([field, data]) => (
                      <OCRScoreBar key={field} score={data.score} label={field.replace(/_/g, ' ')} />
                    ))}
                  </div>
                </div>
              )}

              {/* Field Comparison Table */}
              {selectedDoc.field_match_scores && Object.keys(selectedDoc.field_match_scores).length > 0 && (
                <div className={styles.detailSection}>
                  <div className={styles.detailSectionTitle}>Extracted Field Comparison</div>
                  <div className={styles.comparisonTable}>
                    <div className={styles.compTableHead}>
                      <span>Field</span>
                      <span>Your Input</span>
                      <span>OCR Read</span>
                      <span>Match</span>
                    </div>
                    {Object.entries(selectedDoc.field_match_scores).map(([field, data]) => {
                      const score  = data.score ?? 0
                      const cat    = getOCRCategory(score)
                      const myVal  = fields[field]?.value || data.app_value || '—'
                      const ocrVal = data.ocr_value || '—'
                      return (
                        <div key={field} className={styles.compTableRow}>
                          <span data-label="Field" className={styles.compField}>
                            {field.replace(/_/g, ' ')}
                          </span>
                          <span data-label="Your Input" className={styles.compMyVal}>{myVal}</span>
                          <span data-label="OCR Read" className={styles.compOcrVal}
                            style={{ color: score < 75 ? 'var(--rg-error)' : 'inherit' }}>
                            {ocrVal}
                          </span>
                          <span data-label="Match" className={styles.compScore} style={{ color: cat.color }}>
                            {score}%
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Mismatch Resolver */}
              {selectedDoc.mismatch_fields?.length > 0 && (
                <div className={styles.detailSection}>
                  <div className={styles.detailSectionTitle}>
                    <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--rg-warning)', verticalAlign: 'middle' }}>
                      warning
                    </span>{' '}
                    Mismatched Fields — Action Required
                  </div>
                  {selectedDoc.mismatch_fields.map(field => {
                    const data           = selectedDoc.field_match_scores?.[field] || {}
                    const alreadyResolved = selectedDoc.mismatch_resolutions?.[field]
                    const myVal          = fields[field]?.value || data.app_value || '—'
                    const ocrVal         = data.ocr_value || '—'

                    return (
                      <div
                        key={field}
                        className={`${styles.mismatchCard} ${alreadyResolved ? styles.mismatchResolved : ''}`}
                      >
                        <div className={styles.mismatchHeader}>
                          {alreadyResolved
                            ? <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--rg-success)' }}>check_circle</span>
                            : <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--rg-error)' }}>error</span>
                          }
                          <span className={styles.mismatchField}>{field.replace(/_/g, ' ')}</span>
                          {alreadyResolved && (
                            <span className="status-chip chip-success" style={{ fontSize: '0.6875rem' }}>
                              Resolved: {alreadyResolved}
                            </span>
                          )}
                        </div>

                        {!alreadyResolved && (
                          <>
                            <div className={styles.mismatchCompare}>
                              <div className={styles.mismatchSide}>
                                <div className={styles.mismatchSideLabel}>Your Input</div>
                                <div className={styles.mismatchSideValue}>{myVal}</div>
                              </div>
                              <div className={styles.mismatchVs}>vs</div>
                              <div className={styles.mismatchSide}>
                                <div className={styles.mismatchSideLabel}>OCR Read</div>
                                <div className={styles.mismatchSideValue} style={{ color: 'var(--rg-error)' }}>
                                  {ocrVal}
                                </div>
                              </div>
                            </div>
                            <div className={styles.mismatchActions}>
                              <button
                                className={styles.useOcrBtn}
                                onClick={() => resolveMutation.mutate({
                                  docId: selectedDoc.id, field, resolution: 'USE_OCR'
                                })}
                                disabled={resolveMutation.isPending}
                              >
                                Use Document Value: {ocrVal}
                              </button>
                              <button
                                className={styles.useAppBtn}
                                onClick={() => resolveMutation.mutate({
                                  docId: selectedDoc.id, field, resolution: 'USE_APPLICATION'
                                })}
                                disabled={resolveMutation.isPending}
                              >
                                Keep My Value: {myVal}
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}

              {/* No mismatches */}
              {(!selectedDoc.mismatch_fields || selectedDoc.mismatch_fields.length === 0) &&
               selectedDoc.verification_status === 'VERIFIED' && (
                <div className={styles.detailSection}>
                  <div className={styles.successNote}>
                    <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1", color: 'var(--rg-success)' }}>
                      verified
                    </span>
                    All fields match. Document verified successfully.
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
