import {useWorkoutRestTimer} from '../useWorkoutRestTimer'
import {MediaPlayer} from '../components/MediaPlayer'
import {sportVideo} from '../mediaCatalog'
import { AssistantMaterialButton } from '../components/SectionAssistant'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { MaterialFit } from '../components/MaterialFit'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from '../api'
import { useAuth } from '../auth'
import { useLocalToday } from '../useLocalToday'
import { dateOffset, displayDate } from '../taskTypes'
import { isCalendarDate } from '../healthTypes'
import { buildSportWeeks, weeklySportAdvice } from '../sportSchedule'
import { SportLibrary } from '../components/SportLibrary'
import { Guides } from '../components/Guides'
import { Button, Input, Select } from '../components/ui'
import './Sport.css'

type Place = 'home' | 'outdoor' | 'gym'
type Equipment = 'low_bar' | 'bench' | 'machines' | 'dumbbells' | 'bands' | 'barbell'
type Experience = 'returning' | 'irregular' | 'regular'
type Answers = { goal: 'fat_loss_muscle_focus' | 'maintain' | 'strength_gain'; level: Experience; place: Place; equipment: Equipment[]; days_per_week: number; minutes_per_session: number; limitations: boolean; weekdays: number[] }
type Work = { exercise_id: string; sets: number; reps: string; rest_seconds: number; note: string }
type Session = { id: string; title: string; estimated_minutes?: number; warmup: string; work: Work[]; cooldown: string }
type Program = { id: string; title: string; level?: 'beginner' | 'intermediate'; overview: string; duration_weeks: number; progression: string[]; sources: string[]; sessions: Session[] }
type Exercise = { name: string; technique: string; common_errors: string; easier_version: string; substitution: string; source: string; alternatives?: Array<{ exercise_id: string; places: Place[]; required_equipment: Equipment[] }> }
type Catalog = { version: string; programs: Program[]; exercises: Record<string, Exercise> }
type Match = { program: Program | null; sessions: Session[]; reasons: string[]; material?: { title: string; intro: string; steps: string[]; example: string }; why?: string[]; version: string }
type Plan = { id: string; answers: Omit<Answers, 'level'> & { level: Experience | 'beginner' | 'intermediate' }; program: Program; started_on: string; content_version: string; revoked?: boolean }
type PlanResponse = { plan: Plan | null }
type SaveResponse = { status: 'saved' | 'replaced' | 'unchanged' | 'preview'; plan: Plan; proposed?: Program }
type Workout = { id: string; plan_id: string; date: string; session_id: string; program_title?: string; session_title?: string; difficulty: number; note: string; results?: Array<{ exercise_id: string; performed_exercise_id?: string; performed_exercise_name?: string; completed_sets: number; reps_per_set: number[]; weight_kg: number | null }> }
type ActualExercise = { sets: number; reps: string[]; weight: string; performed?: string }

const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const equipmentNames: Record<Equipment, string> = { low_bar: 'Низкая перекладина', bench: 'Устойчивая скамья', machines: 'Тренажёры', dumbbells: 'Гантели', bands: 'Резинки', barbell: 'Штанга' }
const initialAnswers: Answers = { goal: 'fat_loss_muscle_focus', level: 'returning', place: 'home', equipment: [], days_per_week: 2, minutes_per_session: 45, limitations: false, weekdays: [1, 4] }
function editAnswers(saved: Plan['answers']): Answers {
  return { ...saved, level: saved.level === 'beginner' ? 'returning' : saved.level === 'intermediate' ? 'irregular' : saved.level }
}

