import { afterEach, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { TaskForm } from './components/TaskForm'

afterEach(() => vi.unstubAllGlobals())

test('creating a task waits for the server response and ignores a second submit', async () => {
  let resolveSave!: (response: Response) => void
  const pendingSave = new Promise<Response>(resolve => { resolveSave = resolve })
  const fetchMock = vi.fn(() => pendingSave)
  vi.stubGlobal('fetch', fetchMock)
  const onSaved = vi.fn()
  render(<TaskForm onSaved={onSaved} onCancel={() => undefined} />)
  fireEvent.change(screen.getByLabelText('Название'), { target: { value: 'Прогулка' } })
  fireEvent.click(screen.getByRole('button', { name: 'Создать задачу' }))
  expect(screen.getByRole('button', { name: 'Сохраняем…' })).toBeDisabled()
  expect(onSaved).not.toHaveBeenCalled()
  expect(fetchMock).toHaveBeenCalledTimes(1)

  const task = { id: 'saved-task', title: 'Прогулка', description: '', section: 'personal', due_date: null, priority: 'medium', status: 'todo', recurrence: 'none', weekdays: null, subtasks: [] }
  resolveSave(new Response(JSON.stringify(task), { status: 201 }))
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(task))
  expect(fetchMock).toHaveBeenCalledTimes(1)
})
