export type User = { id: string; email: string; name: string | null; timezone: string; onboarding_complete?: boolean }
export type AuthResult = { user: User; csrf_token: string }

let csrfToken = ''
export function setCsrfToken(value: string) { csrfToken = value }
let authFailureHandler: (() => void) | null = null
export function setAuthFailureHandler(handler: (() => void) | null) { authFailureHandler = handler }
let refreshPromise: Promise<AuthResult> | null = null

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

async function requestResponse(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: {
        ...(init.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...(csrfToken && init.method && !['GET', 'HEAD'].includes(init.method) ? { 'X-CSRF-Token': csrfToken } : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new Error('Сеть недоступна. Проверьте подключение и повторите попытку.')
  }
  if (!response.ok) {
    let detail = ''
    try {
      const body = await response.json() as { detail?: string | Array<{ loc?: Array<string | number>; msg: string }> }
      detail = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map(item => `${item.loc?.slice(1).join('.') || 'Данные'}: ${item.msg}`).join('; ') : ''
    } catch { /* no response body */ }
    throw new ApiError(detail || `Не удалось выполнить запрос (${response.status}). Попробуйте ещё раз.`, response.status)
  }
  return response
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await requestResponse(path, init)
  return response.status === 204 ? undefined as T : await response.json() as T
}

export async function apiResponse(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await requestResponse(path, init)
  } catch (error) {
    if (init.signal?.aborted) throw error
    if (error instanceof ApiError && error.status === 401 && path !== '/auth/refresh' && path !== '/auth/login') {
      try {
        if (!refreshPromise) {
          refreshPromise = request<AuthResult>('/auth/refresh', { method: 'POST', signal: init.signal }).finally(() => { refreshPromise = null })
        }
        const renewed = await refreshPromise
        if (init.signal?.aborted) throw new Error('Запрос отменён.')
        setCsrfToken(renewed.csrf_token)
        return await requestResponse(path, init)
      } catch (refreshError) {
        if (init.signal?.aborted) throw refreshError
        if (refreshError instanceof ApiError && refreshError.status === 401) {
          setCsrfToken('')
          authFailureHandler?.()
        }
        throw refreshError
      }
    }
    throw error
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiResponse(path, init)
  return response.status === 204 ? undefined as T : await response.json() as T
}

export function json(method: string, body: unknown, headers: HeadersInit = {}): RequestInit {
  return { method, body: JSON.stringify(body), headers }
}
