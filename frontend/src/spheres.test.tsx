import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

import { App } from './App'
import { SectionsPage } from './pages/Sections'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn(async (path: string, _init?: RequestInit): Promise<unknown> => {
  if (path === '/profile/spheres') return { hidden_spheres: [] as string[] }
  throw new Error(`Unexpected API path ${path}`)
}) }))
vi.mock('./api', async importOriginal => ({ ...await importOriginal<typeof import('./api')>(), api: apiMock }))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'user-1', email: 'one@example.com', name: null, timezone: 'Asia/Almaty' } }) }))

test('six spheres open their own content path instead of task filters', async () => {
  apiMock.mockClear()
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/sections']}><Routes><Route path="/sections" element={<SectionsPage />} /><Route path="/health" element={<h1>Здоровье открыто</h1>} /></Routes></MemoryRouter>
  </QueryClientProvider>)
  await waitFor(() => expect(screen.getByRole('link', { name: /Здоровье/ })).toBeInTheDocument())
  expect(screen.getByRole('link', { name: /Здоровье/ })).toHaveAttribute('href', '/health')
  expect(screen.getByRole('link', { name: /Финансы/ })).toHaveAttribute('href', '/finance')
  for (const name of ['Обучение', 'Профессия', 'Языки', 'Финансы', 'Личное']) {
    expect(screen.getByText(name)).toBeInTheDocument()
  }
  expect(screen.queryByRole('link', { name: /Задачи/ })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Обучение/ })).toHaveAttribute('href', '/education')
  expect(screen.getByRole('link', { name: /Личное/ })).toHaveAttribute('href', '/personal')
})

test('health sphere contains sport and nutrition paths', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/health']}><App /></MemoryRouter>
  </QueryClientProvider>)
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Здоровье' })).toBeInTheDocument())
  expect(screen.getByRole('link', { name: /Спорт/ })).toHaveAttribute('href', '/health/sport')
  expect(screen.getByRole('link', { name: /Питание/ })).toHaveAttribute('href', '/health/nutrition')
})

test('sections offer direct continuation into saved plans and reading', async () => {
  apiMock.mockImplementation(async (path: string) => {
    if (path === '/profile/spheres') return { hidden_spheres: [] }
    if (path === '/health/sport/plan') return { plan: { id: 'sport-1', program: { title: 'Сила дома' } } }
    if (path === '/study/state/java?history_offset=0') return { active_plan: { id: 'java-1' }, next_lesson_id: 'java-lesson-2' }
    if (path === '/study/state/english?history_offset=0') return { active_plan: { id: 'english-1' }, next_lesson_id: 'en-lesson-2' }
    if (path === '/study/state/java-backend?history_offset=0') return { active_plan: null, next_lesson_id: null }
    if (path === '/reading/books?status=reading&limit=100') return { items: [], total: 0 }
    throw new Error(`Unexpected API path ${path}`)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><SectionsPage /></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByRole('link', { name: 'Продолжить: Сила дома' })).toHaveAttribute('href', '/health/sport?plan=sport-1')
  await waitFor(() => expect(screen.getAllByRole('link', { name: 'Продолжить урок' })).toHaveLength(2))
  expect(screen.getByRole('link', { name: /Финансы/ })).toHaveAttribute('href', '/finance')
  expect(screen.queryByRole('link', { name: 'Открыть расходы' })).not.toBeInTheDocument()
})

test('hiding an unused sphere removes its card without touching tasks', async () => {
  apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/profile/spheres') return init?.method === 'PATCH' ? { hidden_spheres: ['finance'] } : { hidden_spheres: [] }
    throw new Error(`Unexpected API path ${path}`)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><SectionsPage /></MemoryRouter>
  </QueryClientProvider>)
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Финансы' })).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: 'Настроить разделы' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Финансы' }))
  await waitFor(() => expect(screen.queryByRole('heading', { name: 'Финансы' })).not.toBeInTheDocument())
})
