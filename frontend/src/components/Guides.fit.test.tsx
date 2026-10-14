import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { Guides } from './Guides'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(), api: apiMock }))
vi.mock('../auth', () => ({ useAuth: () => ({ user: { id: 'one' } }) }))

test('a finance guide can open another ready guide', async () => {
  apiMock.mockResolvedValue({ items: [
    { id: 'first', title: 'Учитывать расходы', intro: 'Первый', steps: [], example: '', check: [] },
    { id: 'second', title: 'Разбирать месяц', intro: 'Второй', steps: [], example: '', check: [] },
  ] })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><Guides area="finance" /></MemoryRouter></QueryClientProvider>)
  const first = (await screen.findByText('Учитывать расходы')).closest('details')!
  fireEvent.click(screen.getByText('Учитывать расходы', { selector: 'summary' }))
  fireEvent.click(screen.getByRole('button', { name: 'Мне не подходит: Учитывать расходы' }))
  fireEvent.click(screen.getByRole('button', { name: 'Разбирать месяц' }))
  expect(first).not.toHaveAttribute('open')
  expect(screen.getByText('Разбирать месяц', { selector: 'summary' }).closest('details')).toHaveAttribute('open')
})
