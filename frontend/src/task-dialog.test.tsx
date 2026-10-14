import { afterEach, expect, test, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { TasksPage } from './pages/Tasks'

vi.mock('./auth', () => ({
  useAuth: () => ({ user: { id: 'person', email: 'person@example.com', name: null, timezone: 'UTC' } }),
}))

afterEach(() => vi.unstubAllGlobals())

test('task form opens as a modal dialog for keyboard navigation', () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ items: [] }))))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/tasks']}><TasksPage /></MemoryRouter></QueryClientProvider>)
  fireEvent.click(screen.getByRole('button', { name: 'Новая задача' }))
  expect(screen.getByRole('dialog', { name: 'Создание задачи' })).toBeInTheDocument()
  expect(screen.getByLabelText('Название')).toHaveFocus()
})
