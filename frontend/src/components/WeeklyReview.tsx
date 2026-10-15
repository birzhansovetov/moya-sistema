import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, json } from '../api'
import { useAuth } from '../auth'
import { dateOffset, displayDate } from '../taskTypes'
import './WeeklyReview.css'

type Area = 'health' | 'education' | 'profession' | 'languages' | 'finance' | 'personal'
type Feedback = 'fits' | 'too_easy' | 'too_hard'
type Review = { start: string; end: string; tasks: { planned: number; completed: number }; areas: Record<Area, number>;
  training?: { plan_title: string; planned: number; completed: number; average_difficulty: number | null;
    suggestion: 'keep' | 'review_frequency'; reason: string; feedback?: Feedback } | null }
const areas: { key: Area; name: string; to: string }[] = [
  { key: 'health', name: 'Здоровье', to: '/health' },
  { key: 'education', name: 'Книги', to: '/books' },
  { key: 'profession', name: 'Профессия', to: '/profession' },
  { key: 'languages', name: 'Языки', to: '/languages' },
  { key: 'finance', name: 'Финансы', to: '/finance' },
  { key: 'personal', name: 'Личное', to: '/personal' },
]

export function WeeklyReview({ today }: { today: string }) {
  const { user } = useAuth()
  const weekday = new Date(`${today}T12:00:00Z`).getUTCDay()
  const end = dateOffset(today, -(weekday || 7))
  const key = `moya-week-review:${user?.id}:${end}`
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(key) === 'kept')
  const [reason, setReason] = useState('')
  const [savedFeedback, setSavedFeedback] = useState<{ end: string; rating: Feedback } | null>(null)
  const [feedbackError, setFeedbackError] = useState('')
  const [savingFeedback, setSavingFeedback] = useState(false)
  const query = useQuery({ queryKey: ['weekly-review', user?.id, end],
    queryFn: () => api<Review>(`/calendar/weekly-review?end=${end}`), enabled: !!user })
  async function saveFeedback(rating: Feedback) {
    setSavingFeedback(true)
    setFeedbackError('')
    try {
      await api('/calendar/weekly-review/feedback', json('PUT', { end, rating }))
      setSavedFeedback({ end, rating })
    } catch (error) {
      setFeedbackError(error instanceof Error ? error.message : 'Не удалось сохранить оценку')
    } finally {
      setSavingFeedback(false)
    }
  }
  if (dismissed && !query.data?.training) return null
  const selectedFeedback = savedFeedback?.end === end ? savedFeedback.rating : query.data?.training?.feedback
  return <section className="card weeklyReview" aria-label="Еженедельный пересмотр">
    <div className="weeklyReviewHeader"><div><span className="eyebrow">ПРОВЕРИТЬ РИТМ</span><h2>Ваши последние 7 дней</h2><p>{displayDate(dateOffset(end, -6))} — {displayDate(end)}. Сводка составлена по вашим записям.</p></div></div>
    {query.isError ? <p role="alert" className="errorMessage">Не удалось загрузить обзор. <button className="textButton" onClick={() => void query.refetch()}>Повторить</button></p>
      : !query.data ? <p className="muted">Собираем ваши записи за неделю…</p>
        : <><ul className="weeklyReviewAreas">{areas.map(area => <li key={area.key}><Link to={area.to}>{area.name}</Link><strong>{query.data.areas[area.key]}</strong></li>)}</ul>
          <p className="weeklyReviewTasks">Отдельные задачи: <strong>{query.data.tasks.completed} из {query.data.tasks.planned}</strong> выполнено по расписанию.</p>
          {query.data.training && <div className="weeklyReviewTraining"><span className="eyebrow">ТРЕНИРОВКИ</span><h3>{query.data.training.plan_title}</h3><p>{query.data.training.reason}</p><span className="weeklyReviewTrainingCount">{query.data.training.completed} из {query.data.training.planned} занятий записано</span>
            <div className="weeklyReviewFeedback" role="group" aria-label="Как вам нагрузка за неделю?">
              {([['fits', 'Подходит'], ['too_easy', 'Слишком легко'], ['too_hard', 'Слишком сложно']] as const).map(([rating, label]) =>
                <button key={rating} type="button" className="secondaryButton" aria-pressed={selectedFeedback === rating}
                  disabled={savingFeedback} onClick={() => void saveFeedback(rating)}>{label}</button>)}
            </div>
            {savedFeedback?.end === end && !feedbackError && <p className="weeklyReviewFeedbackStatus" role="status">Оценка сохранена для этой недели.</p>}
            {feedbackError && <p role="alert" className="errorMessage">{feedbackError}</p>}
          </div>}
          {query.data.tasks.planned > query.data.tasks.completed && <div className="weeklyReviewReflection"><label>Что помешало выполнить часть отдельных задач?<select value={reason} onChange={event => setReason(event.target.value)}><option value="">Выберите причину</option><option value="time">Не хватило времени</option><option value="hard">Было слишком сложно</option><option value="goal">Цель изменилась</option><option value="other">Другая причина</option></select></label>{reason && <p>{reason === 'time' ? 'Попробуйте сократить дни или время занятий в анкете.' : reason === 'hard' ? 'Откройте нужный раздел и выберите более простой материал.' : reason === 'goal' ? 'Обновите цель в анкете и посмотрите новый подбор.' : 'Вы можете оставить план или изменить условия подбора.'}</p>}</div>}
          <div className="weeklyReviewActions">{query.data.training ? <><Link className="primaryButton" to="/onboarding?focus=sport-program">Подобрать с учётом недели</Link><Link className="secondaryButton" to="/onboarding?focus=sport-schedule">Изменить частоту</Link><Link className="secondaryButton" to="/onboarding?focus=sport-program">Выбрать другую программу</Link></> : <><button type="button" className="secondaryButton" onClick={() => { localStorage.setItem(key, 'kept'); setDismissed(true) }}>План подходит</button><Link className="secondaryButton" to="/onboarding">Уменьшить нагрузку</Link><Link className="primaryButton" to="/onboarding">Изменить цель</Link></>}</div><p className="weeklyReviewNote">{query.data.training ? 'Подбор учтёт вашу оценку нагрузки. Локальный ИИ предложит вариант, если доступен. План изменится только после подтверждения в анкете.' : 'Анкета покажет новый подбор до сохранения. История занятий останется.'}</p></>}
  </section>
}
