import { apiRequest } from './authService'

function query(params) {
  const values = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => { if (value !== '' && value != null) values.set(key, value) })
  return values.size ? `?${values}` : ''
}

export const barcodeService = {
  options: () => apiRequest('/api/v1/barcodes/options'),
  list: (params = {}) => apiRequest(`/api/v1/barcodes${query(params)}`),
  create: (payload) => apiRequest('/api/v1/barcodes', { method: 'POST', body: JSON.stringify(payload) }),
  generate: (id) => apiRequest(`/api/v1/barcodes/${id}/generate`, { method: 'POST' }),
  updateMaterials: (id, materials) => apiRequest(`/api/v1/barcodes/${id}/materials`, { method: 'PUT', body: JSON.stringify({ materials }) }),
  label: (id) => apiRequest(`/api/v1/barcodes/${id}/label`),
  lookup: (value) => apiRequest(`/api/v1/barcodes/lookup/${encodeURIComponent(value)}`),
}
