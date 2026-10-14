import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import { SportPage } from './pages/Sport'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), api: (path: string, init?: RequestInit) => path === '/library/guides?area=sport' ? Promise.resolve({ items: [] }) : apiMock(path, init) }))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'user-1', timezone: 'Asia/Almaty' } }) }))
vi.mock('./useLocalToday', () => ({ useLocalToday: () => '2026-10-06' }))

const program = { id: 'fat_loss_home_beginner_v1', title: 'Сила и ходьба дома', overview: 'Две тренировки в неделю.', duration_weeks: 4, progression: ['Неделя 1: техника'], sources: ['https://www.nhs.uk/live-well/exercise/strength-exercises/'], sessions: [{ id: 'A', title: 'Дом A', warmup: 'Ходьба', cooldown: 'Замедлите шаг', work: [{ exercise_id: 'chair_squat', sets: 2, reps: '8–12', rest_seconds: 75, note: 'Стул' }] }] }
const exercise = { chair_squat: { name: 'Приседание до стула', technique: 'Коснитесь сиденья и встаньте.', common_errors: 'Не падайте на стул.', easier_version: 'Помогайте руками.', substitution: 'Неглубокий присед.', source: 'https://www.nhs.uk/live-well/exercise/strength-exercises/' } }
const answers = { goal: 'fat_loss_muscle_focus', level: 'beginner', place: 'home', equipment: [], days_per_week: 2, minutes_per_session: 35, limitations: false, weekdays: [1, 4] }

function mount(entry = '/health/sport') {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[entry]}><SportPage /></MemoryRouter></QueryClientProvider>)
}

test('sport page explains how to use the supplied beginner training references', async () => {
  apiMock.mockReset().mockImplementation(async (path: string) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [program], exercises: exercise }
    if (path === '/health/sport/plan') return { plan: null }
    if (path === '/health/sport/workouts') return { items: [] }
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  await screen.findByRole('heading', { name: 'Спорт' })
  expect(screen.getByText(/Библиотека упражнений/).closest('details')).not.toHaveAttribute('open')
  expect(screen.getByRole('link', { name: /Статья GoodLooker о фулбоди/ })).toHaveAttribute('href', 'https://goodlooker.ru/silovaya-programma-muzchiny-fullbody.html')
  expect(screen.getByText(/Пятидневную схему автоматически/)).toBeInTheDocument()
})

test('questionnaire chooses a prepared plan and keeps answers after failed save', async () => {
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [program], exercises: exercise }
    if (path === '/health/sport/plan' && !init) return { plan: null }
    if (path === '/health/sport/workouts') return { items: [] }
    if (path === '/health/sport/match') return { program, sessions: program.sessions, reasons: [], version: '1' }
    if (path === '/health/sport/plan' && init?.method === 'PUT') throw new Error('Сохранение недоступно')
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  await screen.findByRole('heading', { name: 'Спорт' })
  fireEvent.change(screen.getByLabelText('Место тренировки'), { target: { value: 'home' } })
  fireEvent.click(screen.getByRole('button', { name: 'Подобрать программу' }))
  await screen.findByText('Сила и ходьба дома')
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить план' }))
  await screen.findByRole('alert')
  expect(screen.getByRole('alert')).toHaveTextContent('Сохранение недоступно')
  expect(screen.getByLabelText('Место тренировки')).toHaveValue('home')
  expect(screen.getByText('Сила и ходьба дома')).toBeInTheDocument()
  const request = apiMock.mock.calls.find(([path, init]) => path === '/health/sport/match' && init)
  expect(JSON.parse(request?.[1]?.body as string)).toMatchObject(answers)
})

test('questionnaire offers four days and a home barbell', async () => {
  apiMock.mockReset().mockImplementation(async (path: string) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [program], exercises: exercise }
    if (path === '/health/sport/plan') return { plan: null }
    if (path === '/health/sport/workouts') return { items: [] }
    if (path === '/health/sport/match') return { program: null, sessions: [], reasons: ['Нет программы'], version: '1' }
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  await screen.findByRole('heading', { name: 'Спорт' })
  expect(screen.getByText(/Если приседания к стулу и отжимания от стены уже лёгкие/)).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Занятий в неделю'), { target: { value: '4' } })
  fireEvent.click(screen.getByLabelText('Штанга'))
  expect(screen.getByLabelText('Штанга')).toBeChecked()
  fireEvent.click(screen.getByRole('button', { name: 'Подобрать программу' }))
  await waitFor(() => {
    const request = apiMock.mock.calls.find(([path, init]) => path === '/health/sport/match' && init)
    expect(JSON.parse(request?.[1]?.body as string)).toMatchObject({ days_per_week: 4, weekdays: [1, 2, 4, 6], equipment: ['barbell'] })
  })
})

