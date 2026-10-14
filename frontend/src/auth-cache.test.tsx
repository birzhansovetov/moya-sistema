import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import { vi } from 'vitest'

import { AuthProvider, useAuth } from './auth'

vi.mock('./api', async importOriginal => ({
  ...await importOriginal<typeof import('./api')>(),
  api: vi.fn(async () => { throw new Error('No session') }),
}))

function Probe() {
  const { user, setAuthenticated } = useAuth()
  const client = useQueryClient()
  return <>
    <span>{user?.email || 'Нет аккаунта'}</span>
    <button onClick={() => setAuthenticated({ user: { id: 'a', email: 'a@example.com', name: null, timezone: 'Asia/Almaty' }, csrf_token: 'a' })}>Войти A</button>
    <button onClick={() => client.setQueryData(['tasks', 'a'], { items: [{ title: 'Личная запись A' }] })}>Сохранить кэш A</button>
    <button onClick={() => setAuthenticated({ user: { id: 'b', email: 'b@example.com', name: null, timezone: 'Asia/Almaty' }, csrf_token: 'b' })}>Войти B</button>
  </>
}

test('switching accounts clears previous private query data', async () => {
  const client = new QueryClient()
  render(<QueryClientProvider client={client}><AuthProvider><Probe /></AuthProvider></QueryClientProvider>)
  await waitFor(() => expect(screen.getByText('Нет аккаунта')).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: 'Войти A' }))
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить кэш A' }))
  expect(client.getQueryData(['tasks', 'a'])).toBeDefined()
  fireEvent.click(screen.getByRole('button', { name: 'Войти B' }))
  expect(screen.getByText('b@example.com')).toBeInTheDocument()
  expect(client.getQueryData(['tasks', 'a'])).toBeUndefined()
})
