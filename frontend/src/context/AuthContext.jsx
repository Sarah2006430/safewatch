import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from '../lib/api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!getToken())

  useEffect(() => {
    if (!getToken()) return
    api('/api/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const onLogout = () => setUser(null)
    window.addEventListener('auth:logout', onLogout)
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [])

  const login = useCallback(async (username, password) => {
    const res = await api('/api/auth/login', { method: 'POST', body: { username, password } })
    setToken(res.access_token)
    setUser(res.user)
    return res.user
  }, [])

  const signup = useCallback(async (full_name, email, password) => {
    const res = await api('/api/auth/signup', { method: 'POST', body: { full_name, email, password } })
    setToken(res.access_token)
    setUser(res.user)
    return res.user
  }, [])

  const logout = useCallback(async () => {
    try { await api('/api/auth/logout', { method: 'POST' }) } catch { /* token may already be invalid */ }
    setToken(null)
    setUser(null)
  }, [])

  const isStaff = user && (user.role === 'admin' || user.role === 'operator')

  return <AuthCtx.Provider value={{ user, loading, login, signup, logout, isStaff }}>{children}</AuthCtx.Provider>
}

export const useAuth = () => useContext(AuthCtx)
