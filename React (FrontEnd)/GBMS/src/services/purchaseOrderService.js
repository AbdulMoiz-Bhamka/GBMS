import { apiRequest } from './authService'

function queryString(params) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  const value = query.toString()
  return value ? `?${value}` : ''
}

export const purchaseOrderService = {
  formOptions: () => apiRequest('/api/v1/purchase-orders/form-options'),
  list: (params = {}) => apiRequest(`/api/v1/purchase-orders${queryString(params)}`),
  get: (id) => apiRequest(`/api/v1/purchase-orders/${id}`),
  printable: (id) => apiRequest(`/api/v1/purchase-orders/${id}/print`),
  create: (payload) => apiRequest('/api/v1/purchase-orders', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id, payload) => apiRequest(`/api/v1/purchase-orders/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  submit: (id) => apiRequest(`/api/v1/purchase-orders/${id}/submit`, { method: 'POST' }),
  cancel: (id, note = null) => apiRequest(`/api/v1/purchase-orders/${id}/cancel`, { method: 'POST', body: JSON.stringify({ note }) }),
}
