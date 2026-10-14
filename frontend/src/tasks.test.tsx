import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import { TaskForm } from './components/TaskForm'

const { submit } = vi.hoisted(() => ({ submit: vi.fn(async (..._args: unknown[]) => { throw new Error('Сеть недоступна. Повторите попытку.') }) }))
vi.mock('./api', async importOriginal => ({ ...await importOriginal<typeof import('./api')>(), api: submit }))

test('failed task save keeps the draft and allows retry', async () => {
  submit.mockClear()
  render(<TaskForm onSaved={() => undefined} onCancel={() => undefined} />)
  fireEvent.change(screen.getByLabelText('Название'), { target: { value: 'Пробежка утром' } })
  fireEvent.click(screen.getByRole('button', { name: 'Создать задачу' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Сеть недоступна'))
  expect(screen.getByLabelText('Название')).toHaveValue('Пробежка утром')
  expect(screen.getByRole('button', { name: 'Создать задачу' })).toBeEnabled()
  expect(submit).toHaveBeenCalledTimes(1)
})

test('retry uses the same key only while the task draft is unchanged', async () => {
  submit.mockClear()
  render(<TaskForm onSaved={() => undefined} onCancel={() => undefined} />)
  fireEvent.change(screen.getByLabelText('Название'), { target: { value: 'Пробежка утром' } })
  fireEvent.click(screen.getByRole('button', { name: 'Создать задачу' }))
  await waitFor(() => expect(submit).toHaveBeenCalledTimes(1))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Создать задачу' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Создать задачу' }))
  await waitFor(() => expect(submit).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Создать задачу' })).toBeEnabled())
  fireEvent.change(screen.getByLabelText('Название'), { target: { value: 'Ходьба утром' } })
  fireEvent.click(screen.getByRole('button', { name: 'Создать задачу' }))
  await waitFor(() => expect(submit).toHaveBeenCalledTimes(3))
  const key = (index: number) => (submit.mock.calls[index][1] as RequestInit).headers as Record<string, string>
  expect(key(0)['Idempotency-Key']).toBe(key(1)['Idempotency-Key'])
  expect(key(2)['Idempotency-Key']).not.toBe(key(1)['Idempotency-Key'])
})
