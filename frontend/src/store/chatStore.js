import { create } from 'zustand'
import { CONV_NODES, STORAGE_KEYS } from '../utils/constants'

const useChatStore = create((set, get) => ({
  citizenIdentifier: localStorage.getItem(STORAGE_KEYS.CITIZEN_IDENTIFIER) || null,
  citizenRef: null,
  sessionId: localStorage.getItem(STORAGE_KEYS.SESSION_ID) || null,
  currentNode: CONV_NODES.INIT,
  channel: 'WEB',
  language: localStorage.getItem(STORAGE_KEYS.PREFERRED_LANG) || 'en',
  literacyLevel: 'MEDIUM',
  consentGiven: false,
  paymentStatus: 'PENDING',
  anomalyScore: 0.0,
  applicationNumber: null,
  serviceType: null,
  filledSlots: {},
  missingSlots: [],
  validationErrors: [],
  messages: [],
  isTyping: false,
  isConnected: false,

  setCitizenIdentifier: (id) => {
    localStorage.setItem(STORAGE_KEYS.CITIZEN_IDENTIFIER, id)
    set({ citizenIdentifier: id })
  },
  setLanguage: (lang) => {
    localStorage.setItem(STORAGE_KEYS.PREFERRED_LANG, lang)
    set({ language: lang })
  },
  setTyping: (v) => set({ isTyping: v }),
  addMessage: (msg) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          timestamp: new Date().toISOString(),
          ...msg,
        },
      ],
    })),
  syncFromResponse: (resp) => {
    if (!resp) return
    const sessionId = resp.session_id || get().sessionId
    if (sessionId) localStorage.setItem(STORAGE_KEYS.SESSION_ID, sessionId)
    set({
      sessionId,
      citizenRef:       resp.citizen_ref      ?? get().citizenRef,
      currentNode:      resp.current_node     ?? get().currentNode,
      language:         resp.language         ?? get().language,
      literacyLevel:    resp.literacy_level   ?? get().literacyLevel,
      consentGiven:     resp.consent_given    ?? get().consentGiven,
      paymentStatus:    resp.payment_status   ?? get().paymentStatus,
      anomalyScore:     resp.anomaly_score    ?? get().anomalyScore,
      filledSlots:      resp.filled_slots     ?? get().filledSlots,
      missingSlots:     resp.missing_slots    ?? get().missingSlots,
      validationErrors: resp.validation_errors ?? get().validationErrors,
      applicationNumber:resp.application_number ?? get().applicationNumber,
      serviceType:      resp.extra_data?.service_type ?? get().serviceType,
      isConnected: true,
    })
  },
  reset: () => {
    localStorage.removeItem(STORAGE_KEYS.SESSION_ID)
    set({
      citizenRef: null,
      sessionId: null,
      currentNode: CONV_NODES.INIT,
      channel: 'WEB',
      consentGiven: false,
      paymentStatus: 'PENDING',
      anomalyScore: 0.0,
      applicationNumber: null,
      serviceType: null,
      filledSlots: {},
      missingSlots: [],
      validationErrors: [],
      messages: [],
      isTyping: false,
    })
  },
}))

export default useChatStore
