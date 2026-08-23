import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Shield, Play, RefreshCw } from 'lucide-react'
import { dataGuardApi } from '../../api/dataGuard'
import { dashboardApi } from '../../api/dashboard'
import styles from './DataGuardDemo.module.css'

const EXAMPLES = [
  {
    label: 'PII Payload → BLOCK',
    payload: { applicant_name: 'Rahul Sharma', aadhaar_number: '1234-5678-9012', date_of_birth: '1990-01-01', message: 'Need income certificate' },
    destination: 'cloud_llm', operation: 'translate_query'
  },
  {
    label: 'Safe Payload → ALLOW',
    payload: { service_type: 'income_certificate', message_text: 'How do I apply?', district_synthetic: 'SYNTH-DIST-001' },
    destination: 'translation_service', operation: 'translate'
  },
  {
    label: 'Synthetic Data → ALLOW',
    payload: { service_type: 'caste_certificate', synthetic_citizen_id: 'SYNTH-CIT-98721', request_count: 1 },
    destination: 'cloud_api', operation: 'eligibility_check', data_classification: 'SYNTHETIC'
  },
  {
    label: 'Nested PII → BLOCK',
    payload: { request: { user: { name: 'Priya Patel', phone: '9876543210' }, doc: 'income_proof' } },
    destination: 'cloud_llm', operation: 'ocr_extract'
  },
]

