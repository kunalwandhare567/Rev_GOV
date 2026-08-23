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
}
