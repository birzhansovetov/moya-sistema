import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, json, setAuthFailureHandler, setCsrfToken, type AuthResult, type User } from './api'

type AuthContextValue = {
  user: User | null
  loading: boolean
  setAuthenticated: (result: AuthResult) => void
  setUser: (user: User) => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setAuthFailureHandler(() => { queryClient.clear(); setCsrfToken(''); setUser(null) })
    api<AuthResult>('/auth/me').then(result => {
      setCsrfToken(result.csrf_token)
      setUser(result.user)
    }).catch(() => undefined).finally(() => setLoading(false))
    return () => setAuthFailureHandler(null)
  }, [queryClient])

  function setAuthenticated(result: AuthResult) {
    queryClient.clear()
    setCsrfToken(result.csrf_token)
    setUser(result.user)
  }

  function updateUser(next: User) {
    if (user && user.id !== next.id) queryClient.clear()
    setUser(next)
  }

  async function logout() {
    await api<void>('/auth/logout', json('POST', {}))
    queryClient.clear()
    setCsrfToken('')
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, setAuthenticated, setUser: updateUser, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('AuthProvider is missing')
  return context
}
