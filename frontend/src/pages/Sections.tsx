import { Link } from 'react-router-dom'
import { useState } from 'react'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from '../api'
import { useAuth } from '../auth'
import { languageCourses, studyPaths, type StudyState } from '../studyTypes'
import type { Book, PageList } from '../readingTypes'
import styles from './Sections.module.css'

type Sphere = 'health' | 'education' | 'profession' | 'languages' | 'finance' | 'personal'
type Preferences = { hidden_spheres: Sphere[] }

const spheres: { key: Sphere; name: string; icon: string; description: string; ready: boolean }[] = [
  { key: 'health', name: 'Здоровье', icon: '✳', description: 'Тренировки, рецепты и калькулятор калорий', ready: true },
  { key: 'education', name: 'Обучение', icon: '◇', description: 'Курсы Java и Go, книги и дневник чтения', ready: true },
  { key: 'profession', name: 'Профессия', icon: '▣', description: 'Backend-разработка: сервис, база данных и портфолио', ready: true },
  { key: 'languages', name: 'Языки', icon: '◌', description: 'Английский, казахский, корейский, турецкий и испанский', ready: true },
  { key: 'finance', name: 'Финансы', icon: '◫', description: 'Доходы, расходы и анализ бюджета', ready: true },
  { key: 'personal', name: 'Личное', icon: '○', description: 'События, отдых и личный дневник', ready: true },
]

export function SectionsPage() {
  const { user } = useAuth()
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')
  const client = useQueryClient()
  const queryKey = ['sphere-preferences', user?.id]
  const preferences = useQuery({ queryKey, queryFn: () => api<Preferences>('/profile/spheres'), enabled: !!user })
  const sport = useQuery({ queryKey: ['sport-plan', user?.id], queryFn: () => api<{ plan: { id: string; program: { title: string } } | null }>('/health/sport/plan'), enabled: !!user })
  const java = useQuery({ queryKey: ['study-state', user?.id, 'java', null, 0], queryFn: () => api<StudyState>('/study/state/java?history_offset=0'), enabled: !!user })
  const go = useQuery({ queryKey: ['study-state', user?.id, 'go', null, 0], queryFn: () => api<StudyState>('/study/state/go?history_offset=0'), enabled: !!user })
  const languageStates = useQueries({ queries: languageCourses.map(id => ({ queryKey: ['study-state', user?.id, id, null, 0], queryFn: () => api<StudyState>(`/study/state/${id}?history_offset=0`), enabled: !!user })) })
  const profession = useQuery({ queryKey: ['study-state', user?.id, 'java-backend', null, 0], queryFn: () => api<StudyState>('/study/state/java-backend?history_offset=0'), enabled: !!user })
  const books = useQuery({ queryKey: ['reading-books', user?.id, 'daily'], queryFn: () => api<PageList<Book>>('/reading/books?status=reading&limit=100'), enabled: !!user })
  const update = useMutation({
    mutationFn: (hidden_spheres: Sphere[]) => api<Preferences>('/profile/spheres', json('PATCH', { hidden_spheres })),
    onSuccess: saved => { setError(''); client.setQueryData(queryKey, saved) },
    onError: cause => setError(cause instanceof Error ? cause.message : 'Не удалось сохранить настройки'),
  })
  const hidden = preferences.data?.hidden_spheres || []
  const visible = spheres.filter(sphere => !hidden.includes(sphere.key))
  const courseLink = (courseId: string, state?: StudyState) => state?.active_plan ? { to: `${studyPaths[courseId]}?${new URLSearchParams({ plan: state.active_plan.id, ...(state.next_lesson_id ? { lesson: state.next_lesson_id } : {}) })}`, label: state.next_lesson_id ? 'Продолжить урок' : 'Открыть план' } : { to: studyPaths[courseId], label: 'Выбрать план' }
  const activeLanguageIndex = languageStates.findIndex(state => !!state.data?.active_plan)
  const activeLanguage = activeLanguageIndex >= 0 ? languageCourses[activeLanguageIndex] : null
  const activeBook = books.data?.items.find(book => !book.deleted && book.status === 'reading')
  const next: Record<Sphere, { to: string; label: string }> = {
    health: sport.isError ? { to: '/health', label: 'Открыть здоровье — прогресс недоступен' } : sport.data?.plan ? { to: `/health/sport?plan=${sport.data.plan.id}`, label: `Продолжить: ${sport.data.plan.program.title}` } : { to: '/health/sport', label: 'Подобрать тренировку' },
    education: java.isError && go.isError && books.isError ? { to: '/education', label: 'Открыть обучение — прогресс недоступен' } : go.data?.active_plan ? courseLink('go', go.data) : java.data?.active_plan ? courseLink('java', java.data) : activeBook ? { to: `/education/reading?book=${activeBook.id}`, label: `Продолжить чтение: ${activeBook.title}` } : { to: '/education', label: 'Выбрать курс или книгу' },
    profession: profession.isError ? { to: '/profession', label: 'Открыть профессию — прогресс недоступен' } : courseLink('java-backend', profession.data),
    languages: activeLanguage ? courseLink(activeLanguage, languageStates[activeLanguageIndex].data) : { to: '/languages', label: languageStates.every(state => state.isError) ? 'Открыть языки — прогресс недоступен' : 'Выбрать язык' },
    finance: { to: '/finance', label: 'Открыть расходы' },
    personal: { to: '/personal', label: 'Открыть дневник' },
  }
  function toggle(key: Sphere) {
    setError('')
    update.mutate(hidden.includes(key) ? hidden.filter(item => item !== key) : [...hidden, key])
  }
  return <div className={styles.page}>
    <div className="pageHeader"><div><h1>Разделы</h1><p>Материалы и планы для каждой сферы жизни.</p></div><button className="secondaryButton" onClick={() => setEditing(!editing)}>{editing ? 'Готово' : 'Настроить разделы'}</button></div>
    {editing && <section className="card sectionSettings"><h2>Показывать сферы</h2><p className="muted">Скрытую сферу можно вернуть. Ваши данные сохраняются.</p>{preferences.isError ? <p className="muted">Настройки недоступны.</p> : preferences.isLoading ? <p className="muted">Загружаем настройки…</p> : spheres.map(sphere => <label key={sphere.key}><input type="checkbox" checked={!hidden.includes(sphere.key)} disabled={update.isPending} onChange={() => toggle(sphere.key)} />{sphere.name}</label>)}{error && <p role="alert" className="errorMessage">{error}</p>}</section>}
    {preferences.isError ? <p role="alert" className="errorMessage">Не удалось загрузить настройки сфер. <button className="textButton" onClick={() => void preferences.refetch()}>Повторить</button></p> : preferences.isLoading ? <p className="muted">Загружаем сферы…</p> : visible.length === 0 ? <div className="emptyState"><h3>Все сферы скрыты</h3><p>Откройте настройки, чтобы показать их снова.</p></div> : <div className={styles.grid}>{visible.map(sphere => <section className={`${styles.card} ${styles[sphere.key]} ${next[sphere.key].to === `/${sphere.key}` ? styles.single : ''}`} key={sphere.key}><Link to={`/${sphere.key}`} className={styles.main}><h2>{sphere.name}</h2><p>{sphere.description}</p></Link>{next[sphere.key].to !== `/${sphere.key}` && <Link className={styles.continue} to={next[sphere.key].to}>{next[sphere.key].label}</Link>}</section>)}</div>}
  </div>
}
