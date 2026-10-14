import { afterEach, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { TaskDetails } from './components/TaskDetails'
import type { Task } from './taskTypes'

afterEach(() => vi.unstubAllGlobals())

const completedTask: Task = {
  id: 'walk', title: 'Прогулка', description: '', section: 'personal', due_date: '2026-10-06',
  priority: 'medium', status: 'done', recurrence: 'none', weekdays: null, subtasks: [],
}

test('moving a completed task does not resend unchanged done status', async () => {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ ...completedTask, due_date: '2026-10-07', status: 'todo' })))
  vi.stubGlobal('fetch', fetchMock)
  render(<TaskDetails task={completedTask} onChanged={() => undefined} onClose={() => undefined} />)
  fireEvent.change(screen.getByLabelText('Дата'), { target: { value: '2026-10-07' } })
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  const payload = JSON.parse(fetchMock.mock.calls[0]![1]!.body as string)
  expect(payload).toEqual({ due_date: '2026-10-07' })
})
