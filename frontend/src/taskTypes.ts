export type Section = 'personal' | 'sport' | 'nutrition' | 'education' | 'work' | 'finance' | 'other'
export type Task = {
  id: string; title: string; description: string; section: Section; due_date: string | null;
  priority: 'low' | 'medium' | 'high'; status: 'todo' | 'in_progress' | 'done';
  recurrence: 'none' | 'daily' | 'weekly' | 'weekdays'; weekdays: number[] | null;
  subtasks: { id: string; title: string; completed: boolean }[]
}
export type Occurrence = {
  task_id: string; title: string; date: string; completed: boolean; historical: boolean;
  priority: Task['priority']; section: Section; status: Task['status']
}
export type TaskList = { items: Task[] }
export type PersonalCalendarItem = {id:string; title:string; date:string; kind:'event'|'experiment'; completed:boolean}
export type CalendarList = { items: Occurrence[]; today: string; personal_items?: PersonalCalendarItem[] }

export const sectionNames: Record<Section, string> = {
  personal: 'Личное', sport: 'Спорт', nutrition: 'Питание', education: 'Обучение',
  work: 'Работа', finance: 'Финансы', other: 'Другое',
}

export function localDate(timezone: string, day = new Date()) {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(day)
}

export function dateOffset(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

export function displayDate(value: string) {
  return new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC', day: 'numeric', month: 'long' }).format(new Date(`${value}T12:00:00Z`))
}

export function taskCountLabel(count: number) {
  const lastTwo = count % 100
  const last = count % 10
  const word = lastTwo >= 11 && lastTwo <= 14 ? 'задач' : last === 1 ? 'задача' : last >= 2 && last <= 4 ? 'задачи' : 'задач'
  return `${count} ${word}`
}
