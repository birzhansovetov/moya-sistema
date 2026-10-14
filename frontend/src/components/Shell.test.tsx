import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { Shell } from './Shell'

vi.mock('../auth', () => ({ useAuth: () => ({ user: { name: 'Тест', email: 'test@example.com' } }) }))

function mount(path: string) {
  render(<MemoryRouter initialEntries={[path]}><Routes><Route element={<Shell />}><Route path="/" element={<p>Сегодня</p>} /><Route path="/sections" element={<p>Разделы</p>} /><Route path="/health/sport" element={<p>Спорт</p>} /></Route></Routes></MemoryRouter>)
}

test('mobile shell keeps five primary destinations and a parent link on a detail page', () => {
  mount('/health/sport')
  const nav = screen.getByRole('navigation', { name: 'Мобильная навигация' })
  expect(within(nav).getAllByRole('link')).toHaveLength(5)
  expect(within(nav).getByRole('link', { name: 'Разделы' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('link', { name: 'Назад к здоровью' })).toHaveAttribute('href', '/health')
})
