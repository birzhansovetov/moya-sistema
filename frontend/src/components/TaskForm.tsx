import { useRef, useState, type FormEvent } from 'react'
import { api, json } from '../api'
import { sectionNames, type Section, type Task } from '../taskTypes'

const newKey = () => globalThis.crypto?.randomUUID?.() || `task-${Date.now()}-${Math.random()}`

export function TaskForm({ onSaved, onCancel, defaultDate = '' }: { onSaved: (task: Task) => void; onCancel: () => void; defaultDate?: string }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [section, setSection] = useState<Section>('personal')
  const [dueDate, setDueDate] = useState(defaultDate)
  const [priority, setPriority] = useState<'low' | 'medium' | 'high'>('medium')
  const [recurrence, setRecurrence] = useState<'none' | 'daily' | 'weekly' | 'weekdays'>('none')
  const [weekdays, setWeekdays] = useState<number[]>([])
  const [subtasks, setSubtasks] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const submission = useRef<{ body: string; key: string } | null>(null)
  const inFlight = useRef(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (inFlight.current) return
    inFlight.current = true; setSaving(true); setError('')
    try {
      const body = {
        title, description, section, due_date: dueDate || null, priority, recurrence,
        weekdays: recurrence === 'weekdays' ? weekdays : null,
        subtasks: subtasks.split('\n').map(value => value.trim()).filter(Boolean),
      }
      const serialized = JSON.stringify(body)
      if (submission.current?.body !== serialized) submission.current = { body: serialized, key: newKey() }
      const task = await api<Task>('/tasks', json('POST', body, { 'Idempotency-Key': submission.current.key }))
      onSaved(task)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось сохранить задачу. Повторите попытку.')
    } finally { inFlight.current = false; setSaving(false) }
  }

  return <section className="card taskFormCard" aria-label="Новая задача">
    <div className="formTitle"><h2>Новая задача</h2><button className="iconButton" type="button" onClick={onCancel} aria-label="Закрыть форму">×</button></div>
    <form className="formStack" onSubmit={submit}>
      <label>Название<input autoFocus required maxLength={160} value={title} onChange={event => setTitle(event.target.value)} placeholder="Например, сходить на тренировку" /></label>
      <label>Описание<textarea rows={3} maxLength={5000} value={description} onChange={event => setDescription(event.target.value)} placeholder="Детали задачи" /></label>
      <div className="formGrid">
        <label>Раздел<select value={section} onChange={event => setSection(event.target.value as Section)}>{Object.entries(sectionNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Дата<input type="date" required={recurrence !== 'none'} value={dueDate} onChange={event => setDueDate(event.target.value)} /></label>
      </div>
      <div className="formGrid">
        <label>Приоритет<select value={priority} onChange={event => setPriority(event.target.value as typeof priority)}><option value="low">Низкий</option><option value="medium">Обычный</option><option value="high">Высокий</option></select></label>
        <label>Повторение<select value={recurrence} onChange={event => setRecurrence(event.target.value as typeof recurrence)}><option value="none">Не повторять</option><option value="daily">Каждый день</option><option value="weekly">Каждую неделю</option><option value="weekdays">Выбранные дни</option></select></label>
      </div>
      {recurrence === 'weekdays' && <fieldset className="weekdayField"><legend>Дни недели</legend>{['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((label, index) => <label key={label}><input type="checkbox" checked={weekdays.includes(index)} onChange={event => setWeekdays(previous => event.target.checked ? [...previous, index].sort() : previous.filter(day => day !== index))} />{label}</label>)}</fieldset>}
      <label>Подзадачи <span className="labelHint">по одной на строке</span><textarea rows={3} value={subtasks} onChange={event => setSubtasks(event.target.value)} placeholder={'Подготовить вещи\nВыйти вовремя'} /></label>
      {error && <p role="alert" className="errorMessage">{error}</p>}
      <div className="formActions"><button type="button" className="secondaryButton" onClick={onCancel}>Отмена</button><button type="submit" className="primaryButton" disabled={saving}>{saving ? 'Сохраняем…' : 'Создать задачу'}</button></div>
    </form>
  </section>
}
