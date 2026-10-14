import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from './api'
import { useAuth } from './auth'
import type { CalendarList, Task, TaskList } from './taskTypes'

export type ActivityStreak = {
  today: string
  current_streak: number
  today_active: boolean
  days: { date: string; active: boolean }[]
}

export function useActivityStreak(today: string) {
  const { user } = useAuth()
  return useQuery({ queryKey: ['activity-streak', user?.id, today], queryFn: () => api<ActivityStreak>('/calendar/streak'), enabled: !!user })
}

export function useTasks() {
  const { user } = useAuth()
  return useQuery({ queryKey: ['tasks', user?.id], queryFn: () => api<TaskList>('/tasks'), enabled: !!user })
}

export function useCalendar(start: string, end: string) {
  const { user } = useAuth()
  return useQuery({ queryKey: ['calendar', user?.id, start, end], queryFn: () => api<CalendarList>(`/calendar?start=${start}&end=${end}`), enabled: !!user })
}

export function useComplete() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, date, completed }: { taskId: string; date: string; completed: boolean }) =>
      api(`/tasks/${taskId}/occurrences/${date}/complete`, json('POST', { completed })),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['calendar'] }); void client.invalidateQueries({ queryKey: ['tasks'] }); void client.invalidateQueries({ queryKey: ['activity-streak'] }) },
  })
}

export function useUpdateTask() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: Partial<Task> }) => api<Task>(`/tasks/${id}`, json('PATCH', changes)),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['tasks'] }); void client.invalidateQueries({ queryKey: ['calendar'] }) },
  })
}
