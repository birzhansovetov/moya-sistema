import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError, api, json, setAuthFailureHandler, setCsrfToken, type AuthResult, type User } from './api'

type AuthContextValue = {
  user: User | null
  loading: boolean
  sessionError: string
  retrySession: () => void
  setAuthenticated: (result: AuthResult) => void
  setUser: (user: User) => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [sessionError, setSessionError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const generation = useRef(0)
  const sessionController = useRef<AbortController | null>(null)

  useEffect(() => {
    setAuthFailureHandler(() => { queryClient.clear(); setCsrfToken(''); setUser(null) })
    const current = ++generation.current
    const controller = new AbortController()
    sessionController.current = controller
    setLoading(true)
    setSessionError('')
    let timer: ReturnType<typeof setTimeout>
    const deadline = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        reject(new Error('Сервер не ответил вовремя. Повторите загрузку.'))
        controller.abort()
      }, 10_000)
    })
    Promise.race([api<AuthResult>('/auth/me', { signal: controller.signal }), deadline]).then(result => {
      if (generation.current !== current) return
      setCsrfToken(result.csrf_token)
      setUser(result.user)
    }).catch(error => {
      if (generation.current !== current) return
      if (!(error instanceof ApiError && error.status === 401)) {
        setSessionError(error instanceof Error ? error.message : 'Не удалось проверить сессию. Повторите загрузку.')
      }
    }).finally(() => {
      clearTimeout(timer)
      if (generation.current === current) setLoading(false)
    })
    return () => {
      ++generation.current
      clearTimeout(timer)
      controller.abort()
      setAuthFailureHandler(null)
    }
  }, [queryClient, attempt])

  function setAuthenticated(result: AuthResult) {
    ++generation.current
    sessionController.current?.abort()
    queryClient.clear()
    setCsrfToken(result.csrf_token)
    setUser(result.user)
    setLoading(false)
    setSessionError('')
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

  return <AuthContext.Provider value={{ user, loading, sessionError, retrySession: () => setAttempt(value => value + 1), setAuthenticated, setUser: updateUser, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('AuthProvider is missing')
  return context
}
