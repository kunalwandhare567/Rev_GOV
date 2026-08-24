import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import toast from 'react-hot-toast'
import {
  Send, Mic, MicOff, Paperclip, Phone, PhoneOff, Globe,
  Search, MoreVertical, RefreshCw, FileText, Play, Volume2,
  CheckCheck, X, ChevronRight
} from 'lucide-react'
import styles from './WhatsAppChat.module.css'

const API = 'http://localhost:8000/api/v1'

const LANGUAGES = [
  { code: 'en', label: 'English', flag: '🇬🇧' },
  { code: 'hi', label: 'हिंदी', flag: '🇮🇳' },
  { code: 'mr', label: 'मराठी', flag: '🇮🇳' },
  { code: 'bn', label: 'বাংলা', flag: '🇮🇳' },
  { code: 'gu', label: 'ગુજરાતી', flag: '🇮🇳' },
  { code: 'ta', label: 'தமிழ்', flag: '🇮🇳' },
  { code: 'te', label: 'తెలుగు', flag: '🇮🇳' },
]

const DOC_TYPES = [
  { type: 'AADHAAR_CARD', icon: '🪪', label: 'Aadhaar Card' },
  { type: 'PAN_CARD', icon: '💳', label: 'PAN Card' },
  { type: 'INCOME_PROOF', icon: '📄', label: 'Income Proof' },
  { type: 'CASTE_CERTIFICATE', icon: '📋', label: 'Caste Certificate' },
  { type: 'ADDRESS_PROOF', icon: '🏠', label: 'Address Proof' },
  { type: 'PAYMENT_RECEIPT', icon: '🧾', label: 'Payment Receipt' },
]

const LIFECYCLE_STEPS = [
  { key: 'DRAFT', label: 'Started' },
  { key: 'INFORMATION_COLLECTION', label: 'Details' },
  { key: 'DOCUMENT_COLLECTION', label: 'Documents' },
  { key: 'OCR_VALIDATION', label: 'Verifying' },
  { key: 'FINAL_REVIEW', label: 'Review' },
  { key: 'SUBMITTED_FOR_VERIFICATION', label: 'Submitted' },
  { key: 'UNDER_REVIEW', label: 'Gov. Review' },
  { key: 'COMPLETED', label: 'Completed' },
]

function getScoreColor(score) {
  if (score >= 90) return '#25d366'
  if (score >= 70) return '#f59e0b'
  return '#ef4444'
}

