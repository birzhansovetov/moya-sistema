import { afterEach, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { OnboardingPage } from './pages/Onboarding'

vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'person', timezone: 'Asia/Almaty' }, setUser: vi.fn() }) }))
afterEach(() => vi.unstubAllGlobals())

test('older survey answers require a fresh confirmation instead of silent conversion', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/onboarding') return new Response(JSON.stringify({ survey_version: 2, needs_reconfirmation: true,
      answers: { health: { sport: { goal: 'strength_gain', place: 'gym' } } } }))
    throw new Error(`Unexpected request: ${url.pathname}`)
  }))
  render(<MemoryRouter><OnboardingPage /></MemoryRouter>)
  expect(await screen.findByText(/Анкета была создана в прежней версии/)).toBeInTheDocument()
  expect(screen.getByRole('radio', { name: /Снизить вес/ })).toBeChecked()
})

test('survey asks in parts and sends selected goal to preview', async () => {
  let submitted: { health: { sport: { goal: string; place: string | null; equipment: string[] }; nutrition_goal: string; allergies: string[] } } | null = null
  let checkedSport: { goal: string; place: string } | null = null
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/onboarding' && !init?.method) return new Response(JSON.stringify({ answers: null }))
    if (url.pathname === '/api/health/sport/match') {
      const sport = JSON.parse(String(init?.body))
      checkedSport = sport
      return new Response(JSON.stringify(sport.goal === 'maintain'
        ? { program: null, reasons: ['Для выбранной цели готовой программы пока нет.'] }
        : { program: { title: 'Начальная программа' }, reasons: [] }))
    }
    if (url.pathname === '/api/onboarding/preview') { submitted = JSON.parse(String(init?.body)); return new Response(JSON.stringify({ areas: { health: { title: 'Здоровье', sport: { status: 'unavailable', reason: 'Для выбранной цели готовой программы пока нет.' } } } })) }
    throw new Error(`Unexpected request: ${url.pathname}`)
  }))
  render(<MemoryRouter><OnboardingPage /></MemoryRouter>)
  expect(screen.getByRole('heading', { name: 'Какая у вас цель?' })).toBeInTheDocument()
  expect(screen.getByText('Выберите место занятий на следующем шаге. Тогда покажем подходящую программу.')).toBeInTheDocument()
  expect(submitted).toBeNull()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Продолжить' })).toBeEnabled())
  fireEvent.click(screen.getByRole('radio', { name: /Поддерживать форму/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  expect(screen.getByRole('heading', { name: 'Где вам удобно заниматься?' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Продолжить' })).toBeDisabled()
  fireEvent.click(screen.getByRole('radio', { name: 'В зале' }))
  expect(screen.queryByText('Что есть под рукой')).not.toBeInTheDocument()
  expect(await screen.findByText('Для выбранной цели готовой программы пока нет.')).toBeInTheDocument()
  expect(checkedSport).toMatchObject({ goal: 'maintain', place: 'gym' })
  expect(checkedSport).not.toHaveProperty('health')
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  expect(screen.getByRole('heading', { name: 'Какой ритм тренировок вам подходит?' })).toBeInTheDocument()
  expect(screen.getByLabelText('Минут на тренировку')).toBeInTheDocument()
  expect(screen.queryByLabelText('Максимум минут на приготовление')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  expect(screen.getByRole('heading', { name: 'Какие рецепты вам подходят?' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Минут на тренировку')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Максимум минут на приготовление')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('radio', { name: /Набор массы/ }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Молоко' }))
  for (let index = 0; index < 7; index++) fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  expect(screen.getByRole('heading', { name: 'Что хотите развивать?' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Посмотреть подбор' }))
  await waitFor(() => expect(submitted).not.toBeNull())
  expect(submitted!.health.sport.goal).toBe('maintain')
  expect(submitted!.health.sport.place).toBe('gym')
  expect(submitted!.health.sport.equipment).toEqual(['machines'])
  expect(submitted!.health.nutrition_goal).toBe('gain')
  expect(submitted!.health.allergies).toEqual(['milk'])
  const health = screen.getByRole('heading', { name: 'Здоровье' }).closest('article')!
  expect(within(health).getByText('Для выбранной цели готовой программы пока нет.')).toBeInTheDocument()
  fireEvent.click(within(health).getByRole('button', { name: 'Изменить' }))
  expect(screen.getByRole('radio', { name: /Поддерживать форму/ })).toBeChecked()
})

test('a previously saved home value is not silently reused for a new recommendation', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/onboarding') return new Response(JSON.stringify({ answers: {
      health: { sport: { goal: 'fat_loss_muscle_focus', level: 'beginner', place: 'home', equipment: [], days_per_week: 2, minutes_per_session: 45, limitations: false, weekdays: [1, 4] }, vegetarian: false, max_cooking_minutes: 45 },
      education: { track: 'java', reading_genres: ['classic'], minutes: 30, weekdays: [0, 2, 4] },
      profession: { track: 'java-backend', minutes: 30, weekdays: [1, 3] },
      languages: { level: 'A2', goal: 'general', minutes: 30, weekdays: [0, 2, 4] },
      finance: { currency: 'KZT', focus: 'record' }, personal: { focus: 'journal' },
    } }))
    throw new Error(`Unexpected request: ${url.pathname}`)
  }))
  render(<MemoryRouter><OnboardingPage /></MemoryRouter>)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Продолжить' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  expect(await screen.findByRole('heading', { name: 'Где вам удобно заниматься?' })).toBeInTheDocument()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Продолжить' })).toBeDisabled())
  for (const place of ['Дома', 'На улице', 'В зале']) expect(screen.getByRole('radio', { name: place })).not.toBeChecked()
  fireEvent.click(screen.getByRole('radio', { name: 'Дома' }))
  expect(screen.getByText('Что есть под рукой')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('radio', { name: 'На улице' }))
  expect(screen.getByText('Что есть под рукой')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('radio', { name: 'В зале' }))
  expect(screen.queryByText('Что есть под рукой')).not.toBeInTheDocument()
})

