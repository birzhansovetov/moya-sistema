import { fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

import { AnalyticsPanel } from './AnalyticsPanel'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(), api: apiMock }))
vi.mock('../auth', () => ({ useAuth: () => ({ user: { id: 'person-1' } }) }))

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><AnalyticsPanel today="2026-10-14" /></MemoryRouter>
  </QueryClientProvider>)
}

const emptyAreas = { health: 0, education: 0, profession: 0, languages: 0, finance: 0, personal: 0 }
const emptyWeeks = ['2026-09-20', '2026-09-27', '2026-10-04', '2026-10-11'].map(end => ({
  end, active_days: 0, workouts_logged: 0, tasks: { planned: 0, completed: 0 }, areas: emptyAreas, training: null,
}))

afterEach(() => { apiMock.mockReset(); localStorage.clear() })

test('empty analytics explains that no activity is recorded without showing misleading ratios', async () => {
  apiMock.mockResolvedValue({ start: '2026-09-14', end: '2026-10-11', weeks: emptyWeeks,
    summary: { active_days: 0, workouts_logged: 0, tasks: { planned: 0, completed: 0 }, areas: emptyAreas } })
  show()
  expect(await screen.findByRole('heading', { name: 'Аналитика за 4 недели' })).toBeInTheDocument()
  expect(await screen.findByText('Пока нет записанных действий за этот период.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Открыть разделы' })).toHaveAttribute('href', '/sections')
  expect(screen.queryByRole('list', { name: 'Активность по неделям' })).not.toBeInTheDocument()
  expect(screen.queryByText('0/0')).not.toBeInTheDocument()
})

test('analytics shows real four-week trends and retains the training review inside details', async () => {
  const weeks = emptyWeeks.map((week, index) => ({ ...week,
    active_days: index === 3 ? 2 : 0, workouts_logged: index === 3 ? 1 : 0,
    tasks: index === 3 ? { planned: 3, completed: 2 } : week.tasks,
    areas: index === 3 ? { ...emptyAreas, health: 1, education: 2 } : emptyAreas,
    training: index === 3 ? { plan_title: 'Домашний план' } : null,
  }))
  apiMock.mockImplementation((path: string) => path.startsWith('/calendar/analytics')
    ? Promise.resolve({ start: '2026-09-14', end: '2026-10-11', weeks,
      summary: { active_days: 2, workouts_logged: 1, tasks: { planned: 3, completed: 2 },
        areas: { ...emptyAreas, health: 1, education: 2 } } })
    : Promise.resolve({ start: '2026-10-05', end: '2026-10-11', tasks: { planned: 3, completed: 2 },
      areas: { ...emptyAreas, health: 1, education: 2 }, training: {
        plan_title: 'Домашний план', planned: 2, completed: 1, average_difficulty: 7,
        suggestion: 'keep', reason: 'Записана одна тренировка.' } }))
  show()
  expect(await screen.findByText('2 активных дня')).toBeInTheDocument()
  expect(screen.getByText('1 тренировка записана')).toBeInTheDocument()
  expect(screen.getByText('2 из 3 задач выполнено')).toBeInTheDocument()
  const trend = screen.getByRole('list', { name: 'Активность по неделям' })
  expect(within(trend).getAllByRole('listitem')).toHaveLength(4)
  expect(screen.getByRole('link', { name: 'Книги 2' })).toHaveAttribute('href', '/books')
  fireEvent.click(screen.getByText('Разбор последней недели'))
  expect(await screen.findByText('Домашний план')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Слишком сложно' })).toBeInTheDocument()
})
