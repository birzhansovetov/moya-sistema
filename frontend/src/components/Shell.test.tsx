import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach } from 'vitest'
import { vi } from 'vitest'
import { Shell } from './Shell'

vi.mock('../auth', () => ({ useAuth: () => ({ user: { name: 'Тест', email: 'test@example.com' } }) }))

function mount(path: string) {
  render(<MemoryRouter initialEntries={[path]}><Routes><Route element={<Shell />}><Route path="*" element={<p>Содержимое</p>} /></Route></Routes></MemoryRouter>)
}

afterEach(() => { cleanup(); document.documentElement.removeAttribute('data-theme') })

test('mobile shell keeps four primary destinations and a parent link on a detail page', () => {
  mount('/health/sport')
  const nav = screen.getByRole('navigation', { name: 'Мобильная навигация' })
  expect(within(nav).getAllByRole('link')).toHaveLength(4)
  expect(within(nav).getByRole('link', { name: 'Разделы' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('link', { name: 'Назад к здоровью' })).toHaveAttribute('href', '/health')
})

test.each([
  ['/health/sport', 'sport'], ['/health/nutrition', 'nutrition'], ['/health/calories', 'calories'],
  ['/education/java', 'study-code'], ['/education/go', 'study-code'], ['/profession', 'profession'],
  ['/languages/kazakh', 'language'], ['/education/reading', 'reading'], ['/finance', 'finance'],
  ['/personal', 'personal'], ['/unknown', 'neutral'],
])('%s applies %s theme to the shell and document', (path, theme) => {
  mount(path)
  expect(screen.getByRole('main').closest('[data-theme]')).toHaveAttribute('data-theme', theme)
  expect(document.documentElement).toHaveAttribute('data-theme', theme)
})