test('weekly review links open the sport question without losing saved answers', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
    if (path === '/api/onboarding') return new Response(JSON.stringify({ answers: {
      health: { sport: { goal: 'fat_loss_muscle_focus', level: 'beginner', place: 'gym', equipment: ['machines'], days_per_week: 3, minutes_per_session: 60, limitations: false, weekdays: [1, 3, 5] }, vegetarian: false, max_cooking_minutes: 45, nutrition_goal: 'maintain', allergies: [] },
      education: { track: 'java', reading_genres: ['classic'], minutes: 30, weekdays: [0, 2, 4] },
      profession: { track: 'java-backend', minutes: 30, weekdays: [1, 3] },
      languages: { level: 'A2', goal: 'general', minutes: 30, weekdays: [0, 2, 4] },
      finance: { currency: 'KZT', focus: 'record' }, personal: { focus: 'journal' },
    } }))
    if (path === '/api/onboarding/preview') return new Response(JSON.stringify({ preview_id: 'focused',
      areas: Object.fromEntries(['health', 'education', 'profession', 'languages', 'finance', 'personal'].map(key => [key, { title: ({ health: 'Здоровье', education: 'Обучение', profession: 'Профессия', languages: 'Языки', finance: 'Финансы', personal: 'Личное' } as Record<string, string>)[key] }])),
      candidates_by_sphere: { health: [{ id: 'sport-a', title: 'Спорт', reason: 'Подходит' }], education: [{ id: 'java', title: 'Java', reason: 'Подходит' }] } }))
    if (path === '/api/onboarding/assist') return new Response(JSON.stringify({ source: 'local_ai', recommendations: {
      health: { id: 'sport-a', title: 'Спорт', reason: 'Подходит', why: 'Нагрузка на прошлой неделе была слишком лёгкой.', source: 'local_ai' },
      education: { id: 'java', title: 'Java', reason: 'Подходит', source: 'local_ai' },
    } }))
    throw new Error(`Unexpected request: ${path}`)
  }))
  render(<MemoryRouter initialEntries={['/onboarding?focus=sport-schedule']}><OnboardingPage /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: 'Какой ритм тренировок вам подходит?' })).toBeInTheDocument()
  expect(screen.getByLabelText('Минут на тренировку')).toHaveValue(60)
  expect(screen.getByRole('button', { name: 'Пн' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Посмотреть обновлённый план' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Посмотреть обновлённый план' }))
  expect(await screen.findByText('Пересматривается только спорт. Остальные планы сохранятся.')).toBeInTheDocument()
  expect(within(screen.getByRole('group', { name: 'Обучение' })).getByRole('checkbox', { name: 'Не создавать план' })).toBeChecked()
  expect(within(screen.getByRole('group', { name: 'Здоровье' })).getByRole('checkbox', { name: 'Не создавать план' })).not.toBeChecked()
  await screen.findByRole('button', { name: 'Выбрать предложение ИИ' })
  expect(screen.getByText(/Нагрузка на прошлой неделе была слишком лёгкой/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Выбрать предложение ИИ' }))
  expect(within(screen.getByRole('group', { name: 'Обучение' })).getByRole('checkbox', { name: 'Не создавать план' })).toBeChecked()
})

