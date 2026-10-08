// src/auth/AuthContext.jsx
import { useCallback, useEffect, useMemo, useState } from 'react'
import { authService } from '../services/authService'
import { AuthContext } from './authContext'

const TOKEN_KEY = 'gbms_access_token'

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(Boolean(sessionStorage.getItem(TOKEN_KEY)))

  useEffect(() => {
    if (!token) return
    let active = true
    authService.me(token).then((data) => {
      if (active) setUser(data)
    }).catch(() => {
      sessionStorage.removeItem(TOKEN_KEY)
      if (active) { setToken(null); setUser(null) }
    }).finally(() => { if (active) setIsLoading(false) })
    return () => { active = false }
  }, [token])

  const login = useCallback(async (credentials) => {
    const result = await authService.login(credentials)
    sessionStorage.setItem(TOKEN_KEY, result.access_token)
    setToken(result.access_token)
    setUser(result.user)
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(() => ({ token, user, isLoading, login, logout }), [token, user, isLoading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

