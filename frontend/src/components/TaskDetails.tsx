import { useEffect, useState, type FormEvent } from 'react'
import { api, json } from '../api'
import { sectionNames, type Section, type Task } from '../taskTypes'

export function TaskDetails({ task, onChanged, onClose }: { task: Task; onChanged: () => void; onClose: () => void }) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description)
  const [section, setSection] = useState<Section>(task.section)
  const [dueDate, setDueDate] = useState(task.due_date || '')
  const [priority, setPriority] = useState<Task['priority']>(task.priority)
  const [status, setStatus] = useState<Task['status']>(task.status)
  const [recurrence, setRecurrence] = useState<Task['recurrence']>(task.recurrence)
  const [weekdays, setWeekdays] = useState<number[]>(task.weekdays || [])
  const [newSubtask, setNewSubtask] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setTitle(task.title); setDescription(task.description); setSection(task.section)
    setDueDate(task.due_date || ''); setPriority(task.priority); setStatus(task.status)
    setRecurrence(task.recurrence); setWeekdays(task.weekdays || [])
  }, [task.id])

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const changes: Record<string, unknown> = {}
      if (title !== task.title) changes.title = title
      if (description !== task.description) changes.description = description
      if (section !== task.section) changes.section = section
      if ((dueDate || null) !== task.due_date) changes.due_date = dueDate || null
      if (priority !== task.priority) changes.priority = priority
      if (status !== task.status) changes.status = status
      if (recurrence !== task.recurrence) changes.recurrence = recurrence
      if (recurrence === 'weekdays' && JSON.stringify(weekdays) !== JSON.stringify(task.weekdays || [])) changes.weekdays = weekdays
      if (Object.keys(changes).length) await api(`/tasks/${task.id}`, json('PATCH', changes))
      onChanged(); onClose()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось сохранить задачу') }
    finally { setBusy(false) }
  }

  async function addSubtask(event: FormEvent) {
    event.preventDefault(); if (!newSubtask.trim()) return
    setBusy(true); setError('')
    try { await api(`/tasks/${task.id}/subtasks`, json('POST', { title: newSubtask })); setNewSubtask(''); onChanged() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось добавить подзадачу') }
    finally { setBusy(false) }
  }

  async function toggleSubtask(id: string, completed: boolean) {
    setBusy(true); setError('')
    try { await api(`/tasks/${task.id}/subtasks/${id}`, json('PATCH', { completed })); onChanged() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось обновить подзадачу') }
    finally { setBusy(false) }
  }

  async function removeSubtask(id: string) {
    setBusy(true); setError('')
    try { await api(`/tasks/${task.id}/subtasks/${id}`, { method: 'DELETE' }); onChanged() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось удалить подзадачу') }
    finally { setBusy(false) }
  }

  async function removeTask() {
    setBusy(true); setError('')
    try { await api(`/tasks/${task.id}`, { method: 'DELETE' }); onChanged(); onClose() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось удалить задачу') }
    finally { setBusy(false) }
  }

  return <section className="card taskFormCard" aria-label={`Редактирование задачи ${task.title}`}>
    <div className="formTitle"><h2>Редактировать задачу</h2><button type="button" className="iconButton" aria-label="Закрыть" onClick={onClose}>×</button></div>
    <form className="formStack" onSubmit={save}>
      <label>Название<input autoFocus required maxLength={160} value={title} onChange={event => setTitle(event.target.value)} /></label>
      <label>Описание<textarea rows={3} maxLength={5000} value={description} onChange={event => setDescription(event.target.value)} /></label>
      <div className="formGrid">
        <label>Раздел<select value={section} onChange={event => setSection(event.target.value as Section)}>{Object.entries(sectionNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Дата<input type="date" required={recurrence !== 'none'} value={dueDate} onChange={event => setDueDate(event.target.value)} /></label>
      </div>
      <div className="formGrid">
        <label>Приоритет<select value={priority} onChange={event => setPriority(event.target.value as Task['priority'])}><option value="low">Низкий</option><option value="medium">Обычный</option><option value="high">Высокий</option></select></label>
        <label>Статус<select value={status} onChange={event => setStatus(event.target.value as Task['status'])}><option value="todo">К выполнению</option><option value="in_progress">В работе</option>{recurrence === 'none' && <option value="done">Готово</option>}</select></label>
      </div>
      <label>Повторение<select value={recurrence} onChange={event => { const next = event.target.value as Task['recurrence']; setRecurrence(next); if (next !== 'none' && status === 'done') setStatus('todo') }}><option value="none">Не повторять</option><option value="daily">Каждый день</option><option value="weekly">Каждую неделю</option><option value="weekdays">Выбранные дни</option></select></label>
      {recurrence === 'weekdays' && <fieldset className="weekdayField"><legend>Дни недели</legend>{['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((label, index) => <label key={label}><input type="checkbox" checked={weekdays.includes(index)} onChange={event => setWeekdays(previous => event.target.checked ? [...previous, index].sort() : previous.filter(day => day !== index))} />{label}</label>)}</fieldset>}
      {error && <p role="alert" className="errorMessage">{error}</p>}
      <div className="formActions"><button type="button" className="secondaryButton" onClick={onClose}>Отмена</button><button className="primaryButton" disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить'}</button></div>
    </form>
    <div className="subtasksPanel"><h3>Подзадачи</h3>{task.subtasks.length === 0 && <p className="muted">Подзадач пока нет.</p>}
      {task.subtasks.map(item => <div className="subtaskRow" key={item.id}><input type="checkbox" aria-label={`Выполнить подзадачу: ${item.title}`} checked={item.completed} disabled={busy} onChange={() => void toggleSubtask(item.id, !item.completed)} /><span>{item.title}</span><button type="button" className="textButton" disabled={busy} onClick={() => void removeSubtask(item.id)} aria-label={`Удалить подзадачу: ${item.title}`}>Удалить</button></div>)}
      <form className="subtaskAdd" onSubmit={addSubtask}><input aria-label="Новая подзадача" maxLength={160} value={newSubtask} onChange={event => setNewSubtask(event.target.value)} placeholder="Новая подзадача" /><button type="submit" className="secondaryButton" disabled={busy || !newSubtask.trim()}>Добавить</button></form>
    </div>
    <div className="deletePanel">{confirmDelete ? <><p>Задача и её история выполнения будут удалены.</p><button type="button" className="dangerButton" disabled={busy} onClick={() => void removeTask()}>Да, удалить задачу</button><button type="button" className="textButton" onClick={() => setConfirmDelete(false)}>Отмена</button></> : <button type="button" className="textButton dangerText" onClick={() => setConfirmDelete(true)}>Удалить задачу</button>}</div>
  </section>
}
