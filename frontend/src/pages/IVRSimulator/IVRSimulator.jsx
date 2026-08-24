import { useState, useRef, useEffect } from 'react'
import { Mic, MicOff, PhoneCall, PhoneOff, Volume2, Hash, Delete } from 'lucide-react'
import toast from 'react-hot-toast'
import styles from './IVRSimulator.module.css'

const API = 'http://localhost:8000/api/v1'

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिंदी' },
  { code: 'mr', label: 'मराठी' },
]

const DIALPAD = [
  ['1', '2', '3'],
  ['4', '5', '6'],
  ['7', '8', '9'],
  ['*', '0', '#'],
]

const MENU_HINTS = {
  en: [
    { key: '1', hint: 'Application Status' },
    { key: '2', hint: 'Tracking ID' },
    { key: '3', hint: 'Payment Status' },
    { key: '0', hint: 'Repeat Menu' },
  ],
  hi: [
    { key: '1', hint: 'आवेदन स्थिति' },
    { key: '2', hint: 'ट्रैकिंग ID' },
    { key: '3', hint: 'भुगतान स्थिति' },
    { key: '0', hint: 'दोहराएं' },
  ],
  mr: [
    { key: '1', hint: 'अर्जाची स्थिती' },
    { key: '2', hint: 'ट्रॅकिंग ID' },
    { key: '3', hint: 'पेमेंट स्थिती' },
    { key: '0', hint: 'पुन्हा ऐका' },
  ],
}

