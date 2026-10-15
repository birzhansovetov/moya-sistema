import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { LanguagesPage } from './pages/Languages'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), api: apiMock }))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'test', timezone: 'Asia/Almaty' } }) }))

test('offers five language routes and continues the saved course', async () => {
  apiMock.mockImplementation(async (path: string) => path.includes('/study/state/kazakh')
    ? { active_plan: { id: 'plan-kz', level: 'B1' }, next_lesson_id: 'kk-b1-01', completed: ['kk-a1-01'] }
    : { active_plan: null, next_lesson_id: null, completed: [] })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><LanguagesPage /></MemoryRouter></QueryClientProvider>)
  for (const title of ['Английский', 'Казахский', 'Корейский', 'Турецкий', 'Испанский'])
    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
  const continueLink = await screen.findByRole('link', { name: 'Продолжить' })
  expect(continueLink).toHaveAttribute('href', '/languages/kazakh?plan=plan-kz&lesson=kk-b1-01')
  expect(screen.getAllByRole('link', { name: 'Посмотреть курс' })).toHaveLength(4)
})
