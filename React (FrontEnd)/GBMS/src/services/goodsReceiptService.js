import { apiRequest } from './authService'

function queryString(params) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  const value = query.toString()
  return value ? `?${value}` : ''
}

export const goodsReceiptService = {
  options: (purchase_order_id) => apiRequest(`/api/v1/goods-receipts/options${queryString({ purchase_order_id })}`),
  create: (payload) => apiRequest('/api/v1/goods-receipts', { method: 'POST', body: JSON.stringify(payload) }),
  lots: (params = {}) => apiRequest(`/api/v1/goods-receipts/lots${queryString(params)}`),
  lotLabel: (lotId) => apiRequest(`/api/v1/goods-receipts/lots/${lotId}/label`),
  lot: (lotId) => apiRequest(`/api/v1/goods-receipts/lots/${lotId}`),
  lookupBarcode: (value) => apiRequest(`/api/v1/goods-receipts/barcode/${encodeURIComponent(value)}`),
}
