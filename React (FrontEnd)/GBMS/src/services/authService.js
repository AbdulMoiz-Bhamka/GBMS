// src/services/authService.js
const API_BASE = (import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? '' : 'http://127.0.0.1:8000')).replace(/\/$/, '')
const TOKEN_KEY = 'gbms_access_token'

async function request(path, { token, ...options } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    })
  } catch (error) {
    if (error instanceof TypeError) throw new Error('Cannot reach FastAPI at http://127.0.0.1:8000. Start the backend and check the Vite proxy.', { cause: error })
    throw error
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = typeof body.detail === 'string'
      ? body.detail
      : Array.isArray(body.detail)
        ? body.detail.map((item) => item.msg).filter(Boolean).join(' ')
        : 'The request could not be completed.'
    const error = new Error(detail)
    error.status = response.status
    throw error
  }
  return body
}

export function apiRequest(path, options = {}) {
  const token = options.token ?? sessionStorage.getItem(TOKEN_KEY)
  return request(path, { ...options, token })
}

export const authService = {
  login: (credentials) => request('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  me: (token) => request('/api/v1/auth/me', { token }),
  dashboard: (token) => request('/api/v1/dashboard', { token }),
}
