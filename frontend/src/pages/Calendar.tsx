import { useEffect, useState } from 'react'
import { useAuth } from '../auth'
import { PersonalDayLinks } from '../components/DevelopmentDay'
import { OccurrenceList } from '../components/OccurrenceList'
import { useCalendar } from '../taskHooks'
import { dateOffset } from '../taskTypes'
import { useLocalToday } from '../useLocalToday'

const weekNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
export function CalendarPage() {
  const { user } = useAuth()
  const today = useLocalToday(user?.timezone || 'Asia/Almaty')
  const [month, setMonth] = useState(today.slice(0, 7))
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const selected = selectedDate ?? today
  useEffect(() => { if (selectedDate === null) setMonth(today.slice(0, 7)) }, [today, selectedDate])
  const first = `${month}-01`
  const last = dateOffset(`${month}-01`, new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate() - 1)
  const calendar = useCalendar(first, last)
  const beginning = new Date(`${first}T12:00:00Z`).getUTCDay()
  const blanks = (beginning + 6) % 7
  const days = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate()
  const label = new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC', month: 'long', year: 'numeric' }).format(new Date(`${first}T12:00:00Z`))
  const items = calendar.data?.items || []
  const personalItems = calendar.data?.personal_items || []
  const selectedPersonal = personalItems.filter(item => item.date === selected)
  const selectedItems = items.filter(item => item.date === selected)
  function moveMonth(offset: number) {
    const date = new Date(`${first}T12:00:00Z`)
    date.setUTCMonth(date.getUTCMonth() + offset)
    const next = date.toISOString().slice(0, 7)
    setMonth(next); setSelectedDate(`${next}-01`)
  }
  return <div>
    <div className="pageHeader"><div><span className="eyebrow">ПЛАНИРОВАНИЕ</span><h1>Календарь</h1><p>Ваши задачи и личные события по датам.</p></div></div>
    <div className="calendarLayout"><section className="card calendarCard">
      <div className="calendarHeader"><h2>{label}</h2><div><button className="iconButton" aria-label="Предыдущий месяц" onClick={() => moveMonth(-1)}>‹</button><button className="iconButton" aria-label="Следующий месяц" onClick={() => moveMonth(1)}>›</button></div></div>
      {calendar.isError && <p role="alert" className="errorMessage">Не удалось загрузить календарь. <button className="textButton" onClick={() => void calendar.refetch()}>Повторить</button></p>}
      <div className="calendarGrid">{weekNames.map(day => <span className="weekdayName" key={day}>{day}</span>)}{Array.from({ length: blanks }, (_, index) => <span key={`blank-${index}`} />)}{Array.from({ length: days }, (_, index) => {
        const value = `${month}-${String(index + 1).padStart(2, '0')}`
        const count = items.filter(item => item.date === value).length
        const personalCount = personalItems.filter(item => item.date === value).length
        return <button key={value} aria-label={`${index + 1} ${label}${calendar.isError ? '' : `, задач: ${count}, событий: ${personalCount}`}`} aria-pressed={selected === value} className={`calendarDay ${value === today ? 'isToday' : ''} ${selected === value ? 'isSelected' : ''}`} onClick={() => setSelectedDate(value === today ? null : value)}><strong>{index + 1}</strong>{!calendar.isError && count > 0 && <small>{count} {count === 1 ? 'задача' : 'задачи'}</small>}{!calendar.isError && personalCount > 0 && <small>◌ {personalCount}</small>}</button>
      })}</div>
      {calendar.isLoading && <p className="muted">Загружаем календарь…</p>}
    </section><section className="card calendarSide"><span className="eyebrow">ВЫБРАННЫЙ ДЕНЬ</span><h2>{new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC', day: 'numeric', month: 'long' }).format(new Date(`${selected}T12:00:00Z`))}</h2>{calendar.isError ? <p className="muted">Данные за день недоступны.</p> : calendar.isLoading ? <p className="muted">Загружаем задачи…</p> : <><OccurrenceList items={selectedItems} /><h3>Личные события</h3><PersonalDayLinks items={selectedPersonal} date={selected} />{!selectedPersonal.length && <p className="muted">На эту дату событий нет.</p>}</>}</section></div>
  </div>
}
