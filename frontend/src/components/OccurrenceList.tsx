import { useState } from 'react'
import { useComplete } from '../taskHooks'
import { displayDate, sectionNames, type Occurrence } from '../taskTypes'

export function OccurrenceList({ items, showDate = false }: { items: Occurrence[]; showDate?: boolean }) {
  const complete = useComplete()
  const [error, setError] = useState('')
  if (items.length === 0) return <div className="emptyState"><div className="emptyIcon">✓</div><h3>На этот период задач нет</h3><p>Добавьте задачу с датой, и она появится здесь.</p></div>
  return <div className="occurrenceList">
    {error && <p role="alert" className="errorMessage">{error}</p>}
    {items.map(item => <div className={`occurrenceRow ${item.completed ? 'completedRow' : ''}`} key={`${item.task_id}-${item.date}`}>
      <input aria-label={`Выполнить: ${item.title}, ${displayDate(item.date)}`} type="checkbox" checked={item.completed} disabled={complete.isPending} onChange={() => { setError(''); complete.mutate({ taskId: item.task_id, date: item.date, completed: !item.completed }, { onError: cause => setError(cause instanceof Error ? cause.message : 'Не удалось сохранить выполнение') }) }} />
      <div className="occurrenceText"><strong>{item.title}</strong><span>{sectionNames[item.section]}{showDate ? ` · ${displayDate(item.date)}` : ''}{item.historical ? ' · выполнено до изменения расписания' : ''}</span></div>
      {item.priority === 'high' && <span className="priorityDot" title="Высокий приоритет">Важное</span>}
    </div>)}
  </div>
}
