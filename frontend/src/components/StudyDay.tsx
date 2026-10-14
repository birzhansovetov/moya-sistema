import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { useAuth } from '../auth'
import { studyPaths } from '../studyTypes'

type StudyDayResponse = {
  items: { course_id: string; course_title: string; plan_id: string; lesson_id: string; title: string; date: string; minutes: number }[]
}

export function StudyDay({ date }: { date: string }) {
  const { user } = useAuth()
  const query = useQuery({
    queryKey: ['study-day', user?.id, date],
    queryFn: () => api<StudyDayResponse>(`/study/day?date=${date}`),
    enabled: !!user,
  })

  return <section className="card healthDay">
    <h2>Обучение и языки</h2>
    {query.isError ? <p role="alert" className="errorMessage">Занятия недоступны. <button className="textButton" onClick={() => void query.refetch()}>Повторить загрузку</button></p>
      : !query.data ? <p className="muted">Загружаем занятия…</p>
        : query.data.items.length ? <>
          <p className="muted">Следующее занятие из вашего плана</p>
          {query.data.items.map(item => <div key={item.plan_id} className="healthDayItem">
            <div><strong>{item.course_title}</strong><p>{item.minutes} минут</p></div>
            <Link to={`${studyPaths[item.course_id]}?${new URLSearchParams({ plan: item.plan_id, lesson: item.lesson_id, date })}`}>{item.title}</Link>
          </div>)}
        </> : <p className="muted">На эту дату занятия нет. Выберите дни в планах <Link to="/education/java">Java</Link>, <Link to="/education/go">Go</Link>, <Link to="/languages">английского</Link> или <Link to="/profession">профессии</Link>.</p>}
  </section>
}
