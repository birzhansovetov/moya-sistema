import { Link, useSearchParams } from 'react-router-dom'
import { useQueries } from '@tanstack/react-query'
import { api } from '../api'
import { useAuth } from '../auth'
import { languageCourses, languageNames, studyPaths, type StudyState } from '../studyTypes'
import { StudyPage } from './Study'
import styles from './Languages.module.css'

export function LanguagesPage() {
  const [params] = useSearchParams()
  const { user } = useAuth()
  const states = useQueries({ queries: languageCourses.map(id => ({
    queryKey: ['study-state', user?.id, id, null, 0],
    queryFn: () => api<StudyState>(`/study/state/${id}?history_offset=0`),
    enabled: !!user,
  })) })
  // Existing links to /languages?plan=... always refer to the English course.
  if (params.has('plan') || params.has('lesson')) return <StudyPage courseId="english" />
  return <div className={styles.page}><div className="pageHeader"><div><h1>Выберите язык</h1><p>Готовые уроки от основ до самостоятельной практики. Можно заниматься по одному плану за раз; при смене языка прежний прогресс сохранится.</p></div></div><div className={styles.grid}>{languageCourses.map((id, index) => {
    const state = states[index]
    const active = state.data?.active_plan
    return <section className={`card ${styles.card}`} key={id}><h2>{languageNames[id]}</h2><p>{id === 'english' ? 'A2–B2' : 'A1–B2'} · уроки, слова и практика</p>{active && <p>Ваш план: {active.level} · {state.data?.completed.length || 0} занятий пройдено</p>}{state.isError && <p role="alert" className="errorMessage">Не удалось получить прогресс. <button className="textButton" onClick={() => void state.refetch()}>Повторить</button></p>}<Link className="primaryButton" to={`${id === 'english' && !active ? '/languages/english' : studyPaths[id]}${active ? `?${new URLSearchParams({ plan: active.id, ...(state.data?.next_lesson_id ? { lesson: state.data.next_lesson_id } : {}) })}` : ''}`}>{active ? 'Продолжить' : 'Посмотреть курс'}</Link></section>
  })}</div></div>
}
