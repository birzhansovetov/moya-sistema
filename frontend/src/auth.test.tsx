import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import { AuthPage } from './pages/Auth'
import { api } from './api'

vi.mock('./api', async importOriginal => ({
  ...await importOriginal<typeof import('./api')>(),
  api: vi.fn(async () => { throw new Error('Сеть недоступна. Повторите попытку.') }),
}))

test('failed sign-in keeps email and shows a retryable error', async () => {
  render(<MemoryRouter initialEntries={['/login']}><AuthPage onAuthenticated={() => undefined} /></MemoryRouter>)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'person@example.com' } })
  fireEvent.change(screen.getByLabelText('Пароль'), { target: { value: 'long password here' } })
  fireEvent.click(screen.getByRole('button', { name: 'Войти' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Сеть недоступна'))
  expect(screen.getByLabelText('Email')).toHaveValue('person@example.com')
  expect(screen.getByRole('button', { name: 'Войти' })).toBeEnabled()
})

test('email owner chooses the password when opening the verification link', async () => {
  render(<MemoryRouter initialEntries={['/verify-email#token=mail-token']}><AuthPage onAuthenticated={() => undefined} /></MemoryRouter>)
  fireEvent.change(screen.getByLabelText('Пароль'), { target: { value: 'owner password value' } })
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить адрес' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/auth/verify', expect.objectContaining({
    method: 'POST', body: JSON.stringify({ token: 'mail-token', password: 'owner password value' }),
  })))
})
