import { Link } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from '../auth'
import { OccurrenceList } from '../components/OccurrenceList'
import { StudyDay } from '../components/StudyDay'
import { DevelopmentDay } from '../components/DevelopmentDay'
import { HealthDay } from '../components/HealthDay'
import { TodayNext } from '../components/TodayNext'
import { AnalyticsPanel } from '../components/AnalyticsPanel'
import { useActivityStreak, useCalendar } from '../taskHooks'
import { dateOffset, displayDate } from '../taskTypes'
import { useLocalToday } from '../useLocalToday'
import './Today.css'

export function TodayPage() {
  const { user } = useAuth()
  const today = useLocalToday(user?.timezone || 'Asia/Almaty')
  const streak = useActivityStreak(today)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const selected = selectedDate ?? today
  const calendar = useCalendar(selected, selected)
  const items = calendar.data?.items.filter(item => !item.historical) || []
  const completed = items.filter(item => item.completed).length
  const weekStart = dateOffset(selected, -((new Date(`${selected}T12:00:00Z`).getUTCDay() + 6) % 7))
  const week = useCalendar(weekStart, dateOffset(weekStart, 6))
  const weekItems = week.data?.items.filter(item => !item.historical) || []
  const weekDone = weekItems.filter(item => item.completed).length
  const streakCount = streak.data?.current_streak ?? 0
  const streakUnit = streakCount % 10 === 1 && streakCount % 100 !== 11 ? 'день' : streakCount % 10 >= 2 && streakCount % 10 <= 4 && (streakCount % 100 < 12 || streakCount % 100 > 14) ? 'дня' : 'дней'
  return <div>
    <div className="pageHeader"><div><h1>Мой день</h1><p>Планы, записи и задачи на {displayDate(selected)}.</p></div><Link to={`/tasks?new=1&date=${selected}`} className="primaryButton">+ Новая задача</Link></div>
    <div className="dateToolbar"><button type="button" className="secondaryButton" aria-label="Предыдущий день" onClick={() => setSelectedDate(dateOffset(selected, -1))}>Ранее</button><label>Дата <input type="date" value={selected} onChange={event => setSelectedDate(event.target.value && event.target.value !== today ? event.target.value : null)} /></label><button type="button" className="secondaryButton" aria-label="Следующий день" onClick={() => setSelectedDate(dateOffset(selected, 1))}>Позже</button>{selected !== today && <button className="textButton" onClick={() => setSelectedDate(null)}>Вернуться к сегодня</button>}</div>
    <TodayNext date={selected} />
    <section className="activityStreak" aria-label="Серия активных дней">
      <div className="activityStreakIntro"><span className="activityStreakLabel">СЕРИЯ АКТИВНОСТИ</span><strong>{streak.isError ? '—' : streak.isLoading ? '…' : streakCount} <small>{streakUnit} подряд</small></strong><p>{streak.isError ? 'Не удалось загрузить активность.' : streak.data?.today_active ? 'Сегодня уже есть активность' : streakCount ? 'Одно действие сегодня сохранит серию' : 'Начните серию с одного действия сегодня'}</p></div>
      <div className="activityStreakDays" aria-label="Активность за последние семь дней">{streak.data?.days.map(day => <div key={day.date} className={`activityStreakDay ${day.active ? 'isActive' : ''}`} title={`${displayDate(day.date)} — ${day.active ? 'есть активность' : 'нет активности'}`} aria-label={`${displayDate(day.date)}: ${day.active ? 'есть активность' : 'нет активности'}`}><span>{new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC', weekday: 'short' }).format(new Date(`${day.date}T12:00:00Z`))}</span><b>{new Date(`${day.date}T12:00:00Z`).getUTCDate()}</b></div>)}</div>
    </section>
    {selected === today && <AnalyticsPanel today={today} />}
    <details className="todayMore"><summary>Все планы и записи на дату</summary><div className="todayColumns">
      <div className="todayPlanColumn"><div id="day-health"><HealthDay date={selected} /></div><div id="day-study"><StudyDay date={selected} /></div></div>
      <div id="day-personal"><DevelopmentDay date={selected} personalItems={calendar.data?.personal_items || []} personalError={calendar.isError} /></div>
    </div></details>
    <div className="todayTasks">
      <section className="card" id="day-tasks"><div className="sectionHeading"><div><h2>Задачи на {selected === today ? 'сегодня' : displayDate(selected)}</h2></div><Link to="/tasks">Все задачи</Link></div>
        <div className="todaySummary" aria-label="Краткая сводка задач">
          <section className="todayMetric"><span>На дату</span><div className="todayMetricValue"><strong>{calendar.isError ? '—' : calendar.isLoading ? '…' : items.length}</strong><small>{calendar.isError ? 'данные недоступны' : 'задач'}</small></div></section>
          <section className="todayMetric"><span>Выполнено</span><div className="todayMetricValue"><strong>{calendar.isError ? '—' : calendar.isLoading ? '…' : completed}</strong><small>{calendar.isError ? 'данные недоступны' : items.length ? `из ${items.length}` : 'задач'}</small></div></section>
          <section className="todayMetric"><span>Неделя</span><div className="todayMetricValue"><strong>{week.isError ? '—' : week.isLoading ? '…' : `${weekDone}/${weekItems.length}`}</strong><small>{week.isError ? 'данные недоступны' : 'задач'}</small></div></section>
        </div>
        {calendar.isError ? <p role="alert" className="errorMessage">Не удалось загрузить задачи. <button className="textButton" onClick={() => void calendar.refetch()}>Повторить</button></p> : calendar.isLoading ? <p className="muted">Загружаем задачи…</p> : <OccurrenceList items={items} />}
      </section>
    </div>
  </div>
}
