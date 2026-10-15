import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { TodayNext } from './TodayNext'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(), api: apiMock }))
vi.mock('../auth', () => ({ useAuth: () => ({ user: { id: 'user-1' } }) }))

test('nearest planned workout is shown before study and links to the exact session', async () => {
  apiMock.mockImplementation(async (path: string) => {
    if (path === '/health/sport/plan') return { plan: { id: 'plan-1', started_on: '2026-10-05', answers: { weekdays: [1] }, program: { duration_weeks: 4, sessions: [{ id: 'session-1', title: 'Силовая дома' }] } } }
    if (path === '/health/sport/workouts') return { items: [] }
    if (path === '/study/day?date=2026-10-12') return { items: [{ course_id: 'java', course_title: 'Java', plan_id: 'study-1', lesson_id: 'lesson-1', title: 'Классы', minutes: 25 }] }
    if (path === '/reading/books?status=reading&limit=100') return { items: [], total: 0 }
    throw new Error(`Unexpected API path ${path}`)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><TodayNext date="2026-10-12" /></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByRole('heading', { name: 'Силовая дома' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Открыть материал' })).toHaveAttribute('href', '/health/sport?plan=plan-1&date=2026-10-12&session=session-1#sport-sessions')
  fireEvent.click(screen.getByText('На сегодня: 60 мин · изменить время'))
  fireEvent.click(screen.getByRole('button', { name: '90 мин' }))
  fireEvent.click(screen.getByText('Следом ещё 1'))
  expect(screen.getByRole('link', { name: 'Java: Классы · 25 мин' })).toHaveAttribute('href', '/profession/java?plan=study-1&lesson=lesson-1&date=2026-10-12')
})
