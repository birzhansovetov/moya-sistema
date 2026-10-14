import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { api } from '../api'
import { useAuth } from '../auth'
import { dateOffset } from '../taskTypes'
import './HealthDay.css'

type SportPlan = { id: string; started_on: string; answers: { weekdays: number[]; days_per_week: number }; program: { duration_weeks?: number; sessions: Array<{ id: string; title: string }> } }
type Workout = { id: string; plan_id: string; date: string; session_id: string }

export function HealthDay({ date }: { date: string }) {
  const { user } = useAuth()
  const plan = useQuery({ queryKey: ['sport-plan', user?.id], queryFn: () => api<{ plan: SportPlan | null }>('/health/sport/plan'), enabled: !!user })
  const workouts = useQuery({ queryKey: ['sport-workouts', user?.id], queryFn: () => api<{ items: Workout[] }>('/health/sport/workouts'), enabled: !!user && !!plan.data?.plan })
  const sport = plan.data?.plan
  const weekday = ((new Date(`${date}T12:00:00Z`).getUTCDay() + 6) % 7) + 1
  const scheduledIndex = sport?.answers.weekdays.indexOf(weekday) ?? -1
  const inSportWindow = !!sport && date >= sport.started_on && date <= dateOffset(sport.started_on, (sport.program.duration_weeks || 4) * 7 - 1)
  const session = inSportWindow && scheduledIndex >= 0 ? sport?.program.sessions[scheduledIndex] : null
  const done = session && workouts.data?.items.some(item => item.plan_id === sport?.id && item.date === date && item.session_id === session.id)
  return <section className="card healthDay"><div className="sectionHeading"><div><h2>Здоровье</h2></div><Link to="/health">Открыть здоровье</Link></div>
    {plan.isLoading && <p className="muted">Загружаем тренировку…</p>}
    {(plan.isError || workouts.isError) && <p role="alert" className="errorMessage">Не удалось загрузить тренировку. Откройте раздел спорта и повторите попытку.</p>}
    {session && <div className="healthDayItem"><div><span className="eyebrow">ТРЕНИРОВКА</span><h3>{session.title}</h3><p>{done ? 'Тренировка записана в спортивном журнале.' : 'Откройте план, выполните занятие и запишите результат.'}</p></div><Link to={`/health/sport?${new URLSearchParams({ plan: sport!.id, date, session: session.id })}#workout-journal`}>{done ? 'Открыть историю' : 'Открыть тренировку'}</Link></div>}
    {!plan.isLoading && !session && !plan.isError && <p className="muted">На эту дату тренировка не запланирована.</p>}
    <Link className="healthDayRecipeLink" to="/health/nutrition">Рецепты с граммами ингредиентов</Link>
  </section>
}