export function SportPage() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const requestedPlan = params.get('plan')
  const requestedDate = params.get('date')
  const requestedSession = params.get('session')
  const today = useLocalToday(user?.timezone || 'Asia/Almaty')
  const queryClient = useQueryClient()
  const catalog = useQuery({ queryKey: ['sport-catalog'], queryFn: () => api<Catalog>('/health/sport/catalog') })
  const planQuery = useQuery({ queryKey: ['sport-plan', user?.id], queryFn: () => api<PlanResponse>('/health/sport/plan') })
  const workouts = useQuery({ queryKey: ['sport-workouts', user?.id], queryFn: () => api<{ items: Workout[] }>('/health/sport/workouts') })
  const [answers, setAnswers] = useState<Answers>(initialAnswers)
  const [initialized, setInitialized] = useState(false)
  const [match, setMatch] = useState<Match | null>(null)
  const [proposed, setProposed] = useState<Program | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [sessionId, setSessionId] = useState('A')
  const [workoutDate, setWorkoutDate] = useState(today)
  const [actual, setActual] = useState<Record<string, ActualExercise>>({})
  const [difficulty, setDifficulty] = useState(5)
  const [note, setNote] = useState('')
  const [journalOpen, setJournalOpen] = useState(!!requestedPlan)
  const [draftLoadedKey, setDraftLoadedKey] = useState('')
  const [draftDirty, setDraftDirty] = useState(false)
  const [draftError, setDraftError] = useState('')
  const [exerciseIndex, setExerciseIndex] = useState(0)
  const finishingRef = useRef(false)

  useEffect(() => {
    if (!initialized && planQuery.data) {
      if (planQuery.data.plan) setAnswers(editAnswers(planQuery.data.plan.answers))
      setInitialized(true)
    }
  }, [initialized, planQuery.data])

  const contextPlan = planQuery.data?.plan
  useEffect(() => {
    if (!contextPlan || (!requestedPlan && !requestedDate && !requestedSession)) return
    const end = dateOffset(contextPlan.started_on, contextPlan.program.duration_weeks * 7 - 1)
    if (requestedPlan !== contextPlan.id || !isCalendarDate(requestedDate) || requestedDate < contextPlan.started_on || requestedDate > end || !contextPlan.program.sessions.slice(0, contextPlan.answers.days_per_week).some(item => item.id === requestedSession)) {
      setError('Ссылка относится к другому плану или занятию. Выберите дату и тренировку в текущем плане.')
      return
    }
    setSessionId(requestedSession!)
    setWorkoutDate(requestedDate)
    document.getElementById('workout-journal')?.scrollIntoView?.({ block: 'start' })
  }, [contextPlan?.id, requestedPlan, requestedDate, requestedSession])

  const matchMutation = useMutation({ mutationFn: (value: Answers) => api<Match>('/health/sport/match', json('POST', value)), onSuccess: selected => { setMatch(selected); setProposed(null); setError(''); setNotice('') }, onError: cause => setError(message(cause)) })
  const saveMutation = useMutation({ mutationFn: (confirm_replace: boolean) => api<SaveResponse>('/health/sport/plan', json('PUT', { answers, confirm_replace })), onSuccess: saved => {
    if (saved.status === 'preview') { setProposed(saved.proposed || null); setNotice('Новый план пока не сохранён. Подтвердите замену после просмотра.'); return }
    queryClient.setQueryData(['sport-plan', user?.id], { plan: saved.plan })
    setProposed(null); setMatch(null); setActual({}); setError(''); setNotice(saved.status === 'replaced' ? 'Новый план сохранён. История прежних тренировок доступна ниже.' : 'План сохранён.')
  }, onError: cause => setError(message(cause)) })
  const logMutation = useMutation({ mutationFn: (payload: unknown) => api<Workout>('/health/sport/workouts', json('POST', payload)), onSuccess: () => { setError(''); setNotice('Тренировка завершена и записана.'); setRestUntil(null); setActual({}); setNote(''); setDraftDirty(false); setDraftError(''); setJournalOpen(false); void queryClient.invalidateQueries({ queryKey: ['sport-workouts', user?.id] }); void queryClient.invalidateQueries({ queryKey: ['sport-draft', user?.id] }) }, onError: cause => { finishingRef.current = false; setError(message(cause)) } })

  const plan = planQuery.data?.plan
  const lastPlanDate = plan ? dateOffset(plan.started_on, plan.program.duration_weeks * 7 - 1) : today
  const activeSessions = plan?.program.sessions.slice(0, plan.answers.days_per_week) || []
  const activeSession = activeSessions.find(item => item.id === sessionId) || activeSessions[0]
  const draftKey = plan && activeSession ? `${plan.id}:${workoutDate}:${activeSession.id}` : ''
  const {restUntil,setRestUntil,restRemaining}=useWorkoutRestTimer(user?.id&&draftKey?`${user.id}:${draftKey}`:'')
  const draftQuery = useQuery({ queryKey: ['sport-draft', user?.id, draftKey], enabled: !!user && !!draftKey && journalOpen,
    queryFn: () => api<{ draft: { actual: Record<string, ActualExercise>; difficulty: number; note: string } | null }>(`/health/sport/draft?plan_id=${encodeURIComponent(plan!.id)}&date=${workoutDate}&session_id=${encodeURIComponent(activeSession!.id)}`), staleTime: Infinity })
  const draftMutation = useMutation({ mutationFn: (payload: { key: string; body: unknown }) => api<{ draft: { actual: Record<string, ActualExercise>; difficulty: number; note: string } }>('/health/sport/draft', json('PUT', payload.body)),
    onSuccess: (saved, payload) => { if (!finishingRef.current) queryClient.setQueryData(['sport-draft', user?.id, payload.key], saved); setDraftError('') },
    onError: cause => { if (!finishingRef.current) setDraftError(message(cause)) } })

  useEffect(() => { finishingRef.current = false; setActual({}); setDifficulty(5); setNote(''); setDraftLoadedKey(''); setDraftDirty(false); setDraftError(''); setExerciseIndex(0) }, [draftKey])
  useEffect(() => {
    if (!draftKey || !draftQuery.isSuccess || draftLoadedKey === draftKey) return
    setActual(draftQuery.data.draft?.actual || {})
    const savedActual = draftQuery.data.draft?.actual || {}
    const next = activeSession?.work.findIndex(work => {
      const result = savedActual[work.exercise_id]
      return !result || result.reps.slice(0, result.sets).some(value => !value.trim())
    }) ?? 0
    setExerciseIndex(next < 0 ? Math.max(0, (activeSession?.work.length || 1) - 1) : next)
    setDifficulty(draftQuery.data.draft?.difficulty || 5)
    setNote(draftQuery.data.draft?.note || '')
    setDraftLoadedKey(draftKey)
  }, [draftKey, draftQuery.isSuccess, draftQuery.data, draftLoadedKey, activeSession])
  useEffect(() => {
    if (!draftDirty || draftLoadedKey !== draftKey || !plan || !activeSession || draftMutation.isPending || finishingRef.current) return
    const timer = window.setTimeout(() => {
      setDraftDirty(false)
      draftMutation.mutate({ key: draftKey, body: { plan_id: plan.id, date: workoutDate, session_id: activeSession.id, actual, difficulty, note } })
    }, 600)
    return () => window.clearTimeout(timer)
  }, [draftDirty, draftLoadedKey, draftKey, plan?.id, activeSession?.id, workoutDate, actual, difficulty, note, draftMutation.isPending])
  const displayProgram = match?.program || plan?.program
  const displaySessions = match?.program ? match.sessions : activeSessions
  const planWeeks = plan ? buildSportWeeks(plan.started_on, plan.answers.weekdays, activeSessions.map(item => item.id), plan.program.duration_weeks) : []
  const startWeekday = plan ? new Date(`${plan.started_on}T12:00:00Z`).getUTCDay() || 7 : 1
  const firstMonday = plan ? dateOffset(plan.started_on, 1 - startWeekday) : today
  const currentWeek = Math.max(0, Math.min(planWeeks.length - 1, Math.floor((Date.parse(`${today}T12:00:00Z`) - Date.parse(`${firstMonday}T12:00:00Z`)) / (7 * 86400000))))

  function update<K extends keyof Answers>(key: K, value: Answers[K]) {
    setAnswers(current => ({ ...current, [key]: value }))
    setMatch(null); setProposed(null); setNotice('')
  }
  function toggleEquipment(key: Equipment) { update('equipment', answers.equipment.includes(key) ? answers.equipment.filter(item => item !== key) : [...answers.equipment, key]) }
  function toggleDay(day: number) { update('weekdays', answers.weekdays.includes(day) ? answers.weekdays.filter(item => item !== day) : [...answers.weekdays, day].sort()) }
  function changeActual(work: Work, change: (current: ActualExercise) => ActualExercise) {
    setActual(current => ({ ...current, [work.exercise_id]: change(current[work.exercise_id] || { sets: work.sets, reps: Array(work.sets).fill(''), weight: '' }) }))
    setDraftDirty(true)
  }
  function saveWorkout() {
    if (!plan || !activeSession) return
    const selected = activeSession.work.filter(work => {
      const entry = actual[work.exercise_id]
      return !!entry && (entry.reps.some(value => value.trim() !== '') || entry.weight.trim() !== '')
    })
    if (!selected.length) { setError('Заполните результат хотя бы одного упражнения.'); return }
    const results = []
    for (const work of selected) {
      const entry = actual[work.exercise_id]
      const reps = entry.reps.slice(0, entry.sets).map(value => Number(value))
      if (entry.reps.slice(0, entry.sets).some(value => value.trim() === '') || reps.some(value => !Number.isInteger(value) || value < 0 || value > 1000) || (entry.weight.trim() && (!Number.isFinite(Number(entry.weight)) || Number(entry.weight) < 0))) {
        setError('Заполните количество отдельно для каждого выполненного подхода и проверьте вес снаряда.')
        return
      }
      results.push({ exercise_id: work.exercise_id, ...(entry.performed ? { performed_exercise_id: entry.performed } : {}), completed_sets: entry.sets, reps_per_set: reps, weight_kg: entry.weight.trim() ? Number(entry.weight) : null })
    }
    finishingRef.current = true
    setDraftDirty(false)
    logMutation.mutate({ plan_id: plan.id, date: workoutDate, session_id: activeSession.id, results, difficulty, note })
  }
  function openSessionDetails(id: string) {
    const details = document.getElementById(`sport-session-${id}`) as HTMLDetailsElement | null
    if (!details) return
    details.open = true
    details.scrollIntoView?.({ behavior: "smooth", block: "start" })
  }
  function openJournal() {
    const journal = document.getElementById('workout-journal') as HTMLDetailsElement | null
    if (!journal) return
    setJournalOpen(true)
    journal.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }
  function nextExercise() {
    if (!activeSession || exerciseIndex >= activeSession.work.length - 1) return
    setRestUntil(Date.now() + activeSession.work[exerciseIndex].rest_seconds * 1000)
    setExerciseIndex(index => index + 1)
  }

  return <div className="healthPage">
    <div className="pageHeader"><div><h1>Спорт</h1><p>{plan ? 'Тренировка и прогресс по программе.' : 'Подберите программу под свою цель и условия.'}</p></div><Link className="secondaryButton" to="/health">К здоровью</Link></div>
    <img className="sportPhoto" src="/images/training-studio.webp" alt="Тренировочное пространство" width="1200" height="600"/><div className={`sportLayout${plan ? ' hasPlan' : ''}`}>
      <details id="sport-form" className="card sportForm" open={!plan || !!match}><summary>{plan ? 'Изменить программу' : 'Подобрать программу'}</summary><p className="muted">Выберите цель, место и удобный ритм занятий.</p>
        <div className="formStack">
          <Select label="Цель" value={answers.goal} onChange={event => update('goal', event.target.value as Answers['goal'])} options={[{value:'fat_loss_muscle_focus',label:'Снижение веса'},{value:'maintain',label:'Поддерживать форму'},{value:'strength_gain',label:'Увеличить силу'}]} />
          <Select label="Опыт тренировок" value={answers.level} onChange={event => { const level=event.target.value as Answers['level'];setAnswers(current=>({...current,level,minutes_per_session:level==='regular'?Math.max(60,current.minutes_per_session):current.minutes_per_session}));setMatch(null);setProposed(null) }} options={[{value:'returning',label:'Начинаю / после перерыва'},{value:'irregular',label:'Занимаюсь нерегулярно'},{value:'regular',label:'Занимаюсь регулярно'}]} />
          <p className="formHint">Опыт — это частота и устойчивость занятий, а не одно упражнение. Покажем цельную программу только при подходящем времени, месте и оборудовании.</p>
          <Select label="Место тренировки" value={answers.place} onChange={event => { const place=event.target.value as Place;setAnswers(current=>({...current,place,equipment:place==='gym'?['machines']:[]}));setMatch(null);setProposed(null) }} options={[{value:'home',label:'Дома'},{value:'outdoor',label:'На улице'},{value:'gym',label:'В зале'}]} />
          {answers.place!=='gym'&&<fieldset className="weekdayField"><legend>Что есть для тренировки</legend>{(Object.keys(equipmentNames) as Equipment[]).filter(key=>key!=='machines'&&(answers.place==='home'?key!=='low_bar':true)).map(key => <label key={key}><input type="checkbox" checked={answers.equipment.includes(key)} onChange={() => toggleEquipment(key)} />{equipmentNames[key]}</label>)}</fieldset>}
          <div className="formGrid"><Select label="Занятий в неделю" value={answers.days_per_week} onChange={event => { const value = Number(event.target.value); setAnswers(current => ({ ...current, days_per_week: value, weekdays: value === 2 ? [1, 4] : value === 3 ? [1, 3, 5] : [1, 2, 4, 6], minutes_per_session: value === 4 ? Math.max(60, current.minutes_per_session) : current.minutes_per_session })); setMatch(null) }} options={[{value:'2',label:'2'},{value:'3',label:'3'},{value:'4',label:'4 · PUSH/PULL/LEGS/UPPER'}]} /><Input label="Минут на занятие" type="number" min={10} max={180} value={answers.minutes_per_session} onChange={event => update('minutes_per_session', Number(event.target.value))} /></div>
          <fieldset className="weekdayField"><legend>Дни тренировок — выберите {answers.days_per_week}</legend>{days.map((label, index) => <label key={label}><input type="checkbox" checked={answers.weekdays.includes(index + 1)} onChange={() => toggleDay(index + 1)} />{label}</label>)}</fieldset>
          <label className="inlineCheck"><input type="checkbox" checked={answers.limitations} onChange={event => update('limitations', event.target.checked)} />Есть ограничения по здоровью или движениям</label>
          <p className="formHint">Если есть ограничения, готовую программу автоматически не назначаем. При боли, головокружении или недомогании остановите занятие.</p>
          <Button loading={matchMutation.isPending} disabled={answers.weekdays.length !== answers.days_per_week} onClick={() => matchMutation.mutate(answers)}>Подобрать программу</Button>
        </div>
      </details>
      <div className="healthContent sportResult">
        {error && <p role="alert" className="errorMessage">{error}</p>}{notice && <p role="status" className="successMessage">{notice}</p>}
        {catalog.isLoading || planQuery.isLoading ? <p className="muted">Загружаем материалы и ваш план…</p> : catalog.isError || planQuery.isError ? <p role="alert" className="errorMessage">Не удалось загрузить материалы или план. <button className="textButton" onClick={() => { void catalog.refetch(); void planQuery.refetch() }}>Повторить</button></p> : null}
        {match && !match.program && <section className="card sportOutcome"><h2>Для этих условий программы пока нет</h2>{match.reasons.map(reason => <p key={reason}>{reason}</p>)}{match.material && <><h3>{match.material.title}</h3><p>{match.material.intro}</p><ol className="healthList">{match.material.steps.map(step => <li key={step}>{step}</li>)}</ol><p><a href="#sport-library">Библиотека упражнений и техника</a> · <a href="#sport-guides">Все спортивные гайды</a></p></>}</section>}
        {match?.program && <section className="card"><h2>{match.program.title}</h2>{match.why?.map(reason => <p key={reason} className="muted">{reason}</p>)}<p>{match.program.overview}</p><button className="primaryButton" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate(false)}>Сохранить план</button></section>}
        {proposed && <section className="card"><h2>Заменить текущий план?</h2><p>Новая программа: {proposed.title}. Предыдущие записи тренировок сохранятся.</p><div className="healthActions"><button className="primaryButton" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate(true)}>Подтвердить замену</button><button className="secondaryButton" onClick={() => setProposed(null)}>Оставить прежний</button></div></section>}
        {plan?.revoked && <p role="alert" className="errorMessage">Эта программа отозвана. Перед следующей тренировкой выберите другую.</p>}
        {plan && <section className="card sportOutcome"><h2>Ваша тренировка</h2><p className="muted">{plan.program.duration_weeks} недели · {plan.answers.weekdays.map(day => days[day - 1]).join(' и ')} · начало {plan.started_on}</p><div className="sportQuickActions"><button className="primaryButton" onClick={openJournal}>Записать тренировку</button><a className="secondaryButton" href="#sport-sessions">Посмотреть занятия</a></div><details className="sportPlanInfo"><summary>О программе и настройках</summary><h3>{plan.program.title}</h3><p>{plan.program.overview}</p>{match && <p className="formHint">Сейчас действует этот план. Новый вариант можно сохранить после просмотра.</p>}<MaterialFit title={plan.program.title} alternatives={[]} reasons={['other','time','hard','equipment','goal']} onConfigure={()=>{const form=document.getElementById('sport-form') as HTMLDetailsElement | null;if(form){form.open=true;form.scrollIntoView?.({behavior:'smooth',block:'start'})}}}/></details></section>}
        {plan && planWeeks.length > 0 && <details className="secondarySection sportWeeks"><summary>Расписание и прогресс по неделям</summary><div className="sportWeeksHeader"><div><h2>План по неделям</h2><p className="muted">Неделя {currentWeek + 1} из {planWeeks.length}</p></div><span className="sportWeekCount">{workouts.data?.items.filter(item => item.plan_id === plan.id).length || 0} занятий записано</span></div>
          {planWeeks.map((week, index) => {
            const logs = (workouts.data?.items || []).filter(item => item.plan_id === plan.id && week.sessions.some(entry => entry.date === item.date && entry.sessionId === item.session_id))
            return <details className="sportWeek" key={week.number} open={index === currentWeek}><summary>Неделя {week.number}<span>{logs.length}/{week.sessions.length} занятий</span></summary><p className="sportWeekGuidance">{plan.program.progression[index] || 'Сохраняйте устойчивую технику и записывайте нагрузку.'}</p><div className="sportWeekSessions">{week.sessions.map(entry => { const session = activeSessions.find(item => item.id === entry.sessionId); const done = logs.some(item => item.date === entry.date && item.session_id === entry.sessionId); return <div key={entry.date + entry.sessionId} className="sportWeekSession"><span>{displayDate(entry.date)}</span><strong>{session?.title || entry.sessionId}</strong><span>{done ? 'Выполнено' : entry.date < today ? 'Не записано' : 'Запланировано'}</span><button className="textButton" type="button" aria-label={`Открыть занятие ${session?.title || entry.sessionId}`} onClick={() => openSessionDetails(entry.sessionId)}>Открыть</button></div> })}</div>{index === currentWeek && <p className="sportWeekAdvice">{weeklySportAdvice(logs, week.sessions.map(item => item.sessionId))}</p>}</details>
          })}
        </details>}
        {plan && today > lastPlanDate && <p className="healthNotice">Цикл завершён {lastPlanDate}. Чтобы повторить его, подберите программу с прежними ответами и подтвердите новый план. История сохранится.</p>}
        {!match && !plan && !planQuery.isLoading && <section className="card"><h2>План ещё не выбран</h2><p className="muted">Заполните анкету и нажмите «Подобрать программу». Вы увидите готовый план до сохранения.</p></section>}
      </div>
      <div className="healthContent sportDetails">
        {displayProgram && <><section className="card" id="sport-sessions"><h2>Ваши занятия</h2><p className="muted">Откройте занятие, чтобы увидеть упражнения и технику.</p>{displaySessions.map(session => <details className="healthSession" key={session.id} id={`sport-session-${session.id}`} open={!!requestedPlan && session.id === requestedSession}><summary>{session.title}</summary><p><strong>Разминка:</strong> {session.warmup}</p>{session.work.map(work => { const guide = catalog.data?.exercises[work.exercise_id]; return <div className="healthExercise" key={work.exercise_id}><h3>{guide?.name || work.exercise_id}</h3><p>{work.sets} {work.sets === 1 ? 'подход' : 'подхода'} · {work.reps} · отдых {work.rest_seconds} сек. {work.note}</p>{guide && <><p>{guide.technique}</p><p><strong>Частые ошибки:</strong> {guide.common_errors}</p><p><strong>Проще:</strong> {guide.easier_version}</p><p><strong>Замена:</strong> {guide.substitution}</p><a href={guide.source} target="_blank" rel="noreferrer">Источник техники</a></>}</div> })}<p><strong>Завершение:</strong> {session.cooldown}</p>{plan && !match && <button type="button" className="primaryButton" disabled={today < plan.started_on || today > lastPlanDate} onClick={() => { setSessionId(session.id); setWorkoutDate(today); openJournal() }}>Начать это занятие</button>}</details>)}</section>
          {!plan && <details className="card sportProgression"><summary>Как увеличивать нагрузку по неделям</summary><ol className="healthList">{displayProgram.progression.map(line => <li key={line}>{line}</li>)}</ol><p className="muted">Основа программы: {displayProgram.sources.map((source, index) => <a key={source} href={source} target="_blank" rel="noreferrer">источник {index + 1}{index < displayProgram.sources.length - 1 ? ', ' : ''}</a>)}</p></details>}</>}
        {plan && <details className="card sportJournal" id="workout-journal" open={journalOpen}><summary onClick={event => { event.preventDefault(); setJournalOpen(open => !open) }}>Записать тренировку</summary>
          {journalOpen && <div className="formGrid sportJournalSelection"><label>Дата<input type="date" value={workoutDate} max={today < lastPlanDate ? today : lastPlanDate} min={plan.started_on} onChange={event => setWorkoutDate(event.target.value)} /></label><label>Занятие<select value={activeSession?.id || ''} onChange={event => setSessionId(event.target.value)}>{activeSessions.map(session => <option key={session.id} value={session.id}>{session.title}</option>)}</select></label></div>}
          {journalOpen && draftQuery.isLoading && <p className="muted">Восстанавливаем занятие…</p>}
          {journalOpen && draftQuery.isError && <p role="alert" className="errorMessage">Не удалось открыть сохранённое занятие. <button className="textButton" onClick={() => void draftQuery.refetch()}>Повторить</button></p>}
          {journalOpen && draftQuery.isSuccess && draftLoadedKey === draftKey && <div className="formStack">
          <p className="sportDraftStatus" role="status">{draftError ? 'Не удалось сохранить черновик. Проверьте соединение.' : draftDirty || draftMutation.isPending ? 'Сохраняем черновик…' : draftQuery.data.draft ? 'Черновик сохранён. Можно продолжить позже.' : 'Результаты будут сохраняться по мере заполнения.'}</p>
          {draftError && <button type="button" className="textButton" onClick={() => { setDraftError(''); setDraftDirty(true) }}>Повторить сохранение</button>}
          <p className="formHint">Заполняйте только выполненные упражнения. Повторения или минуты указываются отдельно для каждого подхода.</p>
          {activeSession && <section className="sportWorkoutStep" aria-label="Активное занятие"><div className="sportWorkoutStepHeader"><div><span className="sportWorkoutSession">{activeSession.title}</span><strong>Упражнение {exerciseIndex + 1} из {activeSession.work.length}</strong></div><progress aria-label="Прогресс занятия" value={exerciseIndex + 1} max={activeSession.work.length}/></div><p><strong>Разминка:</strong> {activeSession.warmup}</p>{restUntil !== null && <div className="sportRestTimer" role="timer"><strong>Отдых: {String(Math.floor(restRemaining / 60)).padStart(2, '0')}:{String(restRemaining % 60).padStart(2, '0')}</strong><button type="button" className="secondaryButton" onClick={() => setRestUntil(null)}>Пропустить отдых</button></div>}</section>}
          {activeSession?.work.map((work, index) => {
            if (index !== exerciseIndex) return null
            const name = catalog.data?.exercises[work.exercise_id]?.name || work.exercise_id
            const entry = actual[work.exercise_id] || { sets: work.sets, reps: Array(work.sets).fill(''), weight: '' }
            const alternatives = catalog.data?.exercises[work.exercise_id]?.alternatives?.filter(option => option.places.includes(plan.answers.place) && option.required_equipment.every(item => plan.answers.equipment.includes(item)) && !activeSession.work.some(item => item.exercise_id === option.exercise_id)) || []
            return <section className="healthLogExercise sportActiveExercise" id={'assisted-exercise-'+work.exercise_id} key={work.exercise_id}><h3>{name}</h3><AssistantMaterialButton section={'sport'} material={{kind:'exercise',id:entry.performed || work.exercise_id}} stepId="sets" handlers={{technique:()=>{const details=document.getElementById('assisted-exercise-'+work.exercise_id)?.querySelector<HTMLDetailsElement>('details');if(details){details.open=true;details.scrollIntoView({block:'center'})}},sets:()=>document.getElementById('assisted-exercise-'+work.exercise_id)?.scrollIntoView({block:'start'})}}/><p>{work.sets} подхода · {work.reps} · отдых {work.rest_seconds} сек. {work.note}</p><details><summary>Техника и частые ошибки</summary><p>{catalog.data?.exercises[entry.performed || work.exercise_id]?.technique}</p><p>{catalog.data?.exercises[entry.performed || work.exercise_id]?.common_errors}</p></details>
              {alternatives.length > 0 && <label>Заменить упражнение: {name}<select value={entry.performed || ''} onChange={event => changeActual(work, current => ({ ...current, performed: event.target.value }))}><option value="">По плану: {name}</option>{alternatives.map(option => <option key={option.exercise_id} value={option.exercise_id}>{catalog.data?.exercises[option.exercise_id]?.name || option.exercise_id}</option>)}</select></label>}
              {entry.performed && <p className="formHint">Техника замены: {catalog.data?.exercises[entry.performed]?.technique} <a href={catalog.data?.exercises[entry.performed]?.source} target="_blank" rel="noreferrer">Источник</a></p>}
              <label>Выполнено подходов: {name}<input type="number" min="1" max={work.sets + 1} value={entry.sets} onChange={event => changeActual(work, current => { const sets = Math.max(1, Math.min(work.sets + 1, Number(event.target.value) || 1)); return { ...current, sets, reps: Array.from({ length: sets }, (_, position) => current.reps[position] || '') } })} /></label>
              <div className="formGrid">{Array.from({ length: entry.sets }, (_, position) => <div className="sportSetRow" key={position}><label>{name} — подход {position + 1} ({work.exercise_id === 'brisk_walk' ? 'минуты' : 'повторения'})<input type="number" min="0" max="1000" value={entry.reps[position] || ''} onChange={event => changeActual(work, current => { const reps = [...current.reps]; reps[position] = event.target.value; return { ...current, reps } })} placeholder="Фактически выполнено" /></label><button type="button" className="secondaryButton" disabled={!entry.reps[position]?.trim()||restUntil!==null} onClick={()=>setRestUntil(Date.now()+work.rest_seconds*1000)} aria-label={`Начать отдых после подхода ${position+1}`}>Отдых {work.rest_seconds} сек.</button></div>)}</div>
              <label>Вес снаряда, кг: {name} (если был)<input type="number" min="0" max="1000" step="0.5" value={entry.weight} onChange={event => changeActual(work, current => ({ ...current, weight: event.target.value }))} placeholder="Без веса" /></label>
            </section>
          })}
          {activeSession && <div className="sportStepActions">{exerciseIndex > 0 && <button type="button" className="secondaryButton" onClick={() => { setRestUntil(null); setExerciseIndex(index => index - 1) }}>Предыдущее упражнение</button>}{exerciseIndex < activeSession.work.length - 1 && <button type="button" className="primaryButton" onClick={nextExercise}>Следующее упражнение</button>}</div>}
          <label>Сложность от 1 до 10<input type="number" min="1" max="10" value={difficulty} onChange={event => { setDifficulty(Number(event.target.value)); setDraftDirty(true) }} /></label><label>Заметка<textarea value={note} onChange={event => { setNote(event.target.value); setDraftDirty(true) }} placeholder="Как прошло занятие" /></label><button className="primaryButton" disabled={logMutation.isPending || workoutDate > today || workoutDate > lastPlanDate || workoutDate < plan.started_on} onClick={saveWorkout}>Завершить тренировку</button></div>}</details>}
        {plan && <details className="card sportHistory"><summary>История тренировок</summary>{workouts.isLoading ? <p className="muted">Загружаем историю…</p> : workouts.isError ? <p role="alert" className="errorMessage">Не удалось загрузить историю. <button className="textButton" onClick={() => void workouts.refetch()}>Повторить</button></p> : workouts.data?.items.length ? <div>{workouts.data.items.map(item => <details className="healthSession" key={item.id}><summary>{item.date} · {item.program_title ? `${item.program_title} · ` : ''}{item.session_title || `занятие ${item.session_id}`}</summary><p>Сложность {item.difficulty}/10{item.note ? ` · ${item.note}` : ''}</p>{item.results?.map(result => <div className="healthExercise" key={result.exercise_id}><h3>{result.performed_exercise_name || catalog.data?.exercises[result.performed_exercise_id || result.exercise_id]?.name || result.performed_exercise_id || result.exercise_id}</h3>{result.performed_exercise_id && <p>Вместо: {catalog.data?.exercises[result.exercise_id]?.name || result.exercise_id}</p>}<p>Подходы: {result.completed_sets} · {result.exercise_id === 'brisk_walk' ? 'минуты' : 'повторения'}: {result.reps_per_set.join(', ')}{result.weight_kg !== null ? ` · вес: ${result.weight_kg} кг` : ''}</p></div>)}</details>)}</div> : <p className="muted">Выполненных занятий пока нет.</p>}</details>}
      </div>
    </div>
    <details className="secondarySection sportVideoCard"><summary>Дополнительная видеотренировка</summary><p className="muted">Дополнительный материал на английском. Не заменяет вашу программу и не адаптирован под ограничения здоровья.</p><MediaPlayer asset={sportVideo}/></details><SportLibrary exercises={catalog.data?.exercises || {}} loading={catalog.isLoading} error={catalog.isError} onRetry={() => void catalog.refetch()} />
    <details className="secondarySection"><summary>Советы по тренировкам</summary><Guides area="sport" /></details>
  </div>
}

function message(cause: unknown): string { return cause instanceof Error ? cause.message : 'Не удалось выполнить действие. Попробуйте ещё раз.' }
