import { afterEach, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import { TodayPage } from './pages/Today'
import { TasksPage } from './pages/Tasks'
import type { Occurrence } from './taskTypes'

vi.mock('./components/HealthDay', () => ({ HealthDay: () => null }))

vi.mock('./auth', () => ({
  useAuth: () => ({ user: { id: 'person', email: 'person@example.com', name: null, timezone: 'UTC' } }),
}))

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

function renderToday(occurrences: Occurrence[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/calendar/streak') return new Response(JSON.stringify({ today: '2026-10-06', current_streak: 2, today_active: false, days: [
      { date: '2026-10-04', active: true }, { date: '2026-10-05', active: true }, { date: '2026-10-06', active: false },
    ] }))
    if (url.pathname === '/api/tasks') return new Response(JSON.stringify({ items: [] }))
    if (url.pathname === '/api/calendar') {
      const start = url.searchParams.get('start') || ''
      const end = url.searchParams.get('end') || ''
      return new Response(JSON.stringify({ items: occurrences.filter(item => item.date >= start && item.date <= end), today: '2026-10-06' }))
    }
    if (url.pathname.endsWith('/complete') && init?.method === 'POST') return new Response(JSON.stringify({ completed: true }))
    throw new Error(`Unexpected request: ${url.pathname}`)
  }))
  render(<QueryClientProvider client={client}><MemoryRouter><TodayPage /></MemoryRouter></QueryClientProvider>)
  fireEvent.change(screen.getByLabelText('Дата'), { target: { value: '2026-10-06' } })
  return client
}

test('rescheduled completion stays in history but is not counted as a planned task', async () => {
  renderToday([
    { task_id: 'old', title: 'Перенесённая задача', date: '2026-10-06', completed: true, historical: true, priority: 'medium', section: 'personal', status: 'todo' },
    { task_id: 'new', title: 'Новая дата', date: '2026-10-07', completed: false, historical: false, priority: 'medium', section: 'personal', status: 'todo' },
  ])
  await waitFor(() => expect(within(screen.getByText('На дату').closest('section')!).getByText('0')).toBeInTheDocument())
  expect(await screen.findByLabelText('Серия активных дней')).toHaveTextContent('2 дня подряд')
  expect(within(screen.getByText('Выполнено').closest('section')!).getByText('0')).toBeInTheDocument()
  expect(within(screen.getByText('Неделя').closest('section')!).getByText('0/1')).toBeInTheDocument()
  expect(screen.getByText('На этот период задач нет')).toBeInTheDocument()
})

test('today task view excludes historical completions from the current plan', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/calendar/streak') return new Response(JSON.stringify({ today: '2026-10-06', current_streak: 0, today_active: false, days: [] }))
    if (url.pathname === '/api/tasks') return new Response(JSON.stringify({ items: [] }))
    if (url.pathname === '/api/calendar') {
      const day = url.searchParams.get('start') || ''
      return new Response(JSON.stringify({ items: [
        { task_id: 'old', title: 'Перенесённая задача', date: day, completed: true, historical: true, priority: 'medium', section: 'personal', status: 'todo' },
      ], today: day }))
    }
    throw new Error(`Unexpected request: ${url.pathname}`)
  }))
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/tasks?view=today']}><TasksPage /></MemoryRouter></QueryClientProvider>)
  await waitFor(() => expect(screen.getByText('На этот период задач нет')).toBeInTheDocument())
  expect(screen.queryByText('Перенесённая задача')).not.toBeInTheDocument()
})

test('completion changes progress only after the server confirms it', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  let completed = false
  let confirm!: () => void
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/calendar/streak') return new Response(JSON.stringify({ today: '2026-10-06', current_streak: completed ? 1 : 0, today_active: completed, days: [] }))
    if (url.pathname === '/api/tasks') return new Response(JSON.stringify({ items: [] }))
    if (url.pathname === '/api/calendar') {
      const start = url.searchParams.get('start') || ''
      const end = url.searchParams.get('end') || ''
      const items = start <= '2026-10-06' && end >= '2026-10-06' ? [
        { task_id: 'walk', title: 'Прогулка', date: '2026-10-06', completed, historical: false, priority: 'medium', section: 'personal', status: 'todo' },
      ] : []
      return new Response(JSON.stringify({ items, today: '2026-10-06' }))
    }
    if (url.pathname === '/api/tasks/walk/occurrences/2026-10-06/complete' && init?.method === 'POST') {
      await new Promise<void>(resolve => { confirm = resolve })
      completed = true
      return new Response(JSON.stringify({ completed: true }))
    }
    throw new Error(`Unexpected request: ${url.pathname}`)
  }))
  render(<QueryClientProvider client={client}><MemoryRouter><TodayPage /></MemoryRouter></QueryClientProvider>)
  fireEvent.change(screen.getByLabelText('Дата'), { target: { value: '2026-10-06' } })
  const checkbox = await screen.findByRole('checkbox', { name: 'Выполнить: Прогулка, 6 октября' })
  expect(checkbox).not.toBeChecked()
  fireEvent.click(checkbox)
  await waitFor(() => expect(confirm).toBeTypeOf('function'))
  expect(checkbox).not.toBeChecked()
  expect(within(screen.getByText('Неделя').closest('section')!).getByText('0/1')).toBeInTheDocument()
  confirm()
  await waitFor(() => expect(checkbox).toBeChecked())
  expect(within(screen.getByText('Неделя').closest('section')!).getByText('1/1')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByLabelText('Серия активных дней')).toHaveTextContent('1 день подряд'))
})

test('today follows local midnight unless a different date was selected', async () => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-06T23:59:00Z'))
  renderToday([])
  expect(screen.getByLabelText('Дата')).toHaveValue('2026-10-06')
  vi.setSystemTime(new Date('2026-10-07T00:01:00Z'))
  fireEvent(window, new Event('focus'))
  await waitFor(() => expect(screen.getByLabelText('Дата')).toHaveValue('2026-10-07'))
  fireEvent.change(screen.getByLabelText('Дата'), { target: { value: '2026-10-06' } })
  vi.setSystemTime(new Date('2026-10-08T00:01:00Z'))
  fireEvent(window, new Event('focus'))
  expect(screen.getByLabelText('Дата')).toHaveValue('2026-10-06')
})

test('date controls move through adjacent days and preserve the chosen date', async () => {
  renderToday([])
  expect(screen.getByLabelText('Дата')).toHaveValue('2026-10-06')
  fireEvent.click(screen.getByRole('button', { name: 'Следующий день' }))
  expect(screen.getByLabelText('Дата')).toHaveValue('2026-10-07')
  expect(screen.getByRole('link', { name: '+ Новая задача' })).toHaveAttribute('href', '/tasks?new=1&date=2026-10-07')
  fireEvent.click(screen.getByRole('button', { name: 'Предыдущий день' }))
  expect(screen.getByLabelText('Дата')).toHaveValue('2026-10-06')
})
