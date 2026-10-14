import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

import { WeeklyReview } from './WeeklyReview'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(), api: apiMock }))
vi.mock('../auth', () => ({ useAuth: () => ({ user: { id: 'person-1' } }) }))

afterEach(() => { localStorage.clear(); apiMock.mockReset() })

test('weekly review shows recorded sphere activity separately from task completion', async () => {
  apiMock.mockResolvedValue({ start: '2026-09-28', end: '2026-10-04', tasks: { planned: 3, completed: 1 },
    areas: { health: 2, education: 1, profession: 0, languages: 3, finance: 2, personal: 1 } })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><WeeklyReview today="2026-10-11" /></MemoryRouter>
  </QueryClientProvider>)
  expect(await screen.findByRole('heading', { name: 'Ваши последние 7 дней' })).toBeInTheDocument()
  expect(apiMock).toHaveBeenCalledWith('/calendar/weekly-review?end=2026-10-04')
  expect(await screen.findByText('1 из 3')).toBeInTheDocument()
  expect(screen.getByText('Здоровье').closest('li')).toHaveTextContent('2')
  expect(screen.getByText('Языки').closest('li')).toHaveTextContent('3')
  fireEvent.change(screen.getByLabelText('Что помешало выполнить часть отдельных задач?'), { target: { value: 'time' } })
  expect(screen.getByText('Попробуйте сократить дни или время занятий в анкете.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Уменьшить нагрузку' })).toHaveAttribute('href', '/onboarding')
  fireEvent.click(screen.getByRole('button', { name: 'План подходит' }))
  expect(screen.queryByRole('heading', { name: 'Ваши последние 7 дней' })).not.toBeInTheDocument()
})

test('weekly review explains a training suggestion and opens the relevant survey steps', async () => {
  apiMock.mockResolvedValue({ start: '2026-10-05', end: '2026-10-11', tasks: { planned: 0, completed: 0 },
    areas: { health: 1, education: 0, profession: 0, languages: 0, finance: 0, personal: 0 },
    training: { plan_title: 'Три тренировки', planned: 3, completed: 1, average_difficulty: 7,
      suggestion: 'review_frequency', suggested_days_per_week: 2, reason: 'За неделю записана 1 из 3 тренировок. Можно попробовать 2 занятия в неделю.' } })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><WeeklyReview today="2026-10-14" /></MemoryRouter>
  </QueryClientProvider>)
  expect(await screen.findByText('Три тренировки')).toBeInTheDocument()
  expect(screen.getByText('За неделю записана 1 из 3 тренировок. Можно попробовать 2 занятия в неделю.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Изменить частоту' })).toHaveAttribute('href', '/onboarding?focus=sport-schedule')
  expect(screen.getByRole('link', { name: 'Выбрать другую программу' })).toHaveAttribute('href', '/onboarding?focus=sport-program')
  expect(screen.getByRole('link', { name: 'Подобрать с учётом недели' })).toHaveAttribute('href', '/onboarding?focus=sport-program')
  expect(screen.getByText(/План изменится только после подтверждения в анкете/)).toBeInTheDocument()
})

test('training difficulty feedback saves for the week and remains editable', async () => {
  apiMock.mockImplementation((path: string) => path.startsWith('/calendar/weekly-review?')
    ? Promise.resolve({ start: '2026-10-05', end: '2026-10-11', tasks: { planned: 0, completed: 0 },
      areas: { health: 1, education: 0, profession: 0, languages: 0, finance: 0, personal: 0 },
      training: { plan_title: 'Две тренировки', planned: 2, completed: 2, average_difficulty: 5,
        suggestion: 'keep', reason: 'Текущий ритм можно сохранить.' } })
    : Promise.resolve({ rating: 'too_easy', week_end: '2026-10-11' }))
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><WeeklyReview today="2026-10-14" /></MemoryRouter>
  </QueryClientProvider>)
  fireEvent.click(await screen.findByRole('button', { name: 'Слишком легко' }))
  await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/calendar/weekly-review/feedback', {
    method: 'PUT', body: JSON.stringify({ end: '2026-10-11', rating: 'too_easy' }), headers: {},
  }))
  expect(await screen.findByText('Оценка сохранена для этой недели.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Слишком легко' })).toHaveAttribute('aria-pressed', 'true')
})

test('training feedback failure keeps the review open and reports the error', async () => {
  apiMock.mockImplementation((path: string) => path.startsWith('/calendar/weekly-review?')
    ? Promise.resolve({ start: '2026-10-05', end: '2026-10-11', tasks: { planned: 0, completed: 0 },
      areas: { health: 1, education: 0, profession: 0, languages: 0, finance: 0, personal: 0 },
      training: { plan_title: 'Две тренировки', planned: 2, completed: 2, average_difficulty: 5,
        suggestion: 'keep', reason: 'Текущий ритм можно сохранить.' } })
    : Promise.reject(new Error('Не удалось сохранить')))
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><WeeklyReview today="2026-10-14" /></MemoryRouter>
  </QueryClientProvider>)
  fireEvent.click(await screen.findByRole('button', { name: 'Слишком сложно' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось сохранить')
  expect(screen.getByRole('button', { name: 'Слишком сложно' })).toHaveAttribute('aria-pressed', 'false')
})

test('a previously dismissed generic review does not hide a newly active training plan', async () => {
  localStorage.setItem('moya-week-review:person-1:2026-10-11', 'kept')
  apiMock.mockResolvedValue({ start: '2026-10-05', end: '2026-10-11', tasks: { planned: 0, completed: 0 },
    areas: { health: 0, education: 0, profession: 0, languages: 0, finance: 0, personal: 0 },
    training: { plan_title: 'Новый план', planned: 2, completed: 0, average_difficulty: null,
      suggestion: 'keep', reason: 'Записей пока нет.' } })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><WeeklyReview today="2026-10-14" /></MemoryRouter>
  </QueryClientProvider>)
  expect(await screen.findByRole('button', { name: 'Слишком легко' })).toBeInTheDocument()
})
