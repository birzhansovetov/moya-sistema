import { act, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { AuthProvider, useAuth } from './auth'
import { App } from './App'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })
function renderApp(path: string) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter></QueryClientProvider>)
}
test('sign-in is available while the session request is still pending', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
  renderApp('/login')
  expect(screen.getByRole('heading', { name: 'С возвращением' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Войти' })).toBeEnabled()
})
test('a stalled session check ends with a retry and can recover', async () => {
  vi.useFakeTimers()
  const fetchMock = vi.fn().mockImplementationOnce(() => new Promise(() => {})).mockResolvedValue(new Response('{}', {status:401}))
  vi.stubGlobal('fetch', fetchMock)
  renderApp('/sections')
  await act(async () => { await vi.advanceTimersByTimeAsync(10001) })
  expect(screen.getByRole('alert')).toHaveTextContent('Сервер не ответил')
  fireEvent.click(screen.getByRole('button', {name:'Повторить загрузку'}))
  await act(async () => {})
  expect(screen.getByRole('heading', {name:'С возвращением'})).toBeVisible()
})
test('a late session response cannot overwrite a successful sign-in', async () => {
  let resolveSession!: (value: Response) => void
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { resolveSession = resolve })))
  function SignInProbe() {
    const auth = useAuth()
    return <><button onClick={() => auth.setAuthenticated({user:{id:'new',email:'new@example.com',name:null,timezone:'UTC'},csrf_token:'new'})}>Sign in</button><span>{auth.user?.id}</span></>
  }
  render(<QueryClientProvider client={new QueryClient()}><AuthProvider><SignInProbe /></AuthProvider></QueryClientProvider>)
  fireEvent.click(screen.getByText('Sign in'))
  await act(async () => { resolveSession(new Response(JSON.stringify({user:{id:'old'},csrf_token:'old'}))) })
  expect(screen.getByText('new')).toBeVisible()
})