export default function IVRSimulator() {
  const [callState, setCallState] = useState('idle') // idle | calling | active | ended
  const [language, setLanguage] = useState('en')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [dialing, setDialing] = useState('')
  const [callDuration, setCallDuration] = useState(0)
  const [callId] = useState(() => `CALL-${Date.now()}`)
  const [sessionId, setSessionId] = useState(null)
  const [transcript, setTranscript] = useState([])
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [appInfo, setAppInfo] = useState(null)
  const [citizenFound, setCitizenFound] = useState(false)

  const timerRef = useRef(null)
  const transcriptEndRef = useRef(null)
  const recognitionRef = useRef(null)

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  // Timer
  useEffect(() => {
    if (callState === 'active') {
      timerRef.current = setInterval(() => setCallDuration(d => d + 1), 1000)
    } else {
      clearInterval(timerRef.current)
      if (callState !== 'active') setCallDuration(0)
    }
    return () => clearInterval(timerRef.current)
  }, [callState])

  // STT init
  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const rec = new SR()
    rec.continuous = false
    rec.interimResults = false
    rec.onstart = () => setIsListening(true)
    rec.onend = () => setIsListening(false)
    rec.onresult = async (e) => {
      const text = e.results[0][0].transcript
      await handleVoiceInput(text)
    }
    rec.onerror = () => setIsListening(false)
    recognitionRef.current = rec
  }, [callState, language])

  const formatTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  const speakText = (text, lang = language) => {
    if (!window.speechSynthesis) {
      setTranscript(prev => [...prev, { role: 'IVR', text }])
      return
    }
    window.speechSynthesis.cancel()
    setIsSpeaking(true)
    const clean = text.replace(/[*#]/g, '').slice(0, 500)
    const utt = new SpeechSynthesisUtterance(clean)
    const langMap = { en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN' }
    utt.lang = langMap[lang] || 'en-IN'
    utt.rate = 0.9
    utt.onend = () => setIsSpeaking(false)
    utt.onerror = () => setIsSpeaking(false)
    window.speechSynthesis.speak(utt)
    setTranscript(prev => [...prev, { role: 'IVR', text }])
  }

  const startCall = async () => {
    if (!phoneNumber.trim()) {
      toast.error('Enter your phone number first')
      return
    }
    setCallState('calling')
    setTranscript([])

    // Simulate ring for 2 seconds
    await new Promise(r => setTimeout(r, 2000))
    setCallState('active')

    try {
      const res = await fetch(`${API}/ivr/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          call_id: callId,
          caller_phone: phoneNumber,
          language,
        }),
      })
      const data = await res.json()
      setSessionId(data.session_id)
      setCitizenFound(data.citizen_found)
      setAppInfo(data.app_info)

      speakText(data.greeting_text, language)

    } catch {
      speakText('Welcome to Revenue Government Platform! For status press 1, tracking press 2, payment press 3.', language)
    }
  }

  const endCall = async () => {
    window.speechSynthesis?.cancel()
    setCallState('ended')
    setIsListening(false)

    const goodbye = {
      en: 'Thank you for calling Revenue Government Platform. Goodbye!',
      hi: 'धन्यवाद। अलविदा!',
      mr: 'धन्यवाद. पुन्हा भेटू.',
    }[language]

    speakText(goodbye, language)
    setTranscript(prev => [...prev, { role: 'SYSTEM', text: '— Call ended —' }])

    try {
      await fetch(`${API}/ivr/end?call_id=${callId}`, { method: 'POST' })
    } catch {}

    setTimeout(() => setCallState('idle'), 3000)
  }

  const handleDTMF = async (key) => {
    if (callState !== 'active') return

    // Dial pad click sound simulation
    setDialing(prev => prev + key)

    setTranscript(prev => [...prev, { role: 'USER', text: `[Keypad: ${key}]` }])

    try {
      const res = await fetch(`${API}/ivr/input`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          call_id: callId,
          input_type: 'dtmf',
          dtmf_key: key,
          language,
        }),
      })
      const data = await res.json()
      if (data.response_text) speakText(data.response_text, language)
    } catch {
      const fallback = {
        '1': { en: 'Status: Your application is under review.', hi: 'स्थिति: आवेदन समीक्षा में है।', mr: 'स्थिती: अर्ज आढाव्यात आहे.' },
        '2': { en: 'No tracking ID found for this number.', hi: 'ट्रैकिंग ID नहीं मिली।', mr: 'ट्रॅकिंग ID सापडली नाही.' },
        '3': { en: 'Payment status: Pending.', hi: 'भुगतान स्थिति: लंबित।', mr: 'पेमेंट स्थिती: प्रलंबित.' },
        '0': { en: 'Press 1 for status, 2 for tracking, 3 for payment.', hi: 'स्थिति के लिए 1, ट्रैकिंग के लिए 2, भुगतान के लिए 3।', mr: 'स्थितीसाठी 1, ट्रॅकिंगसाठी 2, पेमेंटसाठी 3.' },
      }
      const msg = fallback[key]?.[language] || 'Option received.'
      speakText(msg, language)
    }
  }

  const handleVoiceInput = async (text) => {
    if (callState !== 'active') return
    setTranscript(prev => [...prev, { role: 'USER', text: `🎙️ "${text}"` }])

    try {
      const res = await fetch(`${API}/ivr/input`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          call_id: callId,
          input_type: 'voice',
          voice_text: text,
          language,
        }),
      })
      const data = await res.json()
      if (data.response_text) speakText(data.response_text, language)
    } catch {
      speakText('I could not process that. Please try pressing a key.', language)
    }
  }

  const startListening = () => {
    if (!recognitionRef.current) {
      toast.error('Speech recognition not supported')
      return
    }
    const langMap = { en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN' }
    recognitionRef.current.lang = langMap[language] || 'en-IN'
    recognitionRef.current.start()
  }

  return (
    <div className={styles.shell}>

      {/* Left: Info Panel */}
      <div className={styles.infoPanel}>
        <div className={styles.infoPanelHeader}>
          <div className={styles.infoPanelIcon}>📞</div>
          <h2 className={styles.infoPanelTitle}>IVR Helpline</h2>
          <p className={styles.infoPanelSub}>Revenue Government Platform<br />Interactive Voice Response</p>
        </div>

        {/* Language Selector */}
        <div className={styles.langSection}>
          <div className={styles.langLabel}>Select Language / भाषा चुनें / भाषा निवडा</div>
          <div className={styles.langBtns}>
            {LANGUAGES.map(l => (
              <button key={l.code}
                className={`${styles.langBtn} ${language === l.code ? styles.langBtnActive : ''}`}
                onClick={() => setLanguage(l.code)}
                disabled={callState === 'active'}>
                {l.label}
              </button>
            ))}
          </div>
        </div>

        {/* Menu Guide */}
        <div className={styles.menuGuide}>
          <div className={styles.menuGuideTitle}>
            {language === 'en' ? 'Menu Options' : language === 'hi' ? 'मेनू विकल्प' : 'मेनू पर्याय'}
          </div>
          {MENU_HINTS[language]?.map(h => (
            <div key={h.key} className={styles.menuHint}>
              <div className={styles.menuKey}>{h.key}</div>
              <div className={styles.menuHintText}>{h.hint}</div>
            </div>
          ))}
        </div>

        {/* App Info */}
        {appInfo && (
          <div className={styles.appInfoBox}>
            <div className={styles.appInfoTitle}>Application Found</div>
            <div className={styles.appInfoRow}>
              <span>Service:</span><span>{appInfo.service}</span>
            </div>
            <div className={styles.appInfoRow}>
              <span>Tracking:</span><span style={{ color: '#22d3ee', fontFamily: 'monospace' }}>{appInfo.tracking_id}</span>
            </div>
            <div className={styles.appInfoRow}>
              <span>Status:</span><span style={{ color: '#4ade80' }}>{appInfo.status}</span>
            </div>
          </div>
        )}

        {/* Transcript */}
        {transcript.length > 0 && (
          <div className={styles.transcriptPanel}>
            <div className={styles.transcriptTitle}>Call Transcript</div>
            <div className={styles.transcriptList}>
              {transcript.map((t, i) => (
                <div key={i} className={`${styles.transcriptRow} ${styles[t.role.toLowerCase()]}`}>
                  <span className={styles.transcriptRole}>{t.role === 'IVR' ? '🔊 IVR' : t.role === 'USER' ? '👤 You' : '⚙️'}</span>
                  <span className={styles.transcriptText}>{t.text}</span>
                </div>
              ))}
              <div ref={transcriptEndRef} />
            </div>
          </div>
        )}
      </div>

      {/* Right: Phone UI */}
      <div className={styles.phoneContainer}>
        <div className={styles.phone}>

          {/* Phone Screen */}
          <div className={styles.screen}>
            {callState === 'idle' && (
              <>
                <div className={styles.screenTime}>
                  {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
                <div className={styles.screenDate}>
                  {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}
                </div>
                <div className={styles.screenCallerName}>Revenue Gov Helpline</div>
                <div className={styles.screenNumber}>1800-XXX-XXXX</div>

                {/* Phone input */}
                <div className={styles.phoneInputSection}>
                  <div className={styles.numberLabel}>Your Phone Number</div>
                  <input
                    className={styles.numberInput}
                    value={phoneNumber}
                    onChange={e => setPhoneNumber(e.target.value)}
                    placeholder="+91 9876543210"
                    type="tel"
                  />
                </div>
              </>
            )}

            {callState === 'calling' && (
              <>
                <div className={styles.callingAnimation}>
                  <div className={styles.callingRing} />
                  <div className={styles.callingRing} style={{ animationDelay: '0.3s' }} />
                  <div className={styles.callingRing} style={{ animationDelay: '0.6s' }} />
                  <div className={styles.callingAvatar}>🏛️</div>
                </div>
                <div className={styles.callingText}>Calling…</div>
                <div className={styles.callingNum}>Revenue Gov Helpline</div>
              </>
            )}

            {callState === 'active' && (
              <>
                <div className={styles.activeAvatar}>🏛️</div>
                <div className={styles.activeName}>Revenue Gov Helpline</div>
                <div className={styles.activeStatus}>
                  {isSpeaking ? '🔊 Speaking…' : isListening ? '🎙️ Listening…' : 'Connected'}
                </div>
                <div className={styles.callTimer}>{formatTime(callDuration)}</div>

                {isSpeaking && (
                  <div className={styles.waveform}>
                    {[...Array(12)].map((_, i) => (
                      <div key={i} className={styles.wavebar}
                        style={{ animationDelay: `${i * 0.1}s`, height: `${Math.random() * 24 + 8}px` }} />
                    ))}
                  </div>
                )}
              </>
            )}

            {callState === 'ended' && (
              <>
                <div className={styles.endedIcon}>📵</div>
                <div className={styles.endedText}>Call Ended</div>
                <div className={styles.endedDuration}>{formatTime(callDuration)}</div>
              </>
            )}
          </div>

          {/* Dial Pad */}
          {(callState === 'idle' || callState === 'active') && (
            <div className={styles.dialpad}>
              {DIALPAD.map((row, ri) => (
                <div key={ri} className={styles.dialRow}>
                  {row.map(key => (
                    <button key={key} className={styles.dialKey}
                      onClick={() => callState === 'active' ? handleDTMF(key) : setPhoneNumber(p => p + key)}
                      disabled={callState === 'calling'}>
                      <span className={styles.dialKeyNum}>{key}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* Action Buttons */}
          <div className={styles.actionRow}>
            {callState === 'idle' ? (
              <>
                <button className={styles.actionBtn} onClick={() => setPhoneNumber(p => p.slice(0, -1))} title="Backspace">
                  <Delete size={22} />
                </button>
                <button className={styles.callBtn} onClick={startCall}>
                  <PhoneCall size={28} />
                </button>
                <div className={styles.actionBtn} />
              </>
            ) : callState === 'active' ? (
              <>
                {/* Voice input */}
                <button
                  className={`${styles.actionBtn} ${isListening ? styles.actionActive : ''}`}
                  onClick={startListening}
                  title="Speak">
                  {isListening ? <MicOff size={22} /> : <Mic size={22} />}
                </button>

                {/* End call */}
                <button className={styles.hangupBtn} onClick={endCall}>
                  <PhoneOff size={28} />
                </button>

                {/* Speaker */}
                <button className={`${styles.actionBtn} ${isSpeaking ? styles.actionActive : ''}`} title="Speaker">
                  <Volume2 size={22} />
                </button>
              </>
            ) : (
              <div className={styles.callBtn} style={{ opacity: 0.4, cursor: 'not-allowed' }}>
                <PhoneOff size={28} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
