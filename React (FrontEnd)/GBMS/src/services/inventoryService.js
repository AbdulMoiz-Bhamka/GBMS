// src/services/inventoryService.js
import { apiRequest } from './authService'

function queryString(params) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  const value = query.toString()
  return value ? `?${value}` : ''
}

export const inventoryService = {
  categories: () => apiRequest('/api/v1/inventory/categories'),
  createCategory: (payload) => apiRequest('/api/v1/inventory/categories', { method: 'POST', body: JSON.stringify(payload) }),
  units: () => apiRequest('/api/v1/inventory/units'),
  products: (params = {}) => apiRequest(`/api/v1/inventory/products${queryString(params)}`),
  lowStockCount: () => apiRequest('/api/v1/inventory/low-stock/count'),
  getProduct: (productId) => apiRequest(`/api/v1/inventory/products/${productId}`),
  createProduct: (payload) => apiRequest('/api/v1/inventory/products', { method: 'POST', body: JSON.stringify(payload) }),
  updateProduct: (productId, payload) => apiRequest(`/api/v1/inventory/products/${productId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  setProductStatus: (productId, is_active) => apiRequest(`/api/v1/inventory/products/${productId}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  receiveStock: (productId, payload) => apiRequest(`/api/v1/inventory/products/${productId}/stock/receipts`, { method: 'POST', body: JSON.stringify(payload) }),
  issueStock: (productId, payload) => apiRequest(`/api/v1/inventory/products/${productId}/stock/issues`, { method: 'POST', body: JSON.stringify(payload) }),
  adjustStock: (productId, payload) => apiRequest(`/api/v1/inventory/products/${productId}/stock/adjustments`, { method: 'POST', body: JSON.stringify(payload) }),
  stockHistory: (productId, params = {}) => apiRequest(`/api/v1/inventory/products/${productId}/stock/transactions${queryString(params)}`),
  generateBarcode: (productId) => apiRequest(`/api/v1/inventory/products/${productId}/barcode`, { method: 'POST' }),
  barcodeLabel: (productId) => apiRequest(`/api/v1/inventory/products/${productId}/barcode`),
  lookupBarcode: (value) => apiRequest(`/api/v1/inventory/barcodes/${encodeURIComponent(value)}`),
}
