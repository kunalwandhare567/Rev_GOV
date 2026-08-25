import { create } from 'zustand'
import { CONV_NODES, STORAGE_KEYS } from '../utils/constants'
import { conversationApi } from '../api/conversation'

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
  documents: [],

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
    
    // If citizenRef changed, do clean wipe
    if (resp.citizen_ref && get().citizenRef && resp.citizen_ref !== get().citizenRef) {
      get().reset()
    }

    if (resp.status === 'inactive' || resp.status === 'no_active_session') {
      localStorage.removeItem(STORAGE_KEYS.SESSION_ID)
      set({
        sessionId: null,
        citizenRef: resp.citizen_ref || get().citizenRef,
        currentNode: CONV_NODES.INIT,
        consentGiven: false,
        paymentStatus: 'PENDING',
        anomalyScore: 0.0,
        applicationNumber: null,
        serviceType: null,
        filledSlots: {},
        missingSlots: [],
        validationErrors: [],
        messages: [],
        documents: [],
      })
      return
    }

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
      filledSlots:      resp.filled_slots     ?? {},
      missingSlots:     resp.missing_slots    ?? [],
      validationErrors: resp.validation_errors ?? [],
      applicationNumber:resp.application_number ?? null,
      serviceType:      resp.service_type     ?? (resp.extra_data?.service_type ?? null),
      documents: resp.documents ? (
        (() => {
          const map = new Map()
          for (const d of resp.documents) {
            const key = d.id || d.doc_type
            map.set(key, d)
          }
          return Array.from(map.values())
        })()
      ) : [],
      isConnected: true,
    })
  },
  resolveMismatch: async (fieldName, resolution) => {
    set({ isTyping: true })
    try {
      const resp = await conversationApi.resolveMismatch(get().citizenIdentifier, fieldName, resolution)
      get().syncFromResponse(resp)
      get().addMessage({
        role: 'ASSISTANT',
        content: resp.response || `Resolved mismatch for '${fieldName}' using ${resolution}.`,
        language: resp.language || get().language
      })
    } catch (err) {
      throw err
    } finally {
      set({ isTyping: false })
    }
  },
  simulateGovApproval: async () => {
    const appNum = get().applicationNumber
    if (!appNum) return
    set({ isTyping: true })
    try {
      await conversationApi.simulateGovApproval(appNum)
      // Fetch fresh session state to synchronize
      const sessionData = await conversationApi.getSession(get().citizenIdentifier)
      get().syncFromResponse(sessionData)
      get().addMessage({
        role: 'ASSISTANT',
        content: `🟢 Government verification completed! Application **${appNum}** has been **APPROVED**.\n\nPlease proceed to make the payment of **₹50** and upload the payment receipt screenshot in the form panel.`,
        language: get().language
      })
    } catch (err) {
      throw err
    } finally {
      set({ isTyping: false })
    }
  },
  uploadDocument: async (docType, file) => {
    set({ isTyping: true })
    try {
      const resp = await conversationApi.uploadDocument(get().citizenIdentifier, get().sessionId, docType, file)
      get().syncFromResponse(resp)
      get().addMessage({
        role: 'ASSISTANT',
        content: resp.response || "Document uploaded successfully.",
        language: get().language
      })
    } catch (err) {
      throw err
    } finally {
      set({ isTyping: false })
    }
  },
  sendVoiceMessage: async (transcript, file) => {
    set({ isTyping: true })
    const userMsgText = transcript || "🎤 Spoken Voice Note"
    get().addMessage({ role: 'USER', content: userMsgText, language: get().language })

    try {
      const resp = await conversationApi.sendVoiceMessage(
        get().citizenIdentifier,
        get().channel,
        get().language,
        transcript,
        file
      )
      get().syncFromResponse(resp)
      get().addMessage({
        role: 'ASSISTANT',
        content: resp.response,
        language: resp.language || get().language,
        audioUrl: resp.audio_url
      })
      return resp
    } catch (err) {
      get().addMessage({
        role: 'ASSISTANT',
        content: '⚠️ Voice processing failed. Please try again.',
        language: get().language
      })
      throw err
    } finally {
      set({ isTyping: false })
    }
  },
  reset: () => {
    localStorage.removeItem(STORAGE_KEYS.SESSION_ID)
    localStorage.removeItem(STORAGE_KEYS.CITIZEN_IDENTIFIER)
    set({
      citizenIdentifier: null,
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
      documents: [],
      isConnected: false,
    })
  },
}))

export default useChatStore
