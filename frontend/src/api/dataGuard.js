import client from './client'

export const dataGuardApi = {
  check: (payload, destination, operation, dataClassification = null) =>
    client.post('/data-guard/check', { payload, destination, operation, data_classification: dataClassification }),
  classify: (payload) =>
    client.post('/data-guard/classify', { payload }),
  getPolicy: () =>
    client.get('/data-guard/policy'),
}
