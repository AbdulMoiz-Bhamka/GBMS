// src/services/authService.js
const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

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
    if (error instanceof TypeError) throw new Error('Cannot reach the GBMS server. Make sure FastAPI is running.', { cause: error })
    throw error
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : 'The request could not be completed.'
    const error = new Error(detail)
    error.status = response.status
    throw error
  }
  return body
}

export const authService = {
  login: (credentials) => request('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  me: (token) => request('/api/v1/auth/me', { token }),
  dashboard: (token) => request('/api/v1/dashboard', { token }),
}
