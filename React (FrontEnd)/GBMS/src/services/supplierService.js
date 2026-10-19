import { apiRequest } from './authService'

function queryString(params) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  const value = query.toString()
  return value ? `?${value}` : ''
}

export const supplierService = {
  list: (params = {}) => apiRequest(`/api/v1/suppliers${queryString(params)}`),
  get: (supplierId) => apiRequest(`/api/v1/suppliers/${supplierId}`),
  create: (payload) => apiRequest('/api/v1/suppliers', {
    method: 'POST', body: JSON.stringify(payload),
  }),
  update: (supplierId, payload) => apiRequest(`/api/v1/suppliers/${supplierId}`, {
    method: 'PUT', body: JSON.stringify(payload),
  }),
  setStatus: (supplierId, supplier_status) => apiRequest(`/api/v1/suppliers/${supplierId}/status`, {
    method: 'PATCH', body: JSON.stringify({ supplier_status }),
  }),
}
