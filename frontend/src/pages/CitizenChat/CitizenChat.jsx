import { useState, useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Send, Mic, RefreshCw, Globe, Plus, Paperclip, CheckCircle, XCircle, AlertCircle, FileText, Phone, PhoneOff, Play, Volume2, ShieldCheck, Search } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import useChatStore from '../../store/chatStore'
import useUIStore from '../../store/uiStore'
import { conversationApi } from '../../api/conversation'
import { t, LANGUAGE_NAMES } from '../../i18n'
import { CONV_NODES, NODE_STEPS, FRAUD_THRESHOLDS, SUPPORTED_LANGS, APP_STATUS } from '../../utils/constants'
import styles from './CitizenChat.module.css'

const SERVICE_LABELS = {
  income_certificate:  { en: 'Income Certificate',  hi: 'आय प्रमाण पत्र',  mr: 'उत्पन्न प्रमाणपत्र' },
  caste_certificate:   { en: 'Caste Certificate',   hi: 'जाति प्रमाण पत्र', mr: 'जात प्रमाणपत्र' },
  obc_ncl_certificate: { en: 'OBC-NCL Certificate', hi: 'OBC-NCL प्रमाण पत्र', mr: 'OBC-NCL प्रमाणपत्र' },
  domicile_certificate:{ en: 'Domicile Certificate',hi: 'अधिवास प्रमाण पत्र', mr: 'अधिवास प्रमाणपत्र' },
}

const NODE_STEP_LABELS = {
  en: { CONSENT:'Consent', INTENT_DETECTION:'Service Selection', SLOT_FILLING:'Your Details', DOCUMENT_CAPTURE:'Documents', VALIDATION:'Review', PAYMENT:'Payment', SUBMITTED:'Submitted', ESCALATED:'Escalated' },
  hi: { CONSENT:'सहमति', INTENT_DETECTION:'सेवा चयन', SLOT_FILLING:'आपकी जानकारी', DOCUMENT_CAPTURE:'दस्तावेज़', VALIDATION:'समीक्षा', PAYMENT:'भुगतान', SUBMITTED:'जमा हुआ', ESCALATED:'एस्केलेट' },
  mr: { CONSENT:'संमती', INTENT_DETECTION:'सेवा निवड', SLOT_FILLING:'आपली माहिती', DOCUMENT_CAPTURE:'कागదపత్రాలు', VALIDATION:'पुनरावलोकन', PAYMENT:'पेमेंट', SUBMITTED:'सादर केले', ESCALATED:'एस्केलेट' },
}

const SERVICE_FIELDS = {
  income_certificate: [
    { name: 'applicant_name', label: 'Applicant Full Name', type: 'string' },
    { name: 'applicant_dob', label: 'Date of Birth', type: 'date' },
    { name: 'aadhaar_number', label: 'Aadhaar Number (12 digits)', type: 'string' },
    { name: 'annual_income', label: 'Annual Income (₹)', type: 'number' },
    { name: 'address', label: 'Residential Address', type: 'string' },
    { name: 'purpose', label: 'Purpose of Certificate', type: 'string' }
  ],
  caste_certificate: [
    { name: 'applicant_name', label: 'Applicant Full Name', type: 'string' },
    { name: 'applicant_dob', label: 'Date of Birth', type: 'date' },
    { name: 'aadhaar_number', label: 'Aadhaar Number (12 digits)', type: 'string' },
    { name: 'father_name', label: "Father's Full Name", type: 'string' },
    { name: 'caste_category', label: 'Caste Category (SC/ST/OBC...)', type: 'string' },
    { name: 'caste_name', label: 'Sub-Caste Name', type: 'string' },
    { name: 'address', label: 'Residential Address', type: 'string' },
    { name: 'purpose', label: 'Purpose of Certificate', type: 'string' }
  ],
  obc_ncl_certificate: [
    { name: 'applicant_name', label: 'Applicant Full Name', type: 'string' },
    { name: 'applicant_dob', label: 'Date of Birth', type: 'date' },
    { name: 'aadhaar_number', label: 'Aadhaar Number (12 digits)', type: 'string' },
    { name: 'father_name', label: "Father's Full Name", type: 'string' },
    { name: 'annual_income', label: 'Annual Family Income (₹)', type: 'number' },
    { name: 'caste_category', label: 'Caste Category', type: 'string' },
    { name: 'caste_name', label: 'Sub-Caste Name', type: 'string' },
    { name: 'address', label: 'Residential Address', type: 'string' },
    { name: 'purpose', label: 'Purpose of Certificate', type: 'string' }
  ],
  domicile_certificate: [
    { name: 'applicant_name', label: 'Applicant Full Name', type: 'string' },
    { name: 'applicant_dob', label: 'Date of Birth', type: 'date' },
    { name: 'aadhaar_number', label: 'Aadhaar Number (12 digits)', type: 'string' },
    { name: 'residence_years', label: 'Years of Residence', type: 'number' },
    { name: 'address', label: 'Residential Address', type: 'string' },
    { name: 'purpose', label: 'Purpose of Certificate', type: 'string' }
  ]
}

