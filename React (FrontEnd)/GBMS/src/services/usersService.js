// src/services/usersService.js
import { apiRequest } from './authService'

const companyUsersPath = (companyId) => `/api/v1/companies/${companyId}/users`

export const usersService = {
  options: () => apiRequest('/api/v1/users/assignable-options'),
  list: (companyId, search = '') => {
    const query = new URLSearchParams()
    if (search.trim()) query.set('search', search.trim())
    const queryText = query.toString()
    const suffix = queryText ? `?${queryText}` : ''
    return apiRequest(`${companyUsersPath(companyId)}${suffix}`)
  },
  get: (companyId, userId) => apiRequest(`${companyUsersPath(companyId)}/${userId}`),
  create: (companyId, payload) => apiRequest(companyUsersPath(companyId), {
    method: 'POST', body: JSON.stringify(payload),
  }),
  update: (companyId, userId, payload) => apiRequest(`${companyUsersPath(companyId)}/${userId}`, {
    method: 'PUT', body: JSON.stringify(payload),
  }),
  setStatus: (companyId, userId, account_status) => apiRequest(`${companyUsersPath(companyId)}/${userId}/status`, {
    method: 'PATCH', body: JSON.stringify({ account_status }),
  }),
  delete: (companyId, userId) => apiRequest(`${companyUsersPath(companyId)}/${userId}`, {
    method: 'DELETE',
  }),
}