export default function DataGuardDemo() {
  const [payloadText, setPayloadText] = useState(JSON.stringify(EXAMPLES[0].payload, null, 2))
  const [destination, setDestination] = useState(EXAMPLES[0].destination)
  const [operation,   setOperation]   = useState(EXAMPLES[0].operation)
  const [dataClass,   setDataClass]   = useState('')
  const [result,      setResult]      = useState(null)
  const [testing,     setTesting]     = useState(false)
  const [activeTab,   setActiveTab]   = useState('tester')

  const { data: policy } = useQuery({ queryKey:['dg-policy'], queryFn: dataGuardApi.getPolicy })
  const { data: stats }  = useQuery({ queryKey:['dg-stats'],  queryFn: () => dashboardApi.getDataGuardStats() })

  const loadExample = (ex) => {
    setPayloadText(JSON.stringify(ex.payload, null, 2))
    setDestination(ex.destination)
    setOperation(ex.operation)
    setDataClass(ex.data_classification || '')
    setResult(null)
  }

  const runTest = async () => {
    let parsed
    try { parsed = JSON.parse(payloadText) } catch { toast.error('Invalid JSON payload'); return }
    setTesting(true)
    setResult(null)
    try {
      const res = await dataGuardApi.check(parsed, destination, operation, dataClass || null)
      setResult(res)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setTesting(false)
    }
  }

  const [classPayload, setClassPayload] = useState('{"name":"John","district":"Pune","service":"income"}')
  const [classResult,  setClassResult]  = useState(null)
  const [classifying,  setClassifying]  = useState(false)

  const runClassify = async () => {
    let parsed
    try { parsed = JSON.parse(classPayload) } catch { toast.error('Invalid JSON'); return }
    setClassifying(true)
    try {
      const res = await dataGuardApi.classify(parsed)
      setClassResult(res)
    } catch (err) { toast.error(err.message) }
    finally { setClassifying(false) }
  }

  const FIELD_COLORS = { RESTRICTED:'var(--clr-danger-500)', QUASI_IDENTIFIER:'var(--clr-warning-500)', NON_SENSITIVE:'var(--clr-success-500)' }
  const FIELD_ICONS  = { RESTRICTED:'🔴', QUASI_IDENTIFIER:'🟡', NON_SENSITIVE:'🟢' }

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div className={styles.titleRow}>
          <Shield size={28} className={styles.shieldIcon}/>
          <div>
            <h1 className={styles.title}>Data Guard — Trust Boundary</h1>
            <p className={styles.sub}>Watch PII get blocked in real time before reaching cloud services</p>
          </div>
        </div>
        {stats && (
          <div className={styles.statsBar}>
            <span className={styles.statItem}><b style={{color:'var(--clr-danger-400)'}}>{stats.blocks_today ?? 0}</b> Blocks Today</span>
            <span className={styles.statItem}><b style={{color:'var(--clr-success-400)'}}>{stats.allows_today ?? 0}</b> Allows Today</span>
            <span className={styles.statItem}><b style={{color:'var(--admin-text)'}}>{stats.total_today ?? 0}</b> Total</span>
          </div>
        )}
      </div>

      <div className={styles.tabs}>
        {[['tester','Live Tester'],['classifier','Field Classifier'],['policy','Policy Rules']].map(([k,l]) => (
          <button key={k} className={`${styles.tab} ${activeTab===k?styles.tabActive:''}`} onClick={()=>setActiveTab(k)}>{l}</button>
        ))}
      </div>

      {activeTab === 'tester' && (
        <div className={styles.testerLayout}>
          <div className={styles.editorPanel}>
            <div className={styles.examplesRow}>
              {EXAMPLES.map((ex,i) => (
                <button key={i} className={styles.exampleBtn} onClick={()=>loadExample(ex)}>{ex.label}</button>
              ))}
            </div>

            <div className={styles.fieldGroup}>
              <label className={styles.label}>Test Payload (JSON)</label>
              <textarea className={styles.jsonEditor} value={payloadText}
                onChange={e=>setPayloadText(e.target.value)} rows={10} spellCheck={false}/>
            </div>
            <div className={styles.fieldsRow}>
              <div className={styles.fieldGroup}>
                <label className={styles.label}>Destination</label>
                <select className={styles.select} value={destination} onChange={e=>setDestination(e.target.value)}>
                  <option value="cloud_llm">cloud_llm</option>
                  <option value="translation_service">translation_service</option>
                  <option value="cloud_api">cloud_api</option>
                </select>
              </div>
              <div className={styles.fieldGroup}>
                <label className={styles.label}>Operation</label>
                <input className={styles.input} value={operation} onChange={e=>setOperation(e.target.value)} placeholder="e.g. translate_query"/>
              </div>
              <div className={styles.fieldGroup}>
                <label className={styles.label}>Data Classification</label>
                <input className={styles.input} value={dataClass} onChange={e=>setDataClass(e.target.value)} placeholder="SYNTHETIC (optional)"/>
              </div>
            </div>
            <button className={styles.testBtn} onClick={runTest} disabled={testing}>
              {testing ? <RefreshCw size={16} className="anim-spin"/> : <Play size={16}/>}
              {testing ? 'Testing…' : 'Test Data Guard'}
            </button>
          </div>

          <div className={styles.resultPanel}>
            {!result && !testing && (
              <div className={styles.resultPlaceholder}><Shield size={48}/><p>Load an example and click "Test Data Guard"</p></div>
            )}
            {result && (
              <div className={`${styles.resultCard} ${result.decision==='BLOCK'?styles.blocked:styles.allowed}`}
                style={{animation:result.decision==='BLOCK'?'blockFlash .6s ease':'allowFlash .6s ease'}}>
                <div className={styles.decisionBadge}>
                  {result.decision === 'BLOCK' ? '🛑 BLOCKED' : '✅ ALLOWED'}
                </div>
                <p className={styles.decisionReason}>
                  {result.decision === 'BLOCK' ? 'PII Detected Before Cloud Call' : 'No PII detected. Safe to proceed.'}
                </p>

                {result.blocked_fields?.length > 0 && (
                  <div className={styles.blockedFields}>
                    <p className={styles.sectionLabel}>Blocked Fields:</p>
                    {result.blocked_fields.map(f=>(
                      <div key={f.field} className={styles.fieldRow}>
                        <span className={styles.fieldName}>● {f.field}</span>
                        <span className={styles.fieldClass} style={{color:FIELD_COLORS[f.classification]}}>[{f.classification}]</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className={styles.metaList}>
                  {result.audit_id && <div className={styles.metaRow2}><span>Audit Entry</span><span className={styles.monoVal}>#{result.audit_id} ✅</span></div>}
                  {result.payload_hash && <div className={styles.metaRow2}><span>Payload Hash</span><span className={styles.monoVal}>{result.payload_hash.substring(0,16)}…</span></div>}
                  {result.chain_hash   && <div className={styles.metaRow2}><span>Chain Hash</span><span className={styles.monoVal}>{result.chain_hash.substring(0,16)}…</span></div>}
                  <div className={styles.metaRow2}><span>Fields Scanned</span><span className={styles.monoVal}>{result.fields_scanned ?? '—'}</span></div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'classifier' && (
        <div className={styles.classifierLayout}>
          <div className={styles.editorPanel}>
            <div className={styles.fieldGroup}>
              <label className={styles.label}>Paste any JSON object to classify</label>
              <textarea className={styles.jsonEditor} value={classPayload}
                onChange={e=>setClassPayload(e.target.value)} rows={8} spellCheck={false}/>
            </div>
            <button className={styles.testBtn} onClick={runClassify} disabled={classifying}>
              {classifying ? <RefreshCw size={16} className="anim-spin"/> : null}
              Classify Fields
            </button>
          </div>
          {classResult && (
            <div className={styles.classifyResult}>
              {(classResult.fields || []).map(f => (
                <div key={f.field} className={styles.classifyRow}>
                  <span className={styles.classifyIcon}>{FIELD_ICONS[f.classification]||'⚪'}</span>
                  <span className={styles.classifyField}>{f.field}</span>
                  <span className={styles.classifyTag} style={{color:FIELD_COLORS[f.classification]||'gray'}}>{f.classification}</span>
                  <span className={styles.classifyReason}>{f.reason||''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'policy' && (
        <div className={styles.policyPanel}>
          {policy ? (
            <pre className={styles.policyJson}>{JSON.stringify(policy, null, 2)}</pre>
          ) : <div className={styles.resultPlaceholder}><p>Loading policy…</p></div>}
        </div>
      )}
    </div>
  )
}