test('saved plan shows sessions, exercise instructions and history', async () => {
  apiMock.mockReset().mockImplementation(async (path: string) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [program], exercises: exercise }
    if (path === '/health/sport/plan') return { plan: { id: 'plan-1', answers, program, started_on: '2026-10-06', content_version: '1' } }
    if (path === '/health/sport/workouts') return { items: [{ id: 'log-1', date: '2026-10-06', session_id: 'A', difficulty: 5, note: 'Хорошо' }] }
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  await screen.findByRole('heading', { name: 'Приседание до стула' })
  await waitFor(() => expect(screen.getByText('Изменить программу').closest('details')).not.toHaveAttribute('open'))
  fireEvent.click(screen.getByRole('button', { name: 'Мне не подходит: Сила и ходьба дома' }))
  fireEvent.click(screen.getByRole('button', { name: 'Изменить условия подбора' }))
  expect(screen.getByText('Изменить программу').closest('details')).toHaveAttribute('open')
  fireEvent.click(screen.getByRole('button', { name: 'Записать тренировку' }))
  expect(screen.getByText('Записать тренировку', { selector: 'summary' }).closest('details')).toHaveAttribute('open')
  expect(screen.getByText('История тренировок').closest('details')).not.toHaveAttribute('open')
  expect(screen.getAllByText('Коснитесь сиденья и встаньте.').length).toBeGreaterThan(0)
  expect(screen.getByText('Неделя 1: техника')).toBeInTheDocument()
  expect(screen.getByText(/Хорошо/)).toBeInTheDocument()
  await waitFor(() => expect(screen.getByText('Сила и ходьба дома')).toBeInTheDocument())
})

test('workout progress is saved as a draft and restored without completing the session', async () => {
  let savedDraft: { actual: Record<string, { sets: number; reps: string[]; weight: string }>; difficulty: number; note: string } | null = null
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [program], exercises: exercise }
    if (path === '/health/sport/plan') return { plan: { id: 'plan-1', answers, program, started_on: '2026-10-06', content_version: '1' } }
    if (path === '/health/sport/workouts') return { items: [] }
    if (path.startsWith('/health/sport/draft?')) return { draft: savedDraft }
    if (path === '/health/sport/draft' && init?.method === 'PUT') {
      savedDraft = JSON.parse(init.body as string)
      return { draft: savedDraft }
    }
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  fireEvent.click(await screen.findByText('Дом A', { selector: 'summary' }))
  fireEvent.click(screen.getByRole('button', { name: 'Начать это занятие' }))
  const reps = await screen.findByLabelText('Приседание до стула — подход 1 (повторения)')
  fireEvent.change(reps, { target: { value: '10' } })
  await waitFor(() => expect(savedDraft?.actual.chair_squat.reps[0]).toBe('10'), { timeout: 2500 })
  expect(apiMock.mock.calls.some(([path, init]) => path === '/health/sport/workouts' && init?.method === 'POST')).toBe(false)
  cleanup()
  mount()
  fireEvent.click(await screen.findByRole('button', { name: 'Записать тренировку' }))
  expect(await screen.findByLabelText('Приседание до стула — подход 1 (повторения)')).toHaveValue(10)
})

test('guided workout shows one exercise at a time and resumes at the first unfinished exercise', async () => {
  const guided = { ...program, sessions: [{ ...program.sessions[0], work: [program.sessions[0].work[0], { exercise_id: 'walk', sets: 1, reps: '10 минут', rest_seconds: 30, note: 'Ровный темп' }] }] }
  const guides = { ...exercise, walk: { ...exercise.chair_squat, name: 'Быстрая ходьба' } }
  let savedDraft: unknown = null
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [guided], exercises: guides }
    if (path === '/health/sport/plan') return { plan: { id: 'plan-1', answers, program: guided, started_on: '2026-10-06', content_version: '1' } }
    if (path === '/health/sport/workouts') return { items: [] }
    if (path.startsWith('/health/sport/draft?')) return { draft: savedDraft }
    if (path === '/health/sport/draft' && init?.method === 'PUT') { savedDraft = JSON.parse(init.body as string); return { draft: savedDraft } }
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  fireEvent.click(await screen.findByRole('button', { name: 'Записать тренировку' }))
  expect(await screen.findByText('Упражнение 1 из 2')).toBeInTheDocument()
  expect(screen.getByLabelText('Приседание до стула — подход 1 (повторения)')).toBeInTheDocument()
  expect(screen.queryByLabelText('Быстрая ходьба — подход 1 (повторения)')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Приседание до стула — подход 1 (повторения)'), { target: { value: '10' } })
  fireEvent.change(screen.getByLabelText('Приседание до стула — подход 2 (повторения)'), { target: { value: '9' } })
  fireEvent.click(screen.getByRole('button', { name: 'Следующее упражнение' }))
  expect(screen.getByLabelText('Быстрая ходьба — подход 1 (повторения)')).toBeInTheDocument()
  expect(screen.getByText('Отдых: 01:15')).toBeInTheDocument()
  await waitFor(() => expect(savedDraft).not.toBeNull(), { timeout: 2500 })
  cleanup()
  mount()
  fireEvent.click(await screen.findByRole('button', { name: 'Записать тренировку' }))
  expect(await screen.findByText('Упражнение 2 из 2')).toBeInTheDocument()
})

