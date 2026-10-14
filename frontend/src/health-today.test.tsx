import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import { TodayPage } from './pages/Today'
import { HealthDay } from './components/HealthDay'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), api: apiMock }))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'one', timezone: 'Asia/Almaty' } }) }))
vi.mock('./useLocalToday', () => ({ useLocalToday: () => '2026-10-06' }))
vi.mock('./taskHooks', async original => ({ ...await original<typeof import('./taskHooks')>(), useCalendar: () => ({ data: { items: [] }, isLoading: false, isError: false }), useTasks: () => ({ data: { items: [] }, isLoading: false, isError: false }) }))

test('my day shows sport and a recipe link while task counts remain zero', async () => {
  apiMock.mockReset().mockImplementation(async (path: string) => {
    if (path === '/health/sport/plan') return { plan: { id: 'sport-1', started_on: '2026-10-05', answers: { weekdays: [2, 5], days_per_week: 2 }, program: { sessions: [{ id: 'A', title: 'Дом A' }, { id: 'B', title: 'Дом B' }] } } }
    if (path === '/health/sport/workouts') return { items: [{ id: 'old-log', plan_id: 'old-plan', date: '2026-10-06', session_id: 'A' }] }
    throw new Error(`Unexpected ${path}`)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><TodayPage /></MemoryRouter></QueryClientProvider>)
  expect(screen.getByText('Моя аналитика за 4 недели').closest('details')).not.toHaveAttribute('open')
  await screen.findByRole('heading', { name: 'Дом A', level: 2 })
  expect(screen.getByRole('link', { name: 'Открыть материал' })).toHaveAttribute('href', '/health/sport?plan=sport-1&date=2026-10-06&session=A#sport-sessions')
  fireEvent.click(screen.getByText('Все планы и записи на дату'))
  expect(screen.queryByText('Овсяная каша')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Открыть тренировку/ })).toHaveAttribute('href', '/health/sport?plan=sport-1&date=2026-10-06&session=A#workout-journal')
  expect(screen.getByRole('link', { name: /Рецепты с граммами/ })).toHaveAttribute('href', '/health/nutrition')
  expect(screen.getByRole('heading', { name: 'Задачи на сегодня' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Добавить задачу' })).toHaveAttribute('href', '/tasks?new=1&date=2026-10-06')
  await waitFor(() => expect(screen.queryByText('1 запланировано задач')).not.toBeInTheDocument())
})

test('an old plan workout cannot complete a replacement plan on the same date', () => {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } })
  client.setQueryData(['sport-plan', 'one'], { plan: { id: 'new-plan', started_on: '2026-10-06', answers: { weekdays: [2, 5], days_per_week: 2 }, program: { sessions: [{ id: 'A', title: 'Новая тренировка' }] } } })
  client.setQueryData(['sport-workouts', 'one'], { items: [{ id: 'old-log', plan_id: 'old-plan', date: '2026-10-06', session_id: 'A' }] })
  render(<QueryClientProvider client={client}><MemoryRouter><HealthDay date="2026-10-06" /></MemoryRouter></QueryClientProvider>)
  expect(screen.queryByText('Тренировка записана в спортивном журнале.')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Открыть тренировку/ })).toBeInTheDocument()
})
