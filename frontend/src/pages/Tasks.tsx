import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth'
import { TaskForm } from '../components/TaskForm'
import { TaskDetails } from '../components/TaskDetails'
import { TaskDialog } from '../components/TaskDialog'
import { OccurrenceList } from '../components/OccurrenceList'
import { useCalendar, useTasks, useUpdateTask } from '../taskHooks'
import { dateOffset, displayDate, sectionNames, type Task } from '../taskTypes'
import { useLocalToday } from '../useLocalToday'

type View = 'list' | 'today' | 'week' | 'board'

export function TasksPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const [showForm, setShowForm] = useState(params.has('new'))
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const opener = useRef<HTMLElement | null>(null)
  const [error, setError] = useState('')
  const view = (['list', 'today', 'week', 'board'].includes(params.get('view') || '') ? params.get('view') : 'list') as View
  const section = params.get('section')
  const today = useLocalToday(user?.timezone || 'Asia/Almaty')
  const monday = dateOffset(today, -((new Date(`${today}T12:00:00Z`).getUTCDay() + 6) % 7))
  const start = view === 'week' ? monday : today
  const end = view === 'week' ? dateOffset(monday, 6) : today
  const calendar = useCalendar(start, end)
  const tasks = useTasks()
  const update = useUpdateTask()
  const queryClient = useQueryClient()
  const filteredTasks = (tasks.data?.items || []).filter(task => !section || task.section === section)
  const selectedTask = (tasks.data?.items || []).find(task => task.id === selectedId)
  const occurrences = (calendar.data?.items || []).filter(task => !task.historical && (!section || task.section === section))
  function switchView(next: View) { const nextParams = new URLSearchParams(params); nextParams.set('view', next); nextParams.delete('new'); setParams(nextParams) }
  function saveSuccess() { setShowForm(false); const nextParams = new URLSearchParams(params); nextParams.delete('new'); setParams(nextParams); void queryClient.invalidateQueries({ queryKey: ['tasks'] }); void queryClient.invalidateQueries({ queryKey: ['calendar'] }) }
  return <div>
    <div className="pageHeader"><div><h1>Задачи</h1>{section && section in sectionNames && <p>{sectionNames[section as keyof typeof sectionNames]}</p>}</div><button className="primaryButton" onClick={event => { opener.current = event.currentTarget; setShowForm(true) }}>Новая задача</button></div>
    {showForm && <TaskDialog label="Создание задачи" returnFocusTo={opener.current} onClose={() => setShowForm(false)}><TaskForm defaultDate={params.get('date') || ''} onSaved={saveSuccess} onCancel={() => setShowForm(false)} /></TaskDialog>}
    {selectedTask && <TaskDialog label={`Редактирование задачи ${selectedTask.title}`} returnFocusTo={opener.current} onClose={() => setSelectedId(null)}><TaskDetails task={selectedTask} onChanged={() => { void queryClient.invalidateQueries({ queryKey: ['tasks'] }); void queryClient.invalidateQueries({ queryKey: ['calendar'] }) }} onClose={() => setSelectedId(null)} /></TaskDialog>}
    <div className="tabBar" role="tablist" aria-label="Вид задач">{([['list', 'Список'], ['today', 'Сегодня'], ['week', 'Неделя'], ['board', 'Доска']] as [View, string][]).map(([value, label]) => <button role="tab" aria-selected={view === value} className={view === value ? 'selectedTab' : ''} key={value} onClick={() => switchView(value)}>{label}</button>)}</div>
    <section className="card taskArea">
      {['today', 'week'].includes(view) ? calendar.isLoading ? <p className="muted">Загружаем задачи…</p> : calendar.isError ? <p role="alert" className="errorMessage">Не удалось загрузить задачи. <button className="textButton" onClick={() => void calendar.refetch()}>Повторить</button></p> : <OccurrenceList items={occurrences} showDate={view === 'week'} />
        : tasks.isLoading ? <p className="muted">Загружаем задачи…</p> : tasks.isError ? <p role="alert" className="errorMessage">Не удалось загрузить задачи. <button className="textButton" onClick={() => void tasks.refetch()}>Повторить</button></p>
        : filteredTasks.length === 0 ? <div className="emptyState"><div className="emptyIcon">☑</div><h3>Пока нет задач</h3><p>Создайте первую задачу, чтобы начать планирование.</p></div>
        : view === 'board' ? <div className="boardGrid">{([['todo', 'К выполнению'], ['in_progress', 'В работе'], ['done', 'Готово']] as [Task['status'], string][]).map(([value, label]) => <div className="boardColumn" key={value}><h3>{label} <span>{filteredTasks.filter(task => task.status === value).length}</span></h3>{filteredTasks.filter(task => task.status === value).map(task => <article className="boardCard" key={task.id}><span className="eyebrow">{sectionNames[task.section]}</span><h4>{task.title}</h4>{task.due_date && <small>{displayDate(task.due_date)}</small>}<button type="button" className="textButton" onClick={event => { opener.current = event.currentTarget; setSelectedId(task.id) }}>Открыть задачу</button><select aria-label={`Статус: ${task.title}`} value={task.status} disabled={update.isPending} onChange={event => { setError(''); update.mutate({ id: task.id, changes: { status: event.target.value as Task['status'] } }, { onError: cause => setError(cause instanceof Error ? cause.message : 'Не удалось обновить задачу') }) }}><option value="todo">К выполнению</option><option value="in_progress">В работе</option>{task.recurrence === 'none' && <option value="done">Готово</option>}</select></article>)}</div>)}</div>
        : <div className="taskList">{filteredTasks.map(task => <article className="taskRow" key={task.id}><div className="taskRowMain"><strong>{task.title}</strong><span>{sectionNames[task.section]}{task.due_date ? ` · ${displayDate(task.due_date)}` : ' · Без даты'}{task.recurrence !== 'none' ? ' · Повторяется' : ''}</span>{task.description && <p>{task.description}</p>}{task.subtasks.length > 0 && <small>Подзадачи: {task.subtasks.filter(item => item.completed).length}/{task.subtasks.length}</small>}</div><div className="taskRowActions"><span className={`statusBadge status-${task.status}`}>{task.status === 'todo' ? 'К выполнению' : task.status === 'in_progress' ? 'В работе' : 'Готово'}</span><button type="button" className="textButton" onClick={event => { opener.current = event.currentTarget; setSelectedId(task.id) }}>Изменить</button></div></article>)}</div>}
      {error && <p role="alert" className="errorMessage">{error}</p>}
    </section>
  </div>
}
