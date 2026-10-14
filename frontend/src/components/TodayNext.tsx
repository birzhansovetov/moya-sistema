import { Link } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { useAuth } from '../auth'
import { dateOffset } from '../taskTypes'
import { studyPaths } from '../studyTypes'
import type { Book, PageList } from '../readingTypes'

type SportPlan = { id: string; started_on: string; answers: { weekdays: number[]; minutes_per_session?: number }; program: { duration_weeks?: number; sessions: Array<{ id: string; title: string }> } }
type Workout = { plan_id: string; date: string; session_id: string }
type StudyItem = { course_id: string; course_title: string; plan_id: string; lesson_id: string; title: string; date: string; minutes: number }

export function TodayNext({ date }: { date: string }) {
  const { user } = useAuth()
  const [budget, setBudget] = useState(60)
  const sport = useQuery({ queryKey: ['sport-plan', user?.id], queryFn: () => api<{ plan: SportPlan | null }>('/health/sport/plan'), enabled: !!user })
  const workouts = useQuery({ queryKey: ['sport-workouts', user?.id], queryFn: () => api<{ items: Workout[] }>('/health/sport/workouts'), enabled: !!user && !!sport.data?.plan })
  const study = useQuery({ queryKey: ['study-day', user?.id, date], queryFn: () => api<{ items: StudyItem[] }>(`/study/day?date=${date}`), enabled: !!user })
  const books = useQuery({ queryKey: ['reading-books', user?.id, 'daily'], queryFn: () => api<PageList<Book>>('/reading/books?status=reading&limit=100'), enabled: !!user })
  const plan = sport.data?.plan
  const weekday = ((new Date(`${date}T12:00:00Z`).getUTCDay() + 6) % 7) + 1
  const index = plan?.answers.weekdays.indexOf(weekday) ?? -1
  const inWindow = !!plan && date >= plan.started_on && date <= dateOffset(plan.started_on, (plan.program.duration_weeks || 4) * 7 - 1)
  const session = inWindow && index >= 0 ? plan?.program.sessions[index] : null
  const workoutDone = session && workouts.data?.items.some(item => item.plan_id === plan?.id && item.date === date && item.session_id === session.id)
  const lessons = study.data?.items || []
  const book = books.data?.items.find(item => !item.deleted && item.status === 'reading' && (!item.pages || item.current_page < item.pages))
  const steps = [
    ...(session && !workoutDone ? [{ title: session.title, area: 'Тренировка', detail: 'План и техника упражнений', minutes: plan?.answers.minutes_per_session || 45, to: `/health/sport?${new URLSearchParams({ plan: plan!.id, date, session: session.id })}#sport-sessions` }] : []),
    ...lessons.map(lesson => ({ title: lesson.title, area: lesson.course_title, detail: 'Урок и практика', minutes: lesson.minutes, to: `${studyPaths[lesson.course_id]}?${new URLSearchParams({ plan: lesson.plan_id, lesson: lesson.lesson_id, date })}` })),
    ...(book ? [{ title: book.title, area: 'Чтение', detail: book.pages ? `Продолжить со страницы ${book.current_page + 1}` : 'Продолжить чтение', minutes: 15, to: `/education/reading?${new URLSearchParams({ book: book.id, date })}` }] : []),
  ]
  let remaining = budget
  const queue = steps.filter(step => { if (step.minutes > remaining) return false; remaining -= step.minutes; return true })
  const next = queue[0]
  const loading = sport.isLoading || study.isLoading || books.isLoading || (!!plan && workouts.isLoading)
  const failed = sport.isError || study.isError || books.isError || workouts.isError
  return <section className="card todayNext" aria-label="Следующий шаг">{next ? <><div className="todayNextInner"><div><span className="todayNextLabel">Следующий шаг · {next.area} · {next.minutes} мин</span><h2>{next.title}</h2><p>{next.detail}</p></div><Link className="primaryButton" to={next.to}>Открыть материал</Link></div>{queue.length > 1 && <details className="todayNextExtra"><summary>Следом ещё {queue.length - 1}</summary><div className="todayNextQueue">{queue.slice(1).map(step => <Link key={step.to} to={step.to}>{step.area}: {step.title} · {step.minutes} мин</Link>)}</div></details>}</> : loading ? <p className="muted">Ищем следующий шаг в ваших планах…</p> : failed ? <div className="todayNextInner"><div><h2>Не удалось загрузить следующий шаг</h2><p>Можно открыть разделы и продолжить вручную.</p></div><Link className="primaryButton" to="/sections">Открыть разделы</Link></div> : steps.length ? <div className="todayNextInner"><div><h2>Плану нужно больше времени</h2><p>Ближайшее занятие займёт {Math.min(...steps.map(step=>step.minutes))} мин.</p></div><Link className="primaryButton" to={steps[0].to}>Открыть материал</Link></div> : <div className="todayNextInner"><div><h2>Выберите, с чего начать</h2><p>Готовые материалы и планы собраны в шести сферах.</p></div><Link className="primaryButton" to="/sections">Открыть материалы</Link></div>}<details className="todayNextExtra todayNextTime"><summary>На сегодня: {budget} мин · изменить время</summary><div className="todayBudget" aria-label="Время на занятия">{[15,30,60,90].map(value=><button type="button" key={value} aria-pressed={budget===value} onClick={()=>setBudget(value)}>{value} мин</button>)}</div>{steps.length > queue.length && <p className="todayNextHint">Остальные шаги доступны в разделах.</p>}</details></section>
}
