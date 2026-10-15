import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { SectionsPage } from './pages/Sections'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn(async (path: string) => {
  if (path === '/profile/spheres') return { hidden_spheres: [] }
  if (path === '/health/sport/plan') return { plan: null }
  if (path.startsWith('/study/state/')) return { active_plan: null, completed: [] }
  if (path.startsWith('/reading/books')) return { items: [] }
  throw new Error(path)
}) }))
vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), api: apiMock }))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'one' } }) }))

test('six readable sphere entrances keep their destination routes', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><SectionsPage /></MemoryRouter></QueryClientProvider>)
  for (const [name, route] of [['Здоровье', '/health'], ['Книги', '/books'], ['Профессия', '/profession'], ['Языки', '/languages'], ['Финансы', '/finance'], ['Личное', '/personal']]) {
    expect(await screen.findByRole('link', { name: new RegExp(name) })).toHaveAttribute('href', route)
  }
  expect(screen.queryAllByText(/СФЕРА 0[1-6]/)).toHaveLength(0)
})