test('temporary sport check failure has a working retry without resetting answers', async () => {
  let attempts = 0
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
    if (path === '/api/onboarding') return new Response(JSON.stringify({ answers: null }))
    if (path === '/api/health/sport/match') {
      attempts += 1
      return attempts === 1 ? new Response(JSON.stringify({ detail: 'Временно недоступно' }), { status: 503 })
        : new Response(JSON.stringify({ program: { title: 'Программа для зала' }, reasons: [] }))
    }
    throw new Error(`Unexpected request: ${path}`)
  }))
  render(<MemoryRouter><OnboardingPage /></MemoryRouter>)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Продолжить' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  fireEvent.click(screen.getByRole('radio', { name: 'В зале' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Временно недоступно')
  fireEvent.click(screen.getByRole('button', { name: 'Проверить ещё раз' }))
  expect(await screen.findByText('Подходит: Программа для зала')).toBeInTheDocument()
  expect(screen.getByRole('radio', { name: 'В зале' })).toBeChecked()
  expect(attempts).toBe(2)
})

test('saved answers load failure is visible and recoverable before continuing', async () => {
  let attempts = 0
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
    if (path !== '/api/onboarding') throw new Error(`Unexpected request: ${path}`)
    attempts += 1
    return attempts === 1 ? new Response('Unavailable', { status: 503 }) : new Response(JSON.stringify({ answers: null }))
  }))
  render(<MemoryRouter><OnboardingPage /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить сохранённые ответы.')
  expect(screen.getByRole('button', { name: 'Продолжить' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Продолжить' })).toBeEnabled())
  expect(screen.queryByText('Не удалось загрузить сохранённые ответы.')).not.toBeInTheDocument()
})

test('shows the fourth saved choice and sends its ID with skipped spheres', async () => {
  let started: { selected: Record<string, string>; skipped: string[] } | null = null
  const options = [1, 2, 3, 4].map(number => ({ kind: 'sport', id: `plan-${number}`, version: 'v1', digest: 'a'.repeat(64), title: `Программа ${number}`, reason: 'Подходит по расписанию' }))
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), 'http://localhost').pathname
    if (path === '/api/onboarding' && !init?.method) return new Response(JSON.stringify({ answers: null }))
    if (path === '/api/health/sport/match') return new Response(JSON.stringify({ program: { title: 'Программа 1' }, reasons: [] }))
    if (path === '/api/onboarding/preview') return new Response(JSON.stringify({ preview_id: 'opaque', areas: { health: { title: 'Здоровье' }, education: { title: 'Обучение' } }, candidates_by_sphere: { health: options.slice(0, 3), education: [] }, candidate_counts: { health: 4, education: 0 } }))
    if (path === '/api/onboarding/preview/choices') return new Response(JSON.stringify({ candidates_by_sphere: { health: options, education: [] } }))
    if (path === '/api/onboarding/start') { started = JSON.parse(String(init?.body)); return new Response(JSON.stringify({ status: 'started' })) }
    if (path === '/api/auth/me') return new Response(JSON.stringify({ user: { id: 'person', timezone: 'Asia/Almaty' } }))
    throw new Error(`Unexpected request: ${path}`)
  }))
  render(<MemoryRouter><OnboardingPage /></MemoryRouter>)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Продолжить' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  fireEvent.click(screen.getByRole('radio', { name: 'В зале' }))
  for (let index = 0; index < 9; index++) fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  fireEvent.click(screen.getByRole('button', { name: 'Посмотреть подбор' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Показать весь список' }))
  fireEvent.click(await screen.findByRole('radio', { name: /Программа 4/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Начать' }))
  await waitFor(() => expect(started).not.toBeNull())
  expect(started!.selected.health).toBe('plan-4')
  expect(started!.skipped).toContain('education')
})

test('local AI suggestion is shown separately and applied only after a click', async () => {
  let started: { selected: Record<string, string> } | null = null
  const options = [1, 2].map(number => ({ kind: 'sport', id: `plan-${number}`, version: 'v1', digest: 'a'.repeat(64), title: `Программа ${number}`, reason: 'Подходит по расписанию' }))
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), 'http://localhost').pathname
    if (path === '/api/onboarding' && !init?.method) return new Response(JSON.stringify({ answers: null }))
    if (path === '/api/health/sport/match') return new Response(JSON.stringify({ program: { title: 'Программа 1' }, reasons: [] }))
    if (path === '/api/onboarding/preview') return new Response(JSON.stringify({ preview_id: 'opaque', areas: { health: { title: 'Здоровье' } }, candidates_by_sphere: { health: options }, candidate_counts: { health: 2 } }))
    if (path === '/api/onboarding/assist') return new Response(JSON.stringify({ source: 'local_ai', progress_considered: true, recommendations: { health: { id: 'plan-2', reason: 'Подходит по расписанию', source: 'local_ai' } } }))
    if (path === '/api/onboarding/start') { started = JSON.parse(String(init?.body)); return new Response(JSON.stringify({ status: 'started' })) }
    if (path === '/api/auth/me') return new Response(JSON.stringify({ user: { id: 'person', timezone: 'Asia/Almaty' } }))
    throw new Error(`Unexpected request: ${path}`)
  }))
  render(<MemoryRouter><OnboardingPage /></MemoryRouter>)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Продолжить' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  fireEvent.click(screen.getByRole('radio', { name: 'В зале' }))
  for (let index = 0; index < 9; index++) fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
  fireEvent.click(screen.getByRole('button', { name: 'Посмотреть подбор' }))
  expect(await screen.findByText('Локальный ИИ предлагает')).toBeInTheDocument()
  expect(screen.getByText('Учтены записанные тренировки и занятия за последнюю завершённую неделю.')).toBeInTheDocument()
  expect(screen.getByRole('radio', { name: /Программа 1/ })).toBeChecked()
  fireEvent.click(screen.getByRole('button', { name: 'Выбрать предложение ИИ' }))
  expect(screen.getByRole('radio', { name: /Программа 2/ })).toBeChecked()
  fireEvent.click(screen.getByRole('button', { name: 'Начать' }))
  await waitFor(() => expect(started?.selected.health).toBe('plan-2'))
})
