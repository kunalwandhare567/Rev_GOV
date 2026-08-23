import client from './client'

export const conversationApi = {
  sendMessage: (citizenIdentifier, text, channel, language, sessionId = null) =>
    client.post('/conversation/message', {
      citizen_identifier: citizenIdentifier,
      text,
      channel,
      language,
      session_id: sessionId,
    }),

  uploadDocument: (citizenIdentifier, sessionId, docType, file) => {
    const form = new FormData()
    form.append('citizen_identifier', citizenIdentifier)
    form.append('session_id', sessionId)
    form.append('doc_type', docType)
    form.append('file', file)
    form.append('channel', 'WEB')
    return client.post('/conversation/document-upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  switchChannel: (citizenIdentifier, newChannel, language) =>
    client.post('/conversation/channel-switch', {
      citizen_identifier: citizenIdentifier,
      new_channel: newChannel,
      language,
    }),

  getSession: (citizenIdentifier) =>
    client.get(`/conversation/session/${citizenIdentifier}`),

  resolveMismatch: (citizenIdentifier, fieldName, resolution) =>
    client.post('/conversation/resolve-mismatch', {
      citizen_identifier: citizenIdentifier,
      field_name: fieldName,
      resolution,
    }),

  sendVoiceMessage: (citizenIdentifier, channel, language, transcript, file) => {
    const form = new FormData()
    form.append('citizen_identifier', citizenIdentifier)
    form.append('channel', channel)
    form.append('language', language)
    if (transcript) form.append('transcript', transcript)
    if (file) form.append('file', file)
    return client.post('/conversation/voice-message', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  simulateGovApproval: (appNum) =>
    client.post(`/applications/status/${appNum}/simulate-approve`),
}

