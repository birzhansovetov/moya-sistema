import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { dateOffset, displayDate } from '../taskTypes'
import { WeeklyReview } from './WeeklyReview'
import './AnalyticsPanel.css'

type Area = 'health' | 'education' | 'profession' | 'languages' | 'finance' | 'personal'
type Counts = Record<Area, number>
type Week = { end: string; active_days: number; workouts_logged: number;
  tasks: { planned: number; completed: number }; areas: Counts; training: object | null }
type Analytics = { start: string; end: string; weeks: Week[];
  summary: { active_days: number; workouts_logged: number;
    tasks: { planned: number; completed: number }; areas: Counts } }

const areas: { key: Area; label: string; to: string }[] = [
  { key: 'health', label: 'Здоровье', to: '/health' },
  { key: 'education', label: 'Обучение', to: '/education' },
  { key: 'profession', label: 'Профессия', to: '/profession' },
  { key: 'languages', label: 'Языки', to: '/languages' },
  { key: 'finance', label: 'Финансы', to: '/finance' },
  { key: 'personal', label: 'Личное', to: '/personal' },
]

function form(number: number, one: string, few: string, many: string) {
  const lastTwo = number % 100
  if (lastTwo >= 11 && lastTwo <= 14) return many
  if (number % 10 === 1) return one
  if (number % 10 >= 2 && number % 10 <= 4) return few
  return many
}

export function AnalyticsPanel({ today }: { today: string }) {
  const { user } = useAuth()
  const weekday = new Date(`${today}T12:00:00Z`).getUTCDay()
  const end = dateOffset(today, -(weekday || 7))
  const query = useQuery({ queryKey: ['analytics', user?.id, end],
    queryFn: () => api<Analytics>(`/calendar/analytics?end=${end}`), enabled: !!user })
  const data = query.data
  const hasActivity = !!data && (data.summary.active_days > 0 || data.summary.tasks.completed > 0 ||
    Object.values(data.summary.areas).some(count => count > 0))
  const hasTraining = !!data?.weeks.at(-1)?.training
  const totals = data?.weeks.map(week => Object.values(week.areas).reduce((sum, count) => sum + count, 0) + week.tasks.completed) || []
  const maxTotal = Math.max(1, ...totals)

  return <section className="analyticsPanel" aria-label="Аналитика за 4 недели">
    <div className="analyticsPanelHeading"><div><span className="eyebrow">ВАША ДИНАМИКА</span><h2>Аналитика за 4 недели</h2>
      {data && <p>{displayDate(data.start)} — {displayDate(data.end)} · завершённые недели</p>}</div></div>
    {query.isError ? <p role="alert" className="errorMessage">Не удалось загрузить аналитику. <button type="button" className="textButton" onClick={() => void query.refetch()}>Повторить</button></p>
      : !data ? <p className="muted">Собираем записи за четыре недели…</p>
        : !hasActivity && !hasTraining ? <div className="analyticsEmpty"><p>Пока нет записанных действий за этот период.</p><span>Начните с материала в любом направлении, и здесь появится динамика.</span><Link to="/sections">Открыть разделы</Link></div>
          : <>
            <div className="analyticsMetrics" aria-label="Итоги периода">
              <strong>{data.summary.active_days} {form(data.summary.active_days, 'активный день', 'активных дня', 'активных дней')}</strong>
              <strong>{data.summary.workouts_logged} {form(data.summary.workouts_logged, 'тренировка', 'тренировки', 'тренировок')} {form(data.summary.workouts_logged, 'записана', 'записаны', 'записано')}</strong>
              <strong>{data.summary.tasks.completed} из {data.summary.tasks.planned} задач выполнено</strong>
            </div>
            <div className="analyticsBody">
              <div className="analyticsTrend"><h3>Активность по неделям</h3><p>Количество записанных действий</p>
                <ol aria-label="Активность по неделям">{data.weeks.map((week, index) => <li key={week.end}>
                  <span>{displayDate(week.end)}</span><div className="analyticsBarTrack"><i style={{ width: `${totals[index] / maxTotal * 100}%` }} /></div><strong>{totals[index]}</strong>
                </li>)}</ol>
              </div>
              <div className="analyticsAreas"><h3>По направлениям</h3><div>{areas.map(area => <Link to={area.to} key={area.key}>
                <span>{area.label}</span><strong>{data.summary.areas[area.key]}</strong>
              </Link>)}</div></div>
            </div>
            <details className="analyticsDetails"><summary>Разбор последней недели</summary><WeeklyReview today={today} /></details>
          </>}
  </section>
}