function getAnomalyColor(score) {
  if (score < FRAUD_THRESHOLDS.PASS_MAX)   return '#22c55e'
  if (score < FRAUD_THRESHOLDS.REVIEW_MAX) return '#f59e0b'
  return '#ef4444'
}

export default function CitizenChat() {
  const [searchParams] = useSearchParams()
  const preselectedService = searchParams.get('service')
  const store = useChatStore()
  const { demoMode } = useUIStore()

  const [inputText, setInputText] = useState('')
  const [showLangMenu, setShowLangMenu] = useState(false)
  const [showResume, setShowResume] = useState(false)
  const [citizenId, setCitizenId] = useState(store.citizenIdentifier || '')
  const [idSet, setIdSet] = useState(!!store.citizenIdentifier)
  const [showDocSelector, setShowDocSelector] = useState(false)
  const [activeRightTab, setActiveRightTab] = useState('form') // form | docs | payment | track
  
  // Voice & STT/TTS States
  const [isListening, setIsListening] = useState(false)
  const [autoSpeak, setAutoSpeak] = useState(true)
  const [ivrActive, setIvrActive] = useState(false)
  const [ivrDuration, setIvrDuration] = useState(0)
  const [ivrTranscript, setIvrTranscript] = useState([])
  
  // Search Tracker States
  const [searchAppNum, setSearchAppNum] = useState('')
  const [trackedApp, setTrackedApp] = useState(null)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)
  const pendingDocTypeRef = useRef(null)
  const recognitionRef = useRef(null)
  const ivrIntervalRef = useRef(null)
  const sseRef = useRef(null)    // Phase 13: SSE connection ref
  
  // Phase 13: Real-time notification from backend
  const [sseNotification, setSseNotification] = useState(null) // { type, message, status }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [store.messages, store.isTyping])

  // Fetch initial session state
  useEffect(() => {
    if (!store.citizenIdentifier) return
    conversationApi.getSession(store.citizenIdentifier)
      .then(data => { 
        if (data?.session_id && data.current_node !== CONV_NODES.INIT) {
          setShowResume(true) 
        }
        store.syncFromResponse(data)
      })
      .catch(() => {})
  }, [store.citizenIdentifier])

  // Initialize Speech Recognition (STT)
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      const rec = new SpeechRecognition()
      rec.continuous = false
      rec.interimResults = false
      
      rec.onstart = () => setIsListening(true)
      rec.onend = () => setIsListening(false)
      rec.onresult = (e) => {
        const text = e.results[0][0].transcript
        if (ivrActive) {
          handleIvrSpeech(text)
        } else {
          setInputText(text)
          toast.success('Speech captured!')
        }
      }
      rec.onerror = (e) => {
        logger.error('STT error', e)
        setIsListening(false)
      }
      recognitionRef.current = rec
    }
  }, [ivrActive])

  // Handle IVR session timer
  useEffect(() => {
    if (ivrActive) {
      ivrIntervalRef.current = setInterval(() => {
        setIvrDuration(d => d + 1)
      }, 1000)
      // Say welcome
      speakTTS(store.currentNode === CONV_NODES.INIT ? 
        "Welcome to RevenueSeva Voice portal. Please speak clearly to complete your application. Please say yes or agree to consent to data collection." : 
        "Voice call connected. Continuing your application."
      )
    } else {
      if (ivrIntervalRef.current) clearInterval(ivrIntervalRef.current)
      setIvrDuration(0)
    }
    return () => {
      if (ivrIntervalRef.current) clearInterval(ivrIntervalRef.current)
    }
  }, [ivrActive])

  // Phase 13: SSE subscription for real-time status push
  useEffect(() => {
    if (!store.citizenIdentifier) return
    const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const url = `${API_BASE}/api/v1/stream/citizen/${encodeURIComponent(store.citizenIdentifier)}/events`
    
    const es = new EventSource(url)
    sseRef.current = es

    const STATUS_MESSAGES = {
      APPROVED:                 { type: 'success', msg: '🎉 Your application has been APPROVED! Payment step will begin shortly.' },
      REJECTED:                 { type: 'error',   msg: '❌ Your application has been REJECTED. Please check the chat for reasons.' },
      CLARIFICATION_REQUIRED:   { type: 'warning', msg: '📋 Clarification is required. Please check the chat and respond.' },
      CERTIFICATE_READY:        { type: 'success', msg: '📜 Your certificate is ready! Download it from the portal.' },
      COMPLETED:                { type: 'success', msg: '✅ Application completed. Certificate has been issued.' },
    }

    es.addEventListener('status_change', (e) => {
      try {
        const data = JSON.parse(e.data)
        const newStatus = data.new_status
        const cfg = STATUS_MESSAGES[newStatus]
        if (cfg) {
          setSseNotification({ ...cfg, status: newStatus, ts: Date.now() })
          toast(cfg.msg, {
            icon: cfg.type === 'success' ? '✅' : cfg.type === 'error' ? '❌' : '⚠️',
            duration: 8000,
          })
          // Sync status in the store too
          store.syncFromResponse({ application_status: newStatus })
        }
      } catch {/* ignore parse errors */}
    })

    es.addEventListener('notification', (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.message) {
          store.addMessage({ role: 'ASSISTANT', content: data.message, language: store.language })
        }
      } catch {/* ignore */}
    })

    es.onerror = () => {
      // Browser auto-reconnects EventSource — no manual retry needed
    }

    return () => {
      es.close()
      sseRef.current = null
    }
  }, [store.citizenIdentifier])

  // Auto-speak new assistant messages
  useEffect(() => {
    if (!autoSpeak || store.messages.length === 0) return
    const lastMsg = store.messages[store.messages.length - 1]
    if (lastMsg.role === 'ASSISTANT' && !ivrActive) {
      speakTTS(lastMsg.content)
    }
  }, [store.messages, autoSpeak])

  // TTS Reader
  const speakTTS = (text) => {
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    // Strip markdown formatting before speaking
    const cleanText = text.replace(/[*#_`~]/g, '').replace(/⚠️/g, 'Warning.').replace(/✅/g, 'Success.').slice(0, 200)
    const utterance = new SpeechSynthesisUtterance(cleanText)
    
    // Attempt to map voice language
    if (store.language === 'hi') utterance.lang = 'hi-IN'
    else if (store.language === 'mr') utterance.lang = 'mr-IN'
    else utterance.lang = 'en-IN'
    
    window.speechSynthesis.speak(utterance)
  }

  const toggleListening = () => {
    if (!recognitionRef.current) {
      toast.error('Browser Speech Recognition not supported in this environment.')
      return
    }
    if (isListening) {
      recognitionRef.current.stop()
    } else {
      if (store.language === 'hi') recognitionRef.current.lang = 'hi-IN'
      else if (store.language === 'mr') recognitionRef.current.lang = 'mr-IN'
      else recognitionRef.current.lang = 'en-IN'
      recognitionRef.current.start()
    }
  }

  const sendMessage = useCallback(async (text) => {
    if (!text?.trim() || store.isTyping) return
    const msgText = text.trim()
    setInputText('')

    store.addMessage({ role: 'USER', content: msgText, language: store.language })
    store.setTyping(true)

    try {
      const resp = await conversationApi.sendMessage(
        store.citizenIdentifier,
        msgText,
        store.channel,
        store.language,
        store.sessionId
      )
      store.syncFromResponse(resp)
      store.addMessage({ role: 'ASSISTANT', content: resp.response, language: resp.language })
      
      // Auto switch tabs on state updates
      if (resp.current_node === CONV_NODES.DOCUMENT_CAPTURE) setActiveRightTab('docs')
      else if (resp.current_node === CONV_NODES.PAYMENT) setActiveRightTab('payment')
    } catch (err) {
      toast.error(err.message || 'Failed to send message')
      store.addMessage({ role: 'ASSISTANT', content: '⚠️ Connection error. Please try again.', language: store.language })
    } finally {
      store.setTyping(false)
      inputRef.current?.focus()
    }
  }, [store])

  // Simulate IVR vocal interactions
  const handleIvrSpeech = async (text) => {
    setIvrTranscript(prev => [...prev, { role: 'USER', text }])
    store.setTyping(true)
    try {
      const resp = await conversationApi.sendVoiceMessage(
        store.citizenIdentifier,
        'IVR',
        store.language,
        text,
        null
      )
      store.syncFromResponse(resp)
      setIvrTranscript(prev => [...prev, { role: 'ASSISTANT', text: resp.response }])
      speakTTS(resp.response)
    } catch (err) {
      toast.error('Voice message error')
    } finally {
      store.setTyping(false)
    }
  }

  const simulateIvrClick = (text) => {
    handleIvrSpeech(text)
  }

  const handleSend = (e) => { e?.preventDefault(); sendMessage(inputText) }
  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }
  const handleLangChange = async (lang) => { store.setLanguage(lang); setShowLangMenu(false); toast.success(t(lang, 'chat.languageChanged')) }
  const handleResume = () => { setShowResume(false) }
  const handleFresh  = () => { store.reset(); setShowResume(false) }

  const handleSetId = (e) => {
    e.preventDefault()
    if (!citizenId.trim()) return
    store.setCitizenIdentifier(citizenId.trim())
    setIdSet(true)
    sendMessage('Hello')
  }

  // Document Upload Triggers
  const handleFileAttach = (docType) => {
    pendingDocTypeRef.current = docType
    fileInputRef.current.click()
    setShowDocSelector(false)
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !pendingDocTypeRef.current) return
    const docType = pendingDocTypeRef.current
    
    const loadingToast = toast.loading(`Uploading ${docType.replace(/_/g, ' ')}...`)
    try {
      await store.uploadDocument(docType, file)
      toast.success(`${docType.replace(/_/g, ' ')} uploaded & parsed successfully!`, { id: loadingToast })
      setActiveRightTab('docs')
    } catch (err) {
      toast.error(err.message || 'File upload failed', { id: loadingToast })
    } finally {
      e.target.value = ''
      pendingDocTypeRef.current = null
    }
  }

  // Resolve Mismatch Choice Trigger
  const handleResolveMismatch = async (fieldName, resolution) => {
    const loadingToast = toast.loading(`Resolving mismatch...`)
    try {
      await store.resolveMismatch(fieldName, resolution)
      toast.success(`Updated field successfully!`, { id: loadingToast })
    } catch (err) {
      toast.error(err.message || 'Failed to update field', { id: loadingToast })
    }
  }

  // Simulate Officer approval
  const handleSimulateApprove = async () => {
    const loadingToast = toast.loading('Simulating Government Verification & Approval...')
    try {
      await store.simulateGovApproval()
      toast.success('Application APPROVED!', { id: loadingToast })
      setActiveRightTab('payment')
    } catch (err) {
      toast.error(err.message || 'Simulation failed', { id: loadingToast })
    }
  }

  // Search status query tracker
  const handleSearchStatus = async (e) => {
    e.preventDefault()
    if (!searchAppNum.trim()) return
    try {
      const data = await applicationsApi.getStatus(searchAppNum.trim())
      setTrackedApp(data?.application)
      toast.success('Status retrieved!')
    } catch (err) {
      toast.error(err.message)
      setTrackedApp(null)
    }
  }

  const currentStepIdx = NODE_STEPS.indexOf(store.currentNode)
  const totalSlots = store.missingSlots.length + Object.keys(store.filledSlots).length
  const filledCount = Object.keys(store.filledSlots).length
  const slotPct = totalSlots > 0 ? Math.round((filledCount / totalSlots) * 100) : 0
  const activeFields = SERVICE_FIELDS[store.serviceType] || []

  if (!idSet) {
    return (
      <div className={styles.idGate}>
        <div className={styles.idCard}>
          <div className={styles.idIcon}>🏛️</div>
          <h2 className={styles.idTitle}>Welcome to RevenueSeva</h2>
          <p className={styles.idSub}>Enter a unique identifier to start (e.g. your mobile number or email)</p>
          <form onSubmit={handleSetId} className={styles.idForm}>
            <input className={styles.idInput} placeholder="e.g. 9876543210" value={citizenId}
              onChange={e => setCitizenId(e.target.value)} required />
            <button className={styles.idBtn} type="submit">Start →</button>
          </form>
          <p className={styles.idNote}>Your identity is tokenized — we never store raw identifiers.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.shell}>
      {/* LEFT SIDEBAR: Journey Stepper */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarTitle}>Your Journey</div>
        <div className={styles.steps}>
          {NODE_STEPS.map((node, idx) => {
            const done = idx < currentStepIdx
            const active = node === store.currentNode
            return (
              <div key={node} className={`${styles.step} ${done ? styles.done : ''} ${active ? styles.active : ''}`}>
                <div className={styles.stepDot}>{done ? '✓' : idx + 1}</div>
                <span className={styles.stepLabel}>{NODE_STEP_LABELS[store.language]?.[node] || node}</span>
              </div>
            )
          })}
        </div>
        {store.currentNode === CONV_NODES.SLOT_FILLING && totalSlots > 0 && (
          <div className={styles.slotProgress}>
            <div className={styles.slotLabel}>{filledCount}/{totalSlots} {t(store.language,'chat.slotProgress')}</div>
            <div className={styles.slotBar}><div className={styles.slotFill} style={{width:`${slotPct}%`}}/></div>
          </div>
        )}
        {store.applicationNumber && (
          <div className={styles.appNumBox}>
            <span className={styles.appNumLabel}>Application</span>
            <span className={styles.appNum}>{store.applicationNumber}</span>
          </div>
        )}
        {demoMode && (
          <div className={styles.anomalyBox}>
            <span className={styles.anomalyLabel}>Risk Score</span>
            <span className={styles.anomalyValue} style={{color: getAnomalyColor(store.anomalyScore)}}>
              {store.anomalyScore.toFixed(2)}
            </span>
          </div>
        )}
        <div className={styles.voiceSection}>
          <button className={`${styles.voiceModeBtn} ${ivrActive ? styles.active : ''}`} onClick={() => setIvrActive(v => !v)}>
            <Phone size={14}/> {ivrActive ? 'Hang Up IVR' : 'Dial IVR Call'}
          </button>
        </div>
      </aside>

      {/* MIDDLE SECTION: Chat Feed */}
      <div className={styles.chatArea}>
        <header className={styles.chatHeader}>
          <div className={styles.chatTitle}>
            <span className={styles.chatBot}>🤖</span>
            <div>
              <div className={styles.chatName}>RevenueSeva Assistant</div>
              <div className={styles.chatStatus}>{store.isConnected ? '🟢 Connected' : '⚪ Connecting…'}</div>
            </div>
          </div>
          <div className={styles.chatHeaderActions}>
            <button className={`${styles.speakToggle} ${autoSpeak ? styles.active : ''}`} onClick={() => setAutoSpeak(!autoSpeak)} title="Toggle Read Aloud">
              <Volume2 size={16}/>
            </button>
            <div className={styles.langSel}>
              <button className={styles.langSelBtn} onClick={() => setShowLangMenu(v => !v)}>
                <Globe size={16}/> {LANGUAGE_NAMES[store.language] || store.language}
              </button>
              {showLangMenu && (
                <div className={styles.langMenu}>
                  {SUPPORTED_LANGS.map(lang => (
                    <button key={lang} className={`${styles.langMenuItem} ${store.language===lang?styles.langMenuActive:''}`}
                      onClick={() => handleLangChange(lang)}>{LANGUAGE_NAMES[lang]}</button>
                  ))}
                </div>
              )}
            </div>
            <button className={styles.resetBtn} onClick={() => { store.reset(); setIdSet(false); setCitizenId('') }} title="Start over">
              <RefreshCw size={16}/>
            </button>
          </div>
        </header>

        {showResume && (
          <div className={styles.resumeBanner}>
            <span>{t(store.language,'chat.resumeSession')}</span>
            <div className={styles.resumeActions}>
              <button className={styles.resumeBtn} onClick={handleResume}>{t(store.language,'chat.resumeBtn')}</button>
              <button className={styles.freshBtn} onClick={handleFresh}>{t(store.language,'chat.freshBtn')}</button>
            </div>
          </div>
        )}

        {/* Phase 13: SSE Status Notification Banner */}
        {sseNotification && (
          <div className={styles.sseNotificationBanner} data-type={sseNotification.type}>
            <span className={styles.sseNotificationMsg}>{sseNotification.msg}</span>
            <button className={styles.sseNotificationClose} onClick={() => setSseNotification(null)}>✕</button>
          </div>
        )}

        <div className={styles.messages}>
          {store.messages.length === 0 && !store.isTyping && (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>💬</div>
              <p>Start by saying <b>"Hello"</b> or choose a service below</p>
              <div className={styles.quickServices}>
                {Object.entries(SERVICE_LABELS).map(([id, names]) => (
                  <button key={id} className={styles.quickSvcBtn} onClick={() => sendMessage(names[store.language] || names.en)}>
                    {names[store.language] || names.en}
                  </button>
                ))}
              </div>
            </div>
          )}

          {store.messages.map((msg) => (
            <div key={msg.id} className={`${styles.msgRow} ${msg.role === 'USER' ? styles.userRow : styles.assistantRow}`}>
              {msg.role === 'ASSISTANT' && <div className={styles.avatar}>🤖</div>}
              <div className={`${styles.bubble} ${msg.role === 'USER' ? styles.userBubble : styles.assistantBubble}`}>
                <ReactMarkdown>{msg.content}</ReactMarkdown>
                {msg.audioUrl && (
                  <button onClick={() => speakTTS(msg.content)} className={styles.audioPlayBtn}>
                    <Volume2 size={12}/> Listen audio note
                  </button>
                )}
                <span className={styles.timestamp}>
                  {new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}
                </span>
              </div>
            </div>
          ))}

          {store.isTyping && (
            <div className={`${styles.msgRow} ${styles.assistantRow}`}>
              <div className={styles.avatar}>🤖</div>
              <div className={`${styles.bubble} ${styles.assistantBubble} ${styles.typingBubble}`}>
                <span className={styles.tdot}/><span className={styles.tdot}/><span className={styles.tdot}/>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className={styles.inputBar} onSubmit={handleSend}>
          <div className={styles.docUploadContainer}>
            <button type="button" className={styles.inputAction} onClick={() => setShowDocSelector(!showDocSelector)} title="Upload Document">
              <Plus size={18}/>
            </button>
            {showDocSelector && (
              <div className={styles.docUploadDropdown}>
                <span className={styles.dropdownHeader}>Select Document Type:</span>
                {['IDENTITY_PROOF', 'INCOME_PROOF', 'CASTE_PROOF', 'ADDRESS_PROOF', 'PAYMENT_RECEIPT'].map(type => (
                  <button key={type} type="button" onClick={() => handleFileAttach(type)}>
                    📄 {type.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button type="button" className={`${styles.inputAction} ${isListening ? styles.micActive : ''}`} onClick={toggleListening} title="STT Microphone">
            <Mic size={18}/>
          </button>
          <textarea
            ref={inputRef}
            className={styles.textInput}
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? "Listening..." : t(store.language,'chat.placeholder')}
            rows={1}
            maxLength={500}
            disabled={isListening}
          />
          <span className={styles.charCount}>{inputText.length}/500</span>
          <button type="submit" className={styles.sendBtn}
            disabled={!inputText.trim() || store.isTyping || isListening}
            aria-label={t(store.language,'chat.send')}>
            <Send size={18}/>
          </button>
        </form>
        
        {/* HIDDEN FILE INPUT */}
        <input type="file" ref={fileInputRef} onChange={handleFileChange} style={{display:'none'}} accept="image/*,.pdf"/>
      </div>

      {/* RIGHT PANEL: Live Form, Documents checklist, Payments, and Tracking */}
      <aside className={styles.formPanel}>
        <div className={styles.panelTabs}>
          {['form', 'docs', 'payment', 'track'].map(tab => (
            <button key={tab} className={`${styles.panelTab} ${activeRightTab === tab ? styles.panelTabActive : ''}`}
              onClick={() => setActiveRightTab(tab)}>
              {tab.toUpperCase()}
            </button>
          ))}
        </div>

        <div className={styles.panelContent}>
          {/* TAB 1: Real-time Synchronized Form */}
          {activeRightTab === 'form' && (
            <div className={styles.formView}>
              {store.serviceType ? (
                <>
                  <div className={styles.formHeader}>
                    <h3>{SERVICE_LABELS[store.serviceType]?.[store.language] || store.serviceType.replace(/_/g,' ')}</h3>
                    <p className={styles.formSub}>Auto-filling from chat logs in real time</p>
                  </div>
                  
                  <div className={styles.fieldsList}>
                    {activeFields.map(f => {
                      const value = store.filledSlots[f.name]
                      const isWaiting = store.missingSlots[0] === f.name
                      return (
                        <div key={f.name} className={`${styles.fieldCard} ${isWaiting ? styles.waitingField : ''}`}>
                          <label className={styles.fieldLabel}>{f.label}</label>
                          <div className={styles.fieldValueContainer}>
                            {value ? (
                              <span className={styles.fieldValue}>{value}</span>
                            ) : (
                              <span className={styles.fieldPlaceholder}>
                                {isWaiting ? '⏳ Waiting for your response...' : 'Pending'}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </>
              ) : (
                <div className={styles.noServiceState}>
                  <div className={styles.noServiceIcon}>🏛️</div>
                  <h4>No active application</h4>
                  <p>Choose a certificate service in the chat (e.g. say "I want Caste Certificate") to view the live form panel.</p>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Documents and Mismatch Check */}
          {activeRightTab === 'docs' && (
            <div className={styles.docsView}>
              <h3>Document Verification Panel</h3>
              <p className={styles.docsSub}>Verify OCR match scores & resolve mismatches</p>
              
              {store.applicationNumber ? (
                <div className={styles.docsList}>
                  {store.documents.map((doc) => {
                    const isMismatch = doc.verification_status === 'MISMATCH'
                    return (
                      <div key={doc.id} className={`${styles.docCard} ${isMismatch ? styles.mismatchDoc : ''}`}>
                        <div className={styles.docHeader}>
                          <FileText size={18} style={{color:'var(--clr-primary-500)'}}/>
                          <div className={styles.docTitleBlock}>
                            <span className={styles.docTypeLabel}>{doc.doc_type.replace(/_/g, ' ')}</span>
                            <span className={styles.docFileName}>{doc.filename}</span>
                          </div>
                        </div>

                        <div className={styles.docMetaGrid}>
                          <span className={styles.docMetaKey}>Confidence:</span>
                          <span className={styles.docMetaValue}>{(doc.confidence_score * 100).toFixed(1)}%</span>
                          <span className={styles.docMetaKey}>Status:</span>
                          <span className={`${styles.docStatusBadge} ${styles[doc.verification_status.toLowerCase()]}`}>
                            {doc.verification_status}
                          </span>
                        </div>

                        {/* Mismatch Decision Modal Panel */}
                        {isMismatch && doc.mismatch_fields && doc.mismatch_fields.map(field => {
                          const declared = store.filledSlots[field]
                          const ocrVal = doc.extracted_fields[field] || '—'
                          return (
                            <div key={field} className={styles.mismatchResolver}>
                              <div className={styles.mismatchAlert}>
                                <AlertCircle size={14}/> Mismatch in: {field.replace(/_/g, ' ').toUpperCase()}
                              </div>
                              <div className={styles.mismatchComparison}>
                                <div>
                                  <span className={styles.compLabel}>Declared:</span>
                                  <span className={styles.compVal}>{declared}</span>
                                </div>
                                <div>
                                  <span className={styles.compLabel}>Document OCR:</span>
                                  <span className={styles.compVal} style={{color:'var(--clr-danger-500)'}}>{ocrVal}</span>
                                </div>
                              </div>
                              <div className={styles.mismatchActions}>
                                <button className={styles.useDocBtn} onClick={() => handleResolveMismatch(field, 'use_document')}>
                                  Use Doc Value
                                </button>
                                <button className={styles.useDeclBtn} onClick={() => handleResolveMismatch(field, 'use_declared')}>
                                  Keep Declared
                                </button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )
                  })}
                  
                  {store.documents.length === 0 && (
                    <p className={styles.emptyDocsText}>No documents uploaded yet. Upload documents using the "+" button beside chat input.</p>
                  )}
                </div>
              ) : (
                <p className={styles.emptyDocsText}>No active application found.</p>
              )}
            </div>
          )}

          {/* TAB 3: Government Approval Simulator & Payments */}
          {activeRightTab === 'payment' && (
            <div className={styles.paymentView}>
              <h3>Review & Payments</h3>
              
              {store.applicationNumber ? (
                <div className={styles.paymentContainer}>
                  {/* Step 1: Government review */}
                  {store.currentNode === CONV_NODES.VALIDATION && (
                    <div className={styles.reviewFormBox}>
                      <div className={styles.govStateCard}>
                        <ShieldCheck size={28} style={{color:'var(--clr-primary-500)'}}/>
                        <div>
                          <h4>Submitted for Verification</h4>
                          <p>The application is pending Officer Review.</p>
                        </div>
                      </div>
                      
                      <div className={styles.simApprovalCard}>
                        <h5>System Dev Tool</h5>
                        <p>Simulate government officer dashboard approval immediately for testing.</p>
                        <button className={styles.simulateApproveBtn} onClick={handleSimulateApprove}>
                          ⚡ Simulate Government Approval
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Step 2: Payment flow */}
                  {(store.currentNode === CONV_NODES.PAYMENT || store.paymentStatus === 'PAID') ? (
                    <div className={styles.paymentFlowBox}>
                      <div className={styles.amountHeader}>
                        <span>Application Fee:</span>
                        <h2>₹50.00</h2>
                      </div>
                      
                      {store.paymentStatus !== 'PAID' ? (
                        <>
                          <div className={styles.qrContainer}>
                            {/* Simulated UPI QR Code */}
                            <div className={styles.qrCodeSquare}>
                              <div className={styles.qrLogo}>🏛️</div>
                              {/* QR Pattern dots */}
                              <div className={styles.qrDots}/>
                            </div>
                            <span className={styles.upiAddress}>UPI ID: revenue.seva@sbi</span>
                          </div>

                          <div className={styles.receiptUploadBox}>
                            <h5>Verify Payment via Receipt OCR</h5>
                            <p>Upload a screenshot of your transaction confirmation to auto-complete submission.</p>
                            <button type="button" className={styles.uploadReceiptBtn} onClick={() => handleFileAttach('PAYMENT_RECEIPT')}>
                              📤 Upload Screenshot
                            </button>
                          </div>
                        </>
                      ) : (
                        <div className={styles.paidSuccessCard}>
                          <CheckCircle size={36} style={{color:'var(--clr-success-500)'}}/>
                          <h4>Payment Verified successfully</h4>
                          <p>Transaction ID validated and approved.</p>
                        </div>
                      )}
                    </div>
                  ) : null}
                  
                  {store.currentNode !== CONV_NODES.VALIDATION && store.currentNode !== CONV_NODES.PAYMENT && store.paymentStatus !== 'PAID' && (
                    <p className={styles.emptyDocsText}>Application must be verified by government before initiating payment.</p>
                  )}
                </div>
              ) : (
                <p className={styles.emptyDocsText}>No active application found.</p>
              )}
            </div>
          )}

          {/* TAB 4: Search & Track Status */}
          {activeRightTab === 'track' && (
            <div className={styles.trackView}>
              <h3>Track Status</h3>
              <p className={styles.trackSub}>Query status using application tracking ID</p>
              
              <form onSubmit={handleSearchStatus} className={styles.searchBar}>
                <input className={styles.searchInput} placeholder="e.g. APP-IC-2026-XXXX" value={searchAppNum}
                  onChange={e => setSearchAppNum(e.target.value)} required />
                <button type="submit" className={styles.searchBtn}><Search size={16}/></button>
              </form>

              {trackedApp && (
                <div className={styles.trackedResultCard}>
                  <div className={styles.trackedHeader}>
                    <h4>{trackedApp.application_number}</h4>
                    <span className={`${styles.statusBadge} ${styles[trackedApp.status.toLowerCase()]}`}>
                      {trackedApp.status}
                    </span>
                  </div>

                  <div className={styles.trackedDetails}>
                    <div className={styles.trackDetailItem}>
                      <span className={styles.trackKey}>Service:</span>
                      <span className={styles.trackVal}>{trackedApp.service_type.replace(/_/g, ' ').toUpperCase()}</span>
                    </div>
                    <div className={styles.trackDetailItem}>
                      <span className={styles.trackKey}>Payment:</span>
                      <span className={styles.trackVal}>{trackedApp.payment_status}</span>
                    </div>
                    <div className={styles.trackDetailItem}>
                      <span className={styles.trackKey}>Language:</span>
                      <span className={styles.trackVal}>{trackedApp.language.toUpperCase()}</span>
                    </div>
                    <div className={styles.trackDetailItem}>
                      <span className={styles.trackKey}>SLA:</span>
                      <span className={styles.trackVal}>{trackedApp.sla_days} days</span>
                    </div>
                  </div>

                  <div className={styles.timeline}>
                    {['DRAFT', 'UNDER_REVIEW', 'APPROVED', 'SUBMITTED'].map((node, i) => {
                      const statuses = ['DRAFT', 'UNDER_REVIEW', 'APPROVED', 'SUBMITTED']
                      const activeIndex = statuses.indexOf(trackedApp.status)
                      const passed = i <= activeIndex
                      return (
                        <div key={node} className={`${styles.timelineStep} ${passed ? styles.timelinePassed : ''}`}>
                          <div className={styles.timelineDot}>{passed ? '✓' : ''}</div>
                          <span>{node}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
      
      {/* MULTILINGUAL IVR SIMULATOR PHONE OVERLAY */}
      {ivrActive && (
        <div className={styles.ivrOverlay}>
          <div className={styles.ivrPhone}>
            <div className={styles.phoneHeader}>
              <div className={styles.phoneSpeaker}/>
              <div className={styles.phoneSignal}>📶 🔋 100%</div>
            </div>
            
            <div className={styles.phoneCallArea}>
              <div className={styles.phoneCallerName}>RevenueSeva IVR</div>
              <div className={styles.phoneCallerNumber}>1800-REV-SEVA</div>
              <div className={styles.phoneTimer}>
                {Math.floor(ivrDuration / 60)}:{(ivrDuration % 60).toString().padStart(2, '0')}
              </div>
              <div className={styles.callPulsingIcon}>📞</div>
            </div>
            
            {/* Real-time caption log */}
            <div className={styles.phoneTranscriptBox}>
              {ivrTranscript.map((log, i) => (
                <div key={i} className={`${styles.ivrLogLine} ${log.role === 'USER' ? styles.ivrUser : styles.ivrBot}`}>
                  <span className={styles.ivrActor}>{log.role === 'USER' ? 'You' : 'IVR'}:</span>
                  <span className={styles.ivrText}>{log.text}</span>
                </div>
              ))}
              {store.isTyping && (
                <div className={styles.ivrTyping}>IVR is thinking...</div>
              )}
            </div>

            {/* Quick response chips for easier manual simulation */}
            <div className={styles.ivrQuickChoices}>
              <span>Tap to Speak:</span>
              <div className={styles.chipsWrapper}>
                {store.currentNode === CONV_NODES.CONSENT && (
                  <>
                    <button type="button" onClick={() => simulateIvrClick('Yes I agree')}>Agree to consent</button>
                    <button type="button" onClick={() => simulateIvrClick('No I disagree')}>Refuse consent</button>
                  </>
                )}
                {store.currentNode === CONV_NODES.INTENT_DETECTION && (
                  <>
                    <button type="button" onClick={() => simulateIvrClick('I want caste certificate')}>Apply Caste</button>
                    <button type="button" onClick={() => simulateIvrClick('I need income certificate')}>Apply Income</button>
                  </>
                )}
                {store.currentNode === CONV_NODES.SLOT_FILLING && store.missingSlots[0] === 'applicant_name' && (
                  <button type="button" onClick={() => simulateIvrClick('My name is Abhay Kumar')}>Speak Name</button>
                )}
                {store.currentNode === CONV_NODES.SLOT_FILLING && store.missingSlots[0] === 'applicant_dob' && (
                  <button type="button" onClick={() => simulateIvrClick('My date of birth is 15-08-1995')}>Speak DOB</button>
                )}
                {store.currentNode === CONV_NODES.SLOT_FILLING && store.missingSlots[0] === 'annual_income' && (
                  <button type="button" onClick={() => simulateIvrClick('My income is 1,50,000')}>Speak Income</button>
                )}
                {store.currentNode === CONV_NODES.SLOT_FILLING && store.missingSlots[0] === 'aadhaar_number' && (
                  <button type="button" onClick={() => simulateIvrClick('My aadhaar number is 1234 5678 9012')}>Speak Aadhaar</button>
                )}
                {store.currentNode === CONV_NODES.SLOT_FILLING && store.missingSlots[0] === 'address' && (
                  <button type="button" onClick={() => simulateIvrClick('I live at 123 Demo Street Nagpur Maharashtra')}>Speak Address</button>
                )}
                {store.currentNode === CONV_NODES.SLOT_FILLING && store.missingSlots[0] === 'purpose' && (
                  <button type="button" onClick={() => simulateIvrClick('It is for higher studies')}>Speak Purpose</button>
                )}
                {store.currentNode === CONV_NODES.DOCUMENT_CAPTURE && (
                  <button type="button" onClick={() => simulateIvrClick('skip documents')}>Skip Documents Checklist</button>
                )}
              </div>
            </div>

            <div className={styles.phoneControls}>
              <button className={`${styles.phoneMic} ${isListening ? styles.active : ''}`} onClick={toggleListening} title="Voice microphone">
                🎤
              </button>
              <button className={styles.endCallBtn} onClick={() => setIvrActive(false)} title="End Call">
                <PhoneOff size={18}/> End Call
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
