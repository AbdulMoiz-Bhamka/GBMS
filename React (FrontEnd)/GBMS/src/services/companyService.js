import { apiRequest } from './authService'

function queryString(params) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  const value = query.toString()
  return value ? `?${value}` : ''
}

export const companyService = {
  list: (params = {}) => apiRequest(`/api/v1/companies${queryString(params)}`),
  get: (companyId) => apiRequest(`/api/v1/companies/${companyId}`),
  create: (payload) => apiRequest('/api/v1/companies', { method: 'POST', body: JSON.stringify(payload) }),
  update: (companyId, payload) => apiRequest(`/api/v1/companies/${companyId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  setStatus: (companyId, company_status) => apiRequest(`/api/v1/companies/${companyId}/status`, { method: 'PATCH', body: JSON.stringify({ company_status }) }),
  users: (companyId) => apiRequest(`/api/v1/companies/${companyId}/users`),
  createUser: (companyId, payload) => apiRequest(`/api/v1/companies/${companyId}/users`, { method: 'POST', body: JSON.stringify(payload) }),
}
