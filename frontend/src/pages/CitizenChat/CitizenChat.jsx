import { useState, useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Send, Mic, RefreshCw, Globe } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import useChatStore from '../../store/chatStore'
import useUIStore from '../../store/uiStore'
import { conversationApi } from '../../api/conversation'
import { t, LANGUAGE_NAMES } from '../../i18n'
import { CONV_NODES, NODE_STEPS, FRAUD_THRESHOLDS, SUPPORTED_LANGS } from '../../utils/constants'
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
  mr: { CONSENT:'संमती', INTENT_DETECTION:'सेवा निवड', SLOT_FILLING:'आपली माहिती', DOCUMENT_CAPTURE:'कागदपत्रे', VALIDATION:'पुनरावलोकन', PAYMENT:'पेमेंट', SUBMITTED:'सादर केले', ESCALATED:'एस्केलेट' },
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
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [store.messages, store.isTyping])

  useEffect(() => {
    if (!store.citizenIdentifier) return
    conversationApi.getSession(store.citizenIdentifier)
      .then(data => { if (data?.session_id && data.current_node !== CONV_NODES.INIT) setShowResume(true) })
      .catch(() => {})
  }, [store.citizenIdentifier])

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
    } catch (err) {
      toast.error(err.message || 'Failed to send message')
      store.addMessage({ role: 'ASSISTANT', content: '⚠️ Connection error. Please try again.', language: store.language })
    } finally {
      store.setTyping(false)
      inputRef.current?.focus()
    }
  }, [store])

  useEffect(() => {
    if (preselectedService && store.currentNode === CONV_NODES.INTENT_DETECTION && idSet) {
      sendMessage(SERVICE_LABELS[preselectedService]?.[store.language] || preselectedService)
    }
  }, [preselectedService, store.currentNode, idSet, sendMessage])

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

  const currentStepIdx = NODE_STEPS.indexOf(store.currentNode)
  const totalSlots = store.missingSlots.length + Object.keys(store.filledSlots).length
  const filledCount = Object.keys(store.filledSlots).length
  const slotPct = totalSlots > 0 ? Math.round((filledCount / totalSlots) * 100) : 0

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
      </aside>

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
          <button type="button" className={styles.inputAction} title={t(store.language,'chat.voiceSoon')}
            onClick={() => toast(t(store.language,'chat.voiceSoon'))}>
            <Mic size={18}/>
          </button>
          <textarea
            ref={inputRef}
            className={styles.textInput}
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t(store.language,'chat.placeholder')}
            rows={1}
            maxLength={500}
          />
          <span className={styles.charCount}>{inputText.length}/500</span>
          <button type="submit" className={styles.sendBtn}
            disabled={!inputText.trim() || store.isTyping}
            aria-label={t(store.language,'chat.send')}>
            <Send size={18}/>
          </button>
        </form>
      </div>
    </div>
  )
}
