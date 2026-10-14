import { afterEach, expect, test, vi } from 'vitest'
import { ApiError, api, apiResponse, setAuthFailureHandler, setCsrfToken } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
  setAuthFailureHandler(null)
  setCsrfToken('')
})

test('expired refresh clears authenticated state through its handler', async () => {
  const failure = vi.fn()
  setAuthFailureHandler(failure)
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Сессия недействительна' }), { status: 401 }))
  vi.stubGlobal('fetch', fetchMock)
  await expect(api('/tasks')).rejects.toBeInstanceOf(ApiError)
  expect(fetchMock).toHaveBeenCalledTimes(2)
  expect(failure).toHaveBeenCalledOnce()
})

test('temporary refresh failure keeps authenticated state', async () => {
  const failure = vi.fn()
  setAuthFailureHandler(failure)
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(new Response(null, { status: 503 }))
  vi.stubGlobal('fetch', fetchMock)
  await expect(api('/tasks')).rejects.toMatchObject({ status: 503 })
  expect(failure).not.toHaveBeenCalled()
})

test('parallel expired requests use one refresh rotation', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.endsWith('/auth/refresh')) return new Response(JSON.stringify({ user: { id: 'a' }, csrf_token: 'new' }))
    const count = fetchMock.mock.calls.filter(call => String(call[0]).endsWith('/tasks')).length
    return count <= 2 ? new Response(null, { status: 401 }) : new Response(JSON.stringify({ items: [] }))
  })
  vi.stubGlobal('fetch', fetchMock)
  const responses = await Promise.all([api('/tasks'), api('/tasks')])
  expect(responses).toEqual([{ items: [] }, { items: [] }])
  expect(fetchMock.mock.calls.filter(call => String(call[0]).endsWith('/auth/refresh'))).toHaveLength(1)
})

test('binary upload keeps multipart boundary and CSRF token', async () => {
  setCsrfToken('csrf-123')
  const fetchMock = vi.fn().mockResolvedValue(new Response('encrypted', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  const form = new FormData()
  form.append('archive', new File(['cipher'], 'personal.moya-backup'))
  const response = await apiResponse('/profile/backup/preview', { method: 'POST', body: form })
  expect(await response.text()).toBe('encrypted')
  const init = fetchMock.mock.calls[0][1] as RequestInit
  expect(init.headers).toMatchObject({ 'X-CSRF-Token': 'csrf-123' })
  expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined()
})