test('rest can start after a completed set and be skipped without completing the workout',async()=>{
  apiMock.mockReset().mockImplementation(async(path:string,init?:RequestInit)=>{
    if(path==='/health/sport/catalog')return {version:'1',programs:[program],exercises:exercise}
    if(path==='/health/sport/plan')return {plan:{id:'plan-1',answers,program,started_on:'2026-10-06',content_version:'1'}}
    if(path==='/health/sport/workouts')return init?.method==='POST'?{id:'done'}:{items:[]}
    if(path.startsWith('/health/sport/draft?'))return {draft:null}
    if(path==='/health/sport/draft')return {draft:null}
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  fireEvent.click(await screen.findByRole('button',{name:'Записать тренировку'}))
  fireEvent.change(await screen.findByLabelText('Приседание до стула — подход 1 (повторения)'),{target:{value:'10'}})
  fireEvent.click(screen.getByRole('button',{name:'Начать отдых после подхода 1'}))
  expect(screen.getByRole('timer')).toHaveTextContent('01:15')
  fireEvent.click(screen.getByRole('button',{name:'Пропустить отдых'}))
  expect(screen.queryByRole('timer')).not.toBeInTheDocument()
  expect(apiMock.mock.calls.some(([path,init])=>path==='/health/sport/workouts'&&init?.method==='POST')).toBe(false)
  fireEvent.change(screen.getByLabelText('Приседание до стула — подход 2 (повторения)'),{target:{value:'9'}})
  fireEvent.click(screen.getByRole('button',{name:'Начать отдых после подхода 2'}))
  fireEvent.click(screen.getByRole('button',{name:'Завершить тренировку'}))
  await screen.findByText('Тренировка завершена и записана.')
  expect(screen.queryByRole('timer')).not.toBeInTheDocument()
})

test('eight-week home plan shows a dated training calendar and progression guidance', async () => {
  const fullProgram = { ...program, duration_weeks: 8, progression: Array.from({ length: 8 }, (_, index) => `Неделя ${index + 1}: прогресс`), sessions: [program.sessions[0], { ...program.sessions[0], id: 'B', title: 'Дом B' }] }
  apiMock.mockReset().mockImplementation(async (path: string) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [fullProgram], exercises: exercise }
    if (path === '/health/sport/plan') return { plan: { id: 'plan-1', answers, program: fullProgram, started_on: '2026-10-01', content_version: '1' } }
    if (path === '/health/sport/workouts') return { items: [] }
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  expect(await screen.findByRole('heading', { name: 'План по неделям' })).toBeInTheDocument()
  expect(screen.getByText('Неделя 2 из 8')).toBeInTheDocument()
  expect(screen.getByText(/Неделя 8: прогресс/)).toBeInTheDocument()
  expect(screen.getByText(/Запишите тренировки этой недели/)).toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('button', { name: 'Открыть занятие Дом A' })[0])
  expect(screen.getByText('Дом A', { selector: 'summary' }).closest('details')).toHaveAttribute('open')
})

test('unavailable new match stays separate from the saved plan', async () => {
  apiMock.mockReset().mockImplementation(async (path: string) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [program], exercises: exercise }
    if (path === '/health/sport/plan') return { plan: { id: 'plan-1', answers, program, started_on: '2026-10-06', content_version: '1' } }
    if (path === '/health/sport/workouts') return { items: [] }
    if (path === '/health/sport/match') return { program: null, sessions: [], reasons: ['Для среднего уровня программы пока нет.'], version: '1' }
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  await screen.findByRole('heading', { name: 'Сила и ходьба дома' })
  fireEvent.change(screen.getByLabelText('Уровень'), { target: { value: 'intermediate' } })
  fireEvent.click(screen.getByRole('button', { name: 'Подобрать программу' }))
  await screen.findByRole('heading', { name: 'Для этих условий программы пока нет' })
  expect(screen.getByText('Для среднего уровня программы пока нет.')).toBeInTheDocument()
  expect(screen.getByText(/Сейчас действует этот план/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Сила и ходьба дома' })).toBeInTheDocument()
})

test('workout journal saves distinct reps for each set and optional weight', async () => {
  let savedLog: unknown = null
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [program], exercises: exercise }
    if (path === '/health/sport/plan') return { plan: { id: 'plan-1', answers, program, started_on: '2026-10-06', content_version: '1' } }
    if (path === '/health/sport/workouts' && !init) return { items: savedLog ? [savedLog] : [] }
    if (path.startsWith('/health/sport/draft?')) return { draft: null }
    if (path === '/health/sport/workouts' && init?.method === 'POST') {
      savedLog = { id: 'log-2', program_title: 'Сила и ходьба дома', session_title: 'Дом A', ...JSON.parse(init.body as string) }
      return savedLog
    }
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  await screen.findByRole('heading', { name: 'Приседание до стула' })
  fireEvent.click(screen.getByRole('button', { name: 'Записать тренировку' }))
  await screen.findByLabelText('Приседание до стула — подход 1 (повторения)')
  fireEvent.change(screen.getByLabelText('Приседание до стула — подход 1 (повторения)'), { target: { value: '10' } })
  fireEvent.change(screen.getByLabelText('Приседание до стула — подход 2 (повторения)'), { target: { value: '8' } })
  fireEvent.change(screen.getByLabelText('Вес снаряда, кг: Приседание до стула (если был)'), { target: { value: '5' } })
  fireEvent.click(screen.getByRole('button', { name: 'Завершить тренировку' }))
  await waitFor(() => {
    const request = apiMock.mock.calls.find(([path, init]) => path === '/health/sport/workouts' && init?.method === 'POST')
    expect(request).toBeDefined()
    expect(JSON.parse(request?.[1]?.body as string).results).toEqual([
      { exercise_id: 'chair_squat', completed_sets: 2, reps_per_set: [10, 8], weight_kg: 5 },
    ])
  })
  await screen.findByText(/Подходы: 2 · повторения: 10, 8 · вес: 5 кг/)
  expect(screen.getByText(/Сила и ходьба дома · Дом A/)).toBeInTheDocument()
})

test('workout journal records a compatible exercise replacement separately from the planned exercise', async () => {
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health/sport/catalog') return { version: '1', programs: [program], exercises: { ...exercise, chair_squat: { ...exercise.chair_squat, alternatives: [{ exercise_id: 'bodyweight_squat', places: ['home'], required_equipment: [] }] }, bodyweight_squat: { ...exercise.chair_squat, name: 'Приседание без стула' } } }
    if (path === '/health/sport/plan') return { plan: { id: 'plan-1', answers, program, started_on: '2026-10-06', content_version: '1' } }
    if (path === '/health/sport/workouts' && !init) return { items: [] }
    if (path.startsWith('/health/sport/draft?')) return { draft: null }
    if (path === '/health/sport/workouts' && init?.method === 'POST') return { id: 'log-3', ...JSON.parse(init.body as string) }
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  await screen.findByRole('heading', { name: 'Приседание до стула' })
  fireEvent.click(screen.getByRole('button', { name: 'Записать тренировку' }))
  await screen.findByLabelText('Заменить упражнение: Приседание до стула')
  fireEvent.change(screen.getByLabelText('Заменить упражнение: Приседание до стула'), { target: { value: 'bodyweight_squat' } })
  fireEvent.change(screen.getByLabelText('Приседание до стула — подход 1 (повторения)'), { target: { value: '10' } })
  fireEvent.change(screen.getByLabelText('Приседание до стула — подход 2 (повторения)'), { target: { value: '10' } })
  fireEvent.click(screen.getByRole('button', { name: 'Завершить тренировку' }))
  await waitFor(() => {
    const request = apiMock.mock.calls.find(([path, init]) => path === '/health/sport/workouts' && init?.method === 'POST')
    expect(JSON.parse(request?.[1]?.body as string).results[0]).toMatchObject({ exercise_id: 'chair_squat', performed_exercise_id: 'bodyweight_squat' })
  })
})

test('direct workout action keeps the selected past date and session', async () => {
  const sessions = [program.sessions[0], { ...program.sessions[0], id: 'B', title: 'Дом B' }]
  apiMock.mockReset().mockImplementation(async (path: string) => {
    if (path.startsWith('/health/sport/draft?')) return { draft: null }
    if (path === '/health/sport/catalog') return { version: '1', programs: [program], exercises: exercise }
    if (path === '/health/sport/plan') return { plan: { id: 'plan-1', answers, program: { ...program, sessions }, started_on: '2026-10-01', content_version: '1' } }
    if (path === '/health/sport/workouts') return { items: [] }
    throw new Error(`Unexpected ${path}`)
  })
  mount('/health/sport?plan=plan-1&date=2026-10-01&session=B')
  await waitFor(() => expect(screen.getByLabelText('Занятие')).toHaveValue('B'))
  expect(screen.getByLabelText('Дата')).toHaveValue('2026-10-01')
  expect(screen.getByText('Дом B', { selector: 'summary' }).closest('details')).toHaveAttribute('open')
})