export default function WhatsAppChat() {
  const [waNumber, setWaNumber] = useState('')
  const [numberSet, setNumberSet] = useState(false)
  const [language, setLanguage] = useState('en')
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [showLang, setShowLang] = useState(false)
  const [showAttach, setShowAttach] = useState(false)
  const [activeTab, setActiveTab] = useState('form') // form | docs | timeline
  const [appData, setAppData] = useState(null) // Active application data
  const [documents, setDocuments] = useState([])
  const [pendingMismatches, setPendingMismatches] = useState({})
  const [trackingId, setTrackingId] = useState(null)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)
  const pendingDocType = useRef(null)
  const recognitionRef = useRef(null)

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  // Browser STT init
  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const rec = new SR()
    rec.continuous = false
    rec.interimResults = false
    rec.onstart = () => setIsListening(true)
    rec.onend = () => setIsListening(false)
    rec.onresult = (e) => {
      const text = e.results[0][0].transcript
      setInputText(text)
      toast.success('🎙️ Voice captured!')
    }
    rec.onerror = () => setIsListening(false)
    recognitionRef.current = rec
  }, [])

  // Load history on number set
  useEffect(() => {
    if (!numberSet || !waNumber) return
    loadHistory()
  }, [numberSet, waNumber])

  // Poll for application updates
  useEffect(() => {
    if (!numberSet || !waNumber) return
    const interval = setInterval(loadHistory, 5000)
    return () => clearInterval(interval)
  }, [numberSet, waNumber])

  const loadHistory = async () => {
    try {
      const res = await fetch(`${API}/whatsapp/history/${encodeURIComponent(waNumber)}`)
      if (!res.ok) return
      const data = await res.json()
      if (data.messages?.length) {
        setMessages(data.messages.map(m => ({
          id: m.id,
          role: m.role,
          content: m.content,
          modality: m.modality || 'TEXT',
          time: m.created_at,
        })))
      }
    } catch {}
  }

  const sendMessage = useCallback(async (text) => {
    if (!text?.trim() || isTyping) return
    const msg = text.trim()
    setInputText('')

    const userMsg = { id: Date.now(), role: 'USER', content: msg, modality: 'TEXT', time: new Date().toISOString() }
    setMessages(prev => [...prev, userMsg])
    setIsTyping(true)

    try {
      const res = await fetch(`${API}/whatsapp/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from_number: waNumber,
          message_type: 'text',
          text: msg,
          language,
        }),
      })

      const data = await res.json()

      const botMsg = {
        id: Date.now() + 1,
        role: 'ASSISTANT',
        content: data.reply_text || '',
        modality: 'TEXT',
        time: new Date().toISOString(),
        options: data.options || [],
      }
      setMessages(prev => [...prev, botMsg])

      if (data.tracking_id) setTrackingId(data.tracking_id)
      if (data.language) setLanguage(data.language)

      // Reload documents if document tab active
      if (activeTab === 'docs') loadDocuments(data.application_id)

    } catch (err) {
      toast.error('Connection error')
      setMessages(prev => [...prev, {
        id: Date.now() + 2, role: 'ASSISTANT',
        content: '⚠️ Unable to connect to server. Please ensure backend is running.',
        modality: 'TEXT', time: new Date().toISOString(),
      }])
    } finally {
      setIsTyping(false)
      inputRef.current?.focus()
    }
  }, [waNumber, language, isTyping, activeTab])

  const loadDocuments = async (appId) => {
    if (!appId) return
    try {
      const res = await fetch(`${API}/applications/${appId}/documents`)
      if (res.ok) setDocuments(await res.json())
    } catch {}
  }

  const handleSend = (e) => { e?.preventDefault(); sendMessage(inputText) }
  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }

  const toggleListening = () => {
    if (!recognitionRef.current) {
      toast.error('Speech recognition not supported in this browser')
      return
    }
    if (isListening) {
      recognitionRef.current.stop()
    } else {
      const langMap = { en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN', bn: 'bn-IN', ta: 'ta-IN', te: 'te-IN', gu: 'gu-IN' }
      recognitionRef.current.lang = langMap[language] || 'en-IN'
      recognitionRef.current.start()
    }
  }

  const handleFileSelect = (docType) => {
    pendingDocType.current = docType
    fileInputRef.current.click()
    setShowAttach(false)
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !pendingDocType.current) return
    const docType = pendingDocType.current

    // Show upload in chat
    const uploadMsg = {
      id: Date.now(), role: 'USER',
      content: `📎 Uploading ${docType.replace(/_/g, ' ')}...`,
      modality: 'DOCUMENT', fileName: file.name, docType,
      time: new Date().toISOString(),
    }
    setMessages(prev => [...prev, uploadMsg])
    setIsTyping(true)

    const formData = new FormData()
    formData.append('from_number', waNumber)
    formData.append('doc_type', docType)
    formData.append('file', file)

    try {
      const res = await fetch(`${API}/whatsapp/upload`, { method: 'POST', body: formData })
      const data = await res.json()

      const botMsg = {
        id: Date.now() + 1, role: 'ASSISTANT',
        content: data.message || '✅ Document received! Verifying…',
        modality: 'TEXT', time: new Date().toISOString(),
      }
      setMessages(prev => [...prev, botMsg])

      if (data.tracking_id) setTrackingId(data.tracking_id)
      toast.success(`${docType.replace(/_/g, ' ')} uploaded!`)

    } catch {
      toast.error('Upload failed')
    } finally {
      setIsTyping(false)
      e.target.value = ''
      pendingDocType.current = null
    }
  }

  const speakText = (text) => {
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const clean = text.replace(/[*#_`~]/g, '').replace(/[✅⚠️🎉🏛️💳]/g, '').slice(0, 250)
    const utt = new SpeechSynthesisUtterance(clean)
    const langMap = { en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN' }
    utt.lang = langMap[language] || 'en-IN'
    window.speechSynthesis.speak(utt)
  }

  const handleStart = (e) => {
    e.preventDefault()
    if (!waNumber.trim()) return
    setNumberSet(true)

    // Send greeting
    setTimeout(() => {
      const greeting = { en: 'Hello', hi: 'नमस्ते', mr: 'नमस्कार' }[language] || 'Hello'
      sendMessage(greeting)
    }, 300)
  }

  // ── ID GATE ──
  if (!numberSet) {
    return (
      <div className={styles.idGate}>
        <div className={styles.idCard}>
          <div className={styles.idLogo}>💬</div>
          <h2 className={styles.idTitle}>Revenue Gov Platform</h2>
          <p className={styles.idSubtitle}>
            WhatsApp Service Assistant<br />
            Enter your WhatsApp number to start your certificate application
          </p>

          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
              {LANGUAGES.slice(0, 4).map(l => (
                <button key={l.code} onClick={() => setLanguage(l.code)}
                  style={{
                    background: language === l.code ? 'rgba(0,168,132,0.15)' : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${language === l.code ? '#00a884' : '#374045'}`,
                    color: language === l.code ? '#00a884' : '#8696a0',
                    borderRadius: 20, padding: '4px 12px', cursor: 'pointer',
                    fontSize: 13, transition: 'all 0.2s'
                  }}>
                  {l.flag} {l.label}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleStart}>
            <div className={styles.idInputRow}>
              <input className={styles.idInput} placeholder="+91 9876543210"
                value={waNumber} onChange={e => setWaNumber(e.target.value)} required />
              <button className={styles.idBtn} type="submit">Start →</button>
            </div>
          </form>
          <p className={styles.idNote}>🔒 Your number is hashed — we never store it in plaintext.</p>
        </div>
      </div>
    )
  }

  const currentStepIdx = LIFECYCLE_STEPS.findIndex(s => s.key === (appData?.status || 'DRAFT'))

  return (
    <div className={styles.shell}>

      {/* ── LEFT SIDEBAR (Contact List) ── */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <div className={styles.sidebarAvatar}>🏛️</div>
          <div className={styles.sidebarActions}>
            <button className={styles.sidebarActionBtn} title="Language" onClick={() => setShowLang(v => !v)}>
              <Globe size={20} />
            </button>
            <button className={styles.sidebarActionBtn} title="Refresh" onClick={loadHistory}>
              <RefreshCw size={20} />
            </button>
          </div>
        </div>

        <div className={styles.searchBar}>
          <div className={styles.searchWrapper}>
            <Search size={14} className={styles.searchIcon} />
            <input className={styles.searchInput} placeholder="Search or start a new conversation" readOnly />
          </div>
        </div>

        {/* Active conversation */}
        <div className={styles.contactList}>
          <div className={`${styles.contactItem} ${styles.active}`}>
            <div className={styles.contactAvatar}>🏛️</div>
            <div className={styles.contactInfo}>
              <div className={styles.contactName}>Revenue Gov Assistant</div>
              <div className={styles.contactPreview}>
                {messages.length > 0 ? messages[messages.length - 1].content.slice(0, 40) + '…' : 'Certificate Services · Government Portal'}
              </div>
            </div>
            <div className={styles.contactMeta}>
              <div className={styles.contactTime}>
                {messages.length > 0 ? new Date(messages[messages.length - 1].time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
              </div>
              {isTyping && <div className={styles.unreadBadge}>!</div>}
            </div>
          </div>
        </div>
      </aside>

      {/* ── MAIN CHAT AREA ── */}
      <div className={styles.chatMain}>

        {/* Chat Header */}
        <header className={styles.chatHeader}>
          <div className={styles.chatHeaderAvatar}>🏛️</div>
          <div className={styles.chatHeaderInfo}>
            <div className={styles.chatHeaderName}>Revenue Gov Assistant</div>
            <div className={styles.chatHeaderStatus}>
              {isTyping ? '⌨️ typing…' : '🟢 online · ' + LANGUAGES.find(l => l.code === language)?.label}
            </div>
          </div>
          <div className={styles.chatHeaderTools}>
            {/* Language */}
            <div className={styles.langSelector}>
              <button className={styles.toolBtn} onClick={() => setShowLang(v => !v)} title="Language">
                <Globe size={20} />
              </button>
              {showLang && (
                <div className={styles.langDropdown}>
                  {LANGUAGES.map(l => (
                    <button key={l.code} className={`${styles.langOption} ${language === l.code ? styles.selected : ''}`}
                      onClick={() => { setLanguage(l.code); setShowLang(false); toast.success(`Language: ${l.label}`) }}>
                      {l.flag} {l.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button className={styles.toolBtn} onClick={() => {
              setMessages([]); setNumberSet(false); setWaNumber(''); setTrackingId(null)
            }} title="New conversation">
              <RefreshCw size={20} />
            </button>
          </div>
        </header>

        {/* Tracking Banner */}
        {trackingId && (
          <div className={styles.trackingBanner}>
            <span>🏷️</span>
            <div>
              <div className={styles.trackingLabel}>Tracking ID</div>
              <div className={styles.trackingId}>{trackingId}</div>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <div className={styles.trackingStatus}>{appData?.status || 'ACTIVE'}</div>
            </div>
          </div>
        )}

        {/* Messages */}
        <div className={styles.messages}>
          {/* Date separator */}
          <div className={styles.dateSeperator}>
            <div className={styles.datePill}>
              {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}
            </div>
          </div>

          {/* Empty state */}
          {messages.length === 0 && !isTyping && (
            <div style={{ textAlign: 'center', marginTop: 40 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🏛️</div>
              <div style={{ color: '#8696a0', fontSize: 15 }}>
                Welcome to Revenue Gov Platform!<br />
                <span style={{ fontSize: 13 }}>Send a message to start your certificate application</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 20 }}>
                {[
                  { en: 'Income Certificate', hi: 'आय प्रमाण पत्र', mr: 'उत्पन्नाचा दाखला' },
                  { en: 'Caste Certificate', hi: 'जाति प्रमाण पत्र', mr: 'जात प्रमाणपत्र' },
                  { en: 'Domicile Certificate', hi: 'अधिवास प्रमाण पत्र', mr: 'अधिवास प्रमाणपत्र' },
                ].map(s => (
                  <button key={s.en} onClick={() => sendMessage(s[language] || s.en)} className={styles.optionBtn}>
                    {s[language] || s.en}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Message list */}
          {messages.map((msg) => (
            <div key={msg.id} className={`${styles.msgRow} ${msg.role === 'USER' ? styles.userRow : styles.assistantRow}`}>
              <div className={`${styles.bubble} ${msg.role === 'USER' ? styles.user : styles.assistant}`}>

                {/* Voice note */}
                {msg.modality === 'VOICE' ? (
                  <div className={styles.voiceBubble}>
                    <button className={styles.voicePlay} onClick={() => speakText(msg.content)}>
                      <Play size={16} />
                    </button>
                    <div className={styles.voiceWave}>
                      {[...Array(7)].map((_, i) => <div key={i} className={styles.voiceBar} />)}
                    </div>
                    <span style={{ fontSize: 11, color: '#8696a0' }}>0:03</span>
                  </div>
                ) : msg.modality === 'DOCUMENT' ? (
                  <div className={styles.docBubble}>
                    <div className={styles.docIcon}>📄</div>
                    <div className={styles.docInfo}>
                      <div className={styles.docName}>{msg.fileName || 'Document'}</div>
                      <div className={styles.docSize}>{msg.docType?.replace(/_/g, ' ')}</div>
                    </div>
                  </div>
                ) : (
                  <div className={styles.bubbleText}>
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                )}

                {/* Quick reply options */}
                {msg.options?.length > 0 && (
                  <div className={styles.optionsRow}>
                    {msg.options.map(opt => (
                      <button key={opt.id} className={styles.optionBtn}
                        onClick={() => sendMessage(opt.id + ' ' + opt.label)}>
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}

                {/* Listen button for assistant */}
                {msg.role === 'ASSISTANT' && (
                  <button onClick={() => speakText(msg.content)}
                    style={{ background: 'none', border: 'none', color: '#8696a0', cursor: 'pointer', padding: '4px 0 0', display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                    <Volume2 size={12} /> Listen
                  </button>
                )}

                <div className={styles.bubbleMeta}>
                  <span className={styles.bubbleTime}>
                    {new Date(msg.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  {msg.role === 'USER' && <span className={styles.bubbleTick}><CheckCheck size={14} /></span>}
                </div>
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {isTyping && (
            <div className={`${styles.msgRow} ${styles.assistantRow}`}>
              <div className={`${styles.bubble} ${styles.assistant} ${styles.typingBubble}`}>
                <span className={styles.typingDot} />
                <span className={styles.typingDot} />
                <span className={styles.typingDot} />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* ── Input Bar ── */}
        <div className={styles.inputArea}>
          <div className={styles.inputRow}>
            {/* Attachment */}
            <div style={{ position: 'relative' }}>
              <button className={styles.inputActionBtn} onClick={() => setShowAttach(v => !v)} title="Attach">
                <Paperclip size={22} />
              </button>
              {showAttach && (
                <div className={styles.attachMenu}>
                  {DOC_TYPES.map(d => (
                    <button key={d.type} className={styles.attachOption} onClick={() => handleFileSelect(d.type)}>
                      <div className={styles.attachIcon} style={{ background: 'rgba(0,168,132,0.15)' }}>{d.icon}</div>
                      <span className={styles.attachLabel}>{d.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Text input */}
            <textarea
              ref={inputRef}
              className={styles.textBox}
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isListening ? '🎙️ Listening…' : 'Type a message'}
              rows={1}
              maxLength={500}
              disabled={isListening}
            />

            {/* Mic or Send */}
            {inputText.trim() ? (
              <button className={styles.sendBtn} onClick={handleSend} disabled={isTyping}>
                <Send size={20} />
              </button>
            ) : (
              <button
                className={`${styles.inputActionBtn} ${isListening ? styles.recording : ''}`}
                onClick={toggleListening}
                title={isListening ? 'Stop' : 'Voice input'}
              >
                {isListening ? <MicOff size={22} /> : <Mic size={22} />}
              </button>
            )}
          </div>
        </div>
        <input type="file" ref={fileInputRef} onChange={handleFileChange} style={{ display: 'none' }} accept="image/*,.pdf" />
      </div>

      {/* ── RIGHT PANEL ── */}
      <aside className={styles.rightPanel}>
        <div className={styles.panelHeader}>
          <div className={styles.panelTitle}>Application Info</div>
          <div className={styles.panelSubtitle}>
            {trackingId ? `Tracking: ${trackingId}` : 'No active application yet'}
          </div>
        </div>

        <div className={styles.panelTabs}>
          {[['form', 'FORM'], ['docs', 'DOCS'], ['timeline', 'TRACK']].map(([key, label]) => (
            <button key={key} className={`${styles.panelTab} ${activeTab === key ? styles.active : ''}`}
              onClick={() => setActiveTab(key)}>
              {label}
            </button>
          ))}
        </div>

        <div className={styles.panelContent}>

          {/* TAB: FORM */}
          {activeTab === 'form' && (
            <div>
              {appData ? (
                <>
                  <div className={styles.progressSection}>
                    <div className={styles.progressLabel}>
                      <span>Progress</span>
                      <span>{appData.progress_percent || 0}%</span>
                    </div>
                    <div className={styles.progressTrack}>
                      <div className={styles.progressFill} style={{ width: `${appData.progress_percent || 0}%` }} />
                    </div>
                  </div>

                  <div className={styles.fieldCard}>
                    <div className={styles.fieldLabel}>Service</div>
                    <span className={styles.fieldValue}>{appData.service_name || '—'}</span>
                  </div>
                  <div className={styles.fieldCard}>
                    <div className={styles.fieldLabel}>Status</div>
                    <span className={styles.fieldValue}>{appData.status || '—'}</span>
                  </div>
                  <div className={styles.fieldCard}>
                    <div className={styles.fieldLabel}>Channel Origin</div>
                    <span className={styles.fieldValue}>{appData.channel_origin || 'WHATSAPP'}</span>
                  </div>
                </>
              ) : (
                <div style={{ textAlign: 'center', padding: '32px 16px', color: '#8696a0' }}>
                  <div style={{ fontSize: 40, marginBottom: 12 }}>💬</div>
                  <div style={{ fontSize: 14 }}>Start a conversation to create your application</div>
                </div>
              )}
            </div>
          )}

          {/* TAB: DOCS */}
          {activeTab === 'docs' && (
            <div>
              {documents.length > 0 ? documents.map(doc => (
                <div key={doc.id} style={{ background: '#202c33', borderRadius: 8, padding: 12, marginBottom: 8 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ fontSize: 20 }}>📄</span>
                    <div>
                      <div style={{ fontSize: 13, color: '#e9edef', fontWeight: 500 }}>{doc.doc_type?.replace(/_/g, ' ')}</div>
                      <div style={{ fontSize: 11, color: '#8696a0' }}>{doc.upload_channel} · {doc.verification_status}</div>
                    </div>
                    <div style={{ marginLeft: 'auto', fontSize: 14, fontWeight: 700, color: getScoreColor(doc.overall_match_score || 0) }}>
                      {doc.overall_match_score ? `${doc.overall_match_score}%` : '—'}
                    </div>
                  </div>
                  {doc.overall_match_score && (
                    <div className={styles.ocrBar}>
                      <div className={styles.ocrBarFill} style={{ width: `${doc.overall_match_score}%`, background: getScoreColor(doc.overall_match_score) }} />
                    </div>
                  )}
                </div>
              )) : (
                <div style={{ textAlign: 'center', padding: '32px 16px', color: '#8696a0' }}>
                  <div style={{ fontSize: 40, marginBottom: 12 }}>📁</div>
                  <div style={{ fontSize: 14 }}>Upload documents using the 📎 button in chat</div>
                </div>
              )}
            </div>
          )}

          {/* TAB: TIMELINE */}
          {activeTab === 'timeline' && (
            <div>
              <div className={styles.timeline}>
                {LIFECYCLE_STEPS.map((step, idx) => {
                  const done = idx < currentStepIdx
                  const current = idx === currentStepIdx
                  return (
                    <div key={step.key} className={styles.timelineItem}>
                      <div className={`${styles.timelineDot} ${done ? styles.done : ''} ${current ? styles.current : ''}`}>
                        {done ? '✓' : idx + 1}
                      </div>
                      <div className={styles.timelineInfo}>
                        <div className={styles.timelineTitle}>{step.label}</div>
                        {current && <div className={styles.timelineChannel}>WHATSAPP</div>}
                      </div>
                    </div>
                  )
                })}
              </div>

              {trackingId && (
                <div style={{ marginTop: 16, background: '#202c33', borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 11, color: '#8696a0', marginBottom: 4 }}>TRACKING ID</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: '#25d366', fontFamily: 'monospace' }}>{trackingId}</div>
                  <a href={`/tracking/${trackingId}`} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: 12, color: '#00a884', textDecoration: 'none', marginTop: 8, display: 'block' }}>
                    Check status on Web Portal →
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}
