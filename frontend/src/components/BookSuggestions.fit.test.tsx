import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { BookSuggestions } from './BookSuggestions'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(), api: apiMock }))
vi.mock('../auth', () => ({ useAuth: () => ({ user: { id: 'one', onboarding_complete: false } }) }))

test('unsuitable book offers another book from the same interest', async () => {
  apiMock.mockImplementation(async (path: string) => path === '/library/books' ? { items: [
    { id: 'first', title: 'Книга А', author: 'Автор', interest: 'growth', genres: ['self_development'], description: 'Первое описание', questions: [], check: '', source: '', available_offline: true },
    { id: 'second', title: 'Книга Б', author: 'Автор', interest: 'growth', genres: ['self_development'], description: 'Второе описание', questions: [], check: '', source: '', available_offline: true },
  ] } : { paragraphs: ['Текст книги'], total: 1, next_offset: null })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><BookSuggestions onChoose={vi.fn()} /></MemoryRouter></QueryClientProvider>)
  await screen.findByRole('heading',{name:'Книга А'})
  fireEvent.click(screen.getByRole('button', { name: 'Мне не подходит: Книга А' }))
  fireEvent.click(screen.getByRole('button', { name: 'Книга Б' }))
  expect(await screen.findByRole('region', { name: 'Чтение Книга Б' })).toBeInTheDocument()
})
