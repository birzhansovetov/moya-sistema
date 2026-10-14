import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { EducationPage } from './pages/Education'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn(async (path: string) => {
  if (path === '/study/catalog') return { items: [
    { id: 'java', lesson_count: 14 }, { id: 'go', lesson_count: 32 },
  ] }
  if (path.startsWith('/study/state/')) return { plan: null, active_plan: null, completed: [] }
  if (path.startsWith('/reading/books')) return { items: [], total: 0 }
  throw new Error(path)
}) }))
vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), api: apiMock }))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'one' } }) }))

test('education course cards show current catalog lesson counts', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><EducationPage /></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByText(/6 глав · 32 занятий/)).toBeInTheDocument()
  expect(screen.getByText(/Основы · 14 занятий/)).toBeInTheDocument()
})
