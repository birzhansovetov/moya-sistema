import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError, api, json } from '../api'
import { useAuth } from '../auth'
import { readingGenres, type ReadingGenre } from '../readingGenres'
import './Onboarding.css'

type Sport = { goal: 'fat_loss_muscle_focus' | 'maintain' | 'strength_gain'; level: 'returning' | 'irregular' | 'regular'; place: 'home' | 'outdoor' | 'gym' | null; equipment: ('low_bar' | 'bench' | 'machines' | 'dumbbells' | 'bands' | 'barbell')[]; days_per_week: number; minutes_per_session: number; limitations: boolean; weekdays: number[] }
type Survey = {
  health: { sport: Sport | null; vegetarian: boolean; max_cooking_minutes: number; nutrition_goal: 'fat_loss' | 'maintain' | 'gain'; allergies: ('gluten' | 'milk' | 'egg' | 'fish')[] }
  education: { track: 'java' | 'go' | 'reading' | 'both' | 'go-reading' | 'none'; reading_genres: ReadingGenre[]; minutes: 15 | 30 | 45 | 60; weekdays: number[] }
  profession: { track: 'java-backend' | 'none'; minutes: 15 | 30 | 45 | 60; weekdays: number[] }
  languages: { course_id: 'english' | 'kazakh' | 'korean' | 'turkish' | 'spanish' | 'none'; level: 'A1' | 'A2' | 'B1' | 'B2' | 'none'; goal: 'general' | 'work' | 'travel' | 'project'; minutes: 15 | 30 | 45 | 60; weekdays: number[] }
  finance: { currency: 'KZT' | 'USD' | 'EUR' | 'RUB'; focus: 'record' | 'review' }
  personal: { focus: 'journal' | 'habits' | 'reading' }
}
type Candidate = { kind: string; id: string; version: string; digest: string; title: string; reason: string }
type AiSuggestion = { source: 'local_ai' | 'rules'; progress_considered?: boolean; recommendations: Record<string, { id: string; title: string; reason: string; why?: string; source: 'local_ai' | 'rules' }> }
type Preview = { preview_id?: string; existing_plans?: Record<string, string>; candidates_by_sphere?: Record<string, Candidate[]>; candidate_counts?: Record<string, number>; areas: Record<string, { title: string; sport?: { status: string; title?: string; reason?: string; material?: { title: string; route: string } }; recipes?: { count: number; example?: string | null }; study?: { status: string; lesson_count?: number; reason?: string; material?: { title: string; route: string } }; book?: { title: string; author: string }; guide?: { title: string } }> }
function correctionStep(reason: string) {
  if (reason.includes('цели')) return 0
  if (reason.includes('неделю') || reason.includes('день отдыха') || reason.includes('минут')) return 2
  return 1
}
const sphereStep: Record<string, number> = { health: 0, education: 4, profession: 6, languages: 7, finance: 9, personal: 10 }
const initial: Survey = {
  health: { sport: { goal: 'fat_loss_muscle_focus', level: 'returning', place: null, equipment: [], days_per_week: 2, minutes_per_session: 45, limitations: false, weekdays: [1, 4] }, vegetarian: false, max_cooking_minutes: 45, nutrition_goal: 'maintain', allergies: [] },
  education: { track: 'java', reading_genres: ['classic'], minutes: 30, weekdays: [0, 2, 4] },
  profession: { track: 'java-backend', minutes: 30, weekdays: [1, 3] },
  languages: { course_id: 'english', level: 'A2', goal: 'general', minutes: 30, weekdays: [0, 2, 4] },
  finance: { currency: 'KZT', focus: 'record' }, personal: { focus: 'journal' },
}
const steps = [
  { sphere: 'Здоровье', title: 'Какая у вас цель?', lead: 'Выберите то, над чем хотите работать в тренировках.' },
  { sphere: 'Здоровье', title: 'Где вам удобно заниматься?', lead: 'Место, опыт и оборудование определяют подходящую программу.' },
  { sphere: 'Здоровье · спорт', title: 'Какой ритм тренировок вам подходит?', lead: 'Укажите время и дни, в которые сможете заниматься.' },
  { sphere: 'Здоровье · питание', title: 'Какие рецепты вам подходят?', lead: 'Покажем блюда с учётом ваших предпочтений и времени на готовку.' },
  { sphere: 'Обучение', title: 'Что хотите изучать?', lead: 'Подберём готовый курс и книгу по вашему интересу.' },
  { sphere: 'Обучение', title: 'Когда будете учиться?', lead: 'Выберите посильный ритм. Его можно изменить позже.' },
  { sphere: 'Профессия', title: 'Куда двигаться в профессии?', lead: 'Сейчас доступен готовый маршрут Java backend.' },
  { sphere: 'Языки', title: 'Какой язык хотите изучать?', lead: 'Выберите один язык и начальный уровень. Позже выбор можно изменить.' },
  { sphere: 'Языки', title: 'Как часто заниматься языком?', lead: 'Небольшие регулярные занятия помогут держать темп.' },
  { sphere: 'Финансы', title: 'Что важно в финансах?', lead: 'Начните с учёта расходов или разбора месяца.' },
  { sphere: 'Личное', title: 'Что хотите развивать?', lead: 'Выберите подходящий способ наблюдать за своим прогрессом.' },
] as const
const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="onboardingField"><span>{label}</span>{children}</label> }
function Choices<T extends string>({ label, value, options, onChange }: { label: string; value: T | null; options: readonly { value: T; title: string; detail?: string }[]; onChange: (value: T) => void }) {
  return <fieldset className="onboardingChoiceField"><legend>{label}</legend><div className="onboardingChoices">{options.map(option => <label key={option.value} className="onboardingChoice"><input type="radio" name={label} checked={value === option.value} onChange={() => onChange(option.value)} /><span><strong>{option.title}</strong>{option.detail && <small>{option.detail}</small>}</span></label>)}</div></fieldset>
}
function DayPicker({ value, onChange, sport = false }: { value: number[]; onChange: (days: number[]) => void; sport?: boolean }) {
  return <div className="onboardingDays" aria-label="Дни занятий">{dayNames.map((name, index) => { const day = sport ? index + 1 : index; return <button type="button" key={name} aria-pressed={value.includes(day)} onClick={() => { const next = value.includes(day) ? value.filter(item => item !== day) : [...value, day].sort(); if (next.length && (!sport || next.length <= 4)) onChange(next) }}>{name}</button> })}</div>
}
export function OnboardingPage() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const sportFocus = new URLSearchParams(location.search).get('focus')
  const [answers, setAnswers] = useState<Survey>(initial)
  const [step, setStep] = useState(0)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [aiSuggestion, setAiSuggestion] = useState<AiSuggestion | null>(null)
  const [aiChecking, setAiChecking] = useState(false)
  const [selected, setSelected] = useState<Record<string, string>>({})
  const [skipped, setSkipped] = useState<string[]>([])
  const [showAll, setShowAll] = useState<string[]>([])
  const [confirmReplace, setConfirmReplace] = useState(false)
  const [quickPreview, setQuickPreview] = useState<Preview | null>(null)
  const [checking, setChecking] = useState(false)
  const [checkError, setCheckError] = useState('')
  const [checkRetry, setCheckRetry] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loadingSaved, setLoadingSaved] = useState(true)
  const [hasSavedAnswers, setHasSavedAnswers] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [reconfirmation, setReconfirmation] = useState(false)
  const [archive, setArchive] = useState<{ kind: 'sport' | 'study'; plan_id: string; title: string }[]>([])
  const [loadRetry, setLoadRetry] = useState(0)
  const draftTouched = useRef(false)
  const sportReview = hasSavedAnswers && (sportFocus === 'sport-schedule' || sportFocus === 'sport-program')
  useEffect(() => {
    const previewId = preview?.preview_id
    if (!previewId) { setAiSuggestion(null); setAiChecking(false); return }
    let active = true
    setAiSuggestion(null)
    setAiChecking(true)
    api<AiSuggestion>('/onboarding/assist', json('POST', { preview_id: previewId }))
      .then(result => { if (active) setAiSuggestion(result) })
      .catch(() => { if (active) setAiSuggestion(null) })
      .finally(() => { if (active) setAiChecking(false) })
    return () => { active = false }
  }, [preview?.preview_id])
  useEffect(() => { if (!user?.onboarding_complete) return; api<{ items: typeof archive }>('/onboarding/archive').then(result => setArchive(result.items)).catch(() => {}) }, [user?.onboarding_complete])
  async function restorePlan(item: typeof archive[number]) {
    if (!window.confirm(`Восстановить «${item.title}»? Текущий план останется в истории вместе с прогрессом.`)) return
    try { await api('/onboarding/restore', json('POST', { kind: item.kind, plan_id: item.plan_id, confirm_progress: true })); setArchive(previous => previous.filter(entry => entry.plan_id !== item.plan_id)); setError('План восстановлен. Откройте соответствующий раздел.') }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось восстановить план') }
  }
  useEffect(() => { let active = true; setLoadingSaved(true); setLoadError(''); api<{ answers: Survey | null; needs_reconfirmation?: boolean }>('/onboarding').then(result => {
    if (active && result.needs_reconfirmation) { setReconfirmation(true); return }
    if (active && !draftTouched.current && result.answers) {
      setHasSavedAnswers(true)
      setAnswers({ ...result.answers, languages: { ...result.answers.languages, course_id: result.answers.languages.course_id || (result.answers.languages.level === 'none' ? 'none' : 'english') }, health: { ...result.answers.health,
      nutrition_goal: result.answers.health.nutrition_goal || 'maintain', allergies: result.answers.health.allergies || [],
      sport: result.answers.health.sport ? { ...result.answers.health.sport,
        level: (result.answers.health.sport.level as string) === 'beginner' ? 'returning' : (result.answers.health.sport.level as string) === 'intermediate' ? 'irregular' : result.answers.health.sport.level,
        ...(result.answers.health.sport.place === 'home' ? { place: null, equipment: [] } : {}),
      } : null } })
      if (result.answers.health.sport && sportFocus === 'sport-program') setStep(1)
      if (result.answers.health.sport && sportFocus === 'sport-schedule')
        setStep(result.answers.health.sport.place === 'home' ? 1 : 2)
    }
  }).catch(() => { if (active) setLoadError('Не удалось загрузить сохранённые ответы.') }).finally(() => { if (active) setLoadingSaved(false) }); return () => { active = false } }, [loadRetry])
  const update = <K extends keyof Survey>(area: K, change: Partial<Survey[K]>) => { draftTouched.current = true; setAnswers(previous => ({ ...previous, [area]: { ...previous[area], ...change } })); setPreview(null); setError('') }
  const sport = answers.health.sport
  const sportUpdate = (change: Partial<Sport>) => update('health', { sport: sport ? { ...sport, ...change } : null })
  useEffect(() => {
    if (step > 2 || !answers.health.sport?.place) { setChecking(false); setQuickPreview(null); setCheckError(''); return }
    if (answers.health.sport.minutes_per_session < 10 || answers.health.sport.minutes_per_session > 180) return
    const controller = new AbortController()
    setChecking(true)
    setQuickPreview(null)
    setCheckError('')
    const timer = window.setTimeout(() => {
      api<{ program: { title: string } | null; reasons: string[]; material?: { title: string } }>('/health/sport/match', { ...json('POST', answers.health.sport), signal: controller.signal })
        .then(result => { if (!controller.signal.aborted) setQuickPreview({ areas: { health: { title: 'Здоровье', sport: result.program ? { status: 'matched', title: result.program.title } : { status: 'unavailable', reason: result.reasons.join(' '), material: result.material ? { title: result.material.title, route: '/health/sport#sport-guides' } : undefined } } } }) })
        .catch(cause => { if (!controller.signal.aborted) setCheckError(cause instanceof Error ? cause.message : 'Не удалось проверить программу. Попробуйте ещё раз позже.') })
        .finally(() => { if (!controller.signal.aborted) setChecking(false) })
    }, 250)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [answers.health.sport, step, checkRetry])
  async function showPreview() { if (sport && !sport.place) { setStep(1); setError('Выберите место тренировки.'); return } setBusy(true); setError(''); try { const result = await api<Preview>('/onboarding/preview', json('POST', answers)); setPreview(result); setSelected(Object.fromEntries(Object.entries(result.candidates_by_sphere || {}).filter(([sphere, items]) => sphere !== 'health_recipes' && items.length && (!sportReview || sphere === 'health')).map(([sphere, items]) => [sphere, items[0].id]))); setSkipped(Object.keys(result.areas).filter(sphere => (sportReview && sphere !== 'health') || !(result.candidates_by_sphere?.[sphere]?.length))); setShowAll([]); setStep(steps.length) } catch (cause) { setError(cause instanceof ApiError && cause.status === 429 ? 'Слишком много предпросмотров за час. Попробуйте позже.' : cause instanceof Error ? cause.message : 'Не удалось подобрать материалы') } finally { setBusy(false) } }
  async function revealChoices(sphere: string) { if (!preview?.preview_id) return; try { const result = await api<{ candidates_by_sphere: Record<string, Candidate[]> }>('/onboarding/preview/choices', json('POST', { preview_id: preview.preview_id })); setPreview(previous => previous ? { ...previous, candidates_by_sphere: result.candidates_by_sphere } : previous); setShowAll(previous => [...previous, sphere]) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось загрузить варианты') } }
  async function applyAiSuggestion() {
    if (!preview?.preview_id || aiSuggestion?.source !== 'local_ai') return
    const proposed = Object.fromEntries(Object.entries(aiSuggestion.recommendations).filter(([sphere, item]) => item.source === 'local_ai' && (!sportReview || sphere === 'health')).map(([sphere, item]) => [sphere, item.id]))
    const hidden = Object.entries(proposed).filter(([sphere, id]) => !(preview.candidates_by_sphere?.[sphere] || []).some(item => item.id === id)).map(([sphere]) => sphere)
    if (hidden.length) {
      try {
        const result = await api<{ candidates_by_sphere: Record<string, Candidate[]> }>('/onboarding/preview/choices', json('POST', { preview_id: preview.preview_id }))
        setPreview(previous => previous ? { ...previous, candidates_by_sphere: result.candidates_by_sphere } : previous)
        setShowAll(previous => [...new Set([...previous, ...hidden])])
      } catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось загрузить варианты'); return }
    }
    setSelected(previous => ({ ...previous, ...proposed }))
    setSkipped(previous => previous.filter(sphere => !proposed[sphere]))
  }
  async function start() {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      if (preview?.preview_id) {
        await api('/onboarding/start', json('POST', { preview_id: preview.preview_id, selected, skipped, confirm_replace: confirmReplace }))
        const profile = await api<{ user: NonNullable<typeof user> }>('/auth/me')
        setUser(profile.user)
      } else {
        const result = await api<{ user: NonNullable<typeof user> }>('/onboarding/start?confirm_replace=true', json('POST', answers))
        setUser(result.user)
      }
      navigate('/sections', { replace: true })
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409 && preview?.preview_id) {
        if (cause.message.includes('Подтвердите замену')) {
          setError(cause.message)
        } else {
          await showPreview()
          setError(`${cause.message} Подбор обновлён; проверьте выбор ещё раз.`)
        }
      } else {
        if (preview?.preview_id) {
          try {
            const state = await api<{ committed: boolean }>('/onboarding/result', json('POST', { preview_id: preview.preview_id }))
            if (state.committed) {
              const profile = await api<{ user: NonNullable<typeof user> }>('/auth/me')
              setUser(profile.user)
              navigate('/sections', { replace: true })
              return
            }
          } catch { /* keep draft and allow safe retry */ }
        }
        setError(cause instanceof Error ? cause.message : 'Не удалось сохранить подбор')
      }
    } finally { setBusy(false) }
  }
  return <main className="onboardingPage"><div className="onboardingFrame">
    <header className="onboardingHeader"><span className="onboardingBrand">Моя система</span><span>{step === steps.length ? 'Ваш подбор' : `Шаг ${step + 1} из ${steps.length}`}</span></header>
    <div className="onboardingProgress" role="progressbar" aria-label="Прогресс анкеты" aria-valuenow={step} aria-valuemin={0} aria-valuemax={steps.length}><span style={{ width: `${step / steps.length * 100}%` }} /></div>
    {loadingSaved && <p className="onboardingHint">Загружаем ваши ответы…</p>}
    {!!archive.length && <section className="onboardingResult" aria-label="Недавние планы"><h2>Недавние планы</h2><p>В течение 7 дней можно вернуть прежний план. Текущий прогресс сохранится в истории.</p>{archive.map(item => <p key={item.plan_id}>{item.title} <button type="button" className="textButton" onClick={() => void restorePlan(item)}>Восстановить</button></p>)}</section>}
    {loadError && <p role="alert" className="errorMessage">{loadError} <button type="button" className="textButton" onClick={() => setLoadRetry(value => value + 1)}>Повторить загрузку</button></p>}
    {step < steps.length ? <>
      <p className="onboardingEyebrow">{steps[step].sphere}</p><h1>{steps[step].title}</h1><p className="onboardingLead">{steps[step].lead}</p>
      <section className="onboardingCard" aria-label={steps[step].title}>
        {step === 0 && <>
          <Choices label="Тренировки" value={sport ? 'yes' : 'no'} options={[{ value: 'yes', title: 'Хочу подобрать программу', detail: 'Покажем готовые тренировки по вашим условиям' }, { value: 'no', title: 'Пока без тренировок' }]} onChange={value => update('health', { sport: value === 'yes' ? initial.health.sport : null })} />
          {sport && <Choices label="Главная цель" value={sport.goal} options={[{ value: 'fat_loss_muscle_focus', title: 'Снизить вес и сохранить мышцы', detail: 'Нагрузка с учётом опыта и условий занятий' }, { value: 'maintain', title: 'Поддерживать форму', detail: 'Регулярная нагрузка на всё тело' }, { value: 'strength_gain', title: 'Стать сильнее', detail: 'Силовые упражнения с постепенным увеличением нагрузки' }]} onChange={goal => sportUpdate({ goal })} />}
        </>}
        {step === 1 && (sport ? <>
          <Choices label="Ваш опыт" value={sport.level} options={[{ value: 'returning', title: 'Начинаю или возвращаюсь', detail: 'Долгий перерыв или первый устойчивый ритм' }, { value: 'irregular', title: 'Тренировался нерегулярно', detail: 'Техника знакома, но расписание было с перерывами' }, { value: 'regular', title: 'Занимался регулярно', detail: 'Несколько месяцев системных тренировок' }]} onChange={level => sportUpdate({ level })} />
          <Choices label="Место занятий" value={sport.place} options={[{ value: 'home', title: 'Дома' }, { value: 'outdoor', title: 'На улице' }, { value: 'gym', title: 'В зале' }]} onChange={place => sportUpdate({ place, equipment: place === 'gym' ? ['machines'] : [] })} />
          {(sport.place === 'home' || sport.place === 'outdoor') && <div className="onboardingField onboardingWide"><span>Что есть под рукой</span><div className="onboardingEquipment">{([['low_bar','Турник'],['bench','Скамья'],['dumbbells','Гантели'],['bands','Резинки'],['barbell','Штанга']] as const).map(([id,label]) => <label key={id}><input type="checkbox" checked={sport.equipment.includes(id)} onChange={event => sportUpdate({ equipment: event.target.checked ? [...sport.equipment, id] : sport.equipment.filter(item => item !== id) })} />{label}</label>)}</div></div>}
          <label className="onboardingCheck"><input type="checkbox" checked={sport.limitations} onChange={event => sportUpdate({ limitations: event.target.checked })} />Есть ограничения для тренировок</label>
        </> : <p className="onboardingHint">Тренировки пропущены. Вы сможете добавить программу позже.</p>)}
        {step === 2 && (sport ? <><Field label="Минут на тренировку"><input type="number" min="10" max="180" value={sport.minutes_per_session} onChange={event => sportUpdate({ minutes_per_session: Number(event.target.value) })} /></Field><div className="onboardingField onboardingWide"><span>Дни тренировок · до четырёх</span><DayPicker sport value={sport.weekdays} onChange={weekdays => sportUpdate({ weekdays, days_per_week: weekdays.length })} /><small>Для четырёхдневной программы выберите Пн, Вт, Чт и Сб; нужно от 60 минут.</small></div></> : <p className="onboardingHint">Тренировки пока пропущены. На следующем шаге подберём рецепты.</p>)}
        {step === 3 && <>
          <Choices label="Цель питания" value={answers.health.nutrition_goal} options={[{ value: 'maintain', title: 'На каждый день', detail: 'Разные блюда без строгой цели по весу' }, { value: 'fat_loss', title: 'Снижение веса', detail: 'Сначала более белковые блюда относительно калорийности' }, { value: 'gain', title: 'Набор массы', detail: 'Сначала более калорийные и белковые блюда' }]} onChange={nutrition_goal => update('health', { nutrition_goal })} />
          <label className="onboardingCheck"><input type="checkbox" checked={answers.health.vegetarian} onChange={event => update('health', { vegetarian: event.target.checked })} />Подбирать вегетарианские рецепты</label>
          <div className="onboardingField onboardingWide"><span>Что исключить из-за аллергии</span><div className="onboardingEquipment">{([['gluten','Глютен'],['milk','Молоко'],['egg','Яйца'],['fish','Рыба']] as const).map(([id,label]) => <label key={id}><input type="checkbox" checked={answers.health.allergies.includes(id)} onChange={event => update('health', { allergies: event.target.checked ? [...answers.health.allergies, id] : answers.health.allergies.filter(item => item !== id) })} />{label}</label>)}</div></div>
          <Field label="Максимум минут на приготовление"><input type="number" min="5" max="180" value={answers.health.max_cooking_minutes} onChange={event => update('health', { max_cooking_minutes: Number(event.target.value) })} /></Field>
        </>}
        {step === 4 && <>
          <Choices label="Направление" value={answers.education.track} options={[{ value: 'java', title: 'Java' }, { value: 'go', title: 'Go' }, { value: 'reading', title: 'Чтение' }, { value: 'both', title: 'Java и чтение' }, { value: 'go-reading', title: 'Go и чтение' }, { value: 'none', title: 'Пока не выбираю' }]} onChange={track => update('education', { track })} />
          {(['reading', 'both', 'go-reading'] as const).includes(answers.education.track as 'reading' | 'both' | 'go-reading') && <fieldset className="onboardingChoiceField"><legend>Какие жанры вам нравятся? Можно выбрать несколько.</legend><div className="onboardingChoices">{readingGenres.map(genre => <label key={genre.id} className="onboardingChoice"><input type="checkbox" checked={answers.education.reading_genres.includes(genre.id)} onChange={event => update('education', { reading_genres: event.target.checked ? [...answers.education.reading_genres, genre.id] : answers.education.reading_genres.filter(item => item !== genre.id) })} /><span><strong>{genre.label}</strong></span></label>)}</div></fieldset>}
        </>}
        {step === 5 && <><Field label="Минут на учёбу"><select value={answers.education.minutes} onChange={event => update('education', { minutes: Number(event.target.value) as Survey['education']['minutes'] })}>{[15, 30, 45, 60].map(n => <option key={n}>{n}</option>)}</select></Field><div className="onboardingField onboardingWide"><span>Дни учёбы</span><DayPicker value={answers.education.weekdays} onChange={weekdays => update('education', { weekdays })} /></div></>}
        {step === 6 && <><Choices label="Профессиональное направление" value={answers.profession.track} options={[{ value: 'java-backend', title: 'Java backend', detail: 'Готовый маршрут с уроками и практикой' }, { value: 'none', title: 'Пока не выбираю' }]} onChange={track => update('profession', { track })} />{answers.profession.track !== 'none' && <><Field label="Минут на занятие"><select value={answers.profession.minutes} onChange={event => update('profession', { minutes: Number(event.target.value) as Survey['profession']['minutes'] })}>{[15, 30, 45, 60].map(n => <option key={n}>{n}</option>)}</select></Field><div className="onboardingField onboardingWide"><span>Дни занятий</span><DayPicker value={answers.profession.weekdays} onChange={weekdays => update('profession', { weekdays })} /></div></>}</>}
        {step === 7 && <><Choices label="Выберите язык" value={answers.languages.course_id} options={[{ value: 'english', title: 'Английский · A2–B2' }, { value: 'kazakh', title: 'Казахский · A1–B2' }, { value: 'korean', title: 'Корейский · A1–B2' }, { value: 'turkish', title: 'Турецкий · A1–B2' }, { value: 'spanish', title: 'Испанский · A1–B2' }, { value: 'none', title: 'Пока пропустить' }]} onChange={course_id => update('languages', { course_id, level: course_id === 'none' ? 'none' : course_id === 'english' && (answers.languages.level === 'A1' || answers.languages.level === 'none') ? 'A2' : answers.languages.level === 'none' ? 'A1' : answers.languages.level })} />{answers.languages.course_id !== 'none' && <><Choices label="Текущий уровень" value={answers.languages.level} options={[...(answers.languages.course_id === 'english' ? [] : [{ value: 'A1' as const, title: 'A1 · начинаю с основ' }]), { value: 'A2' as const, title: 'A2 · основы знакомы' }, { value: 'B1' as const, title: 'B1 · могу объясниться' }, { value: 'B2' as const, title: 'B2 · уверенно общаюсь' }]} onChange={level => update('languages', { level })} /><Choices label="Зачем нужен язык" value={answers.languages.goal} options={[{ value: 'general', title: 'Для себя' }, { value: 'work', title: 'Для работы' }, { value: 'travel', title: 'Для поездок' }, { value: 'project', title: 'Для проекта' }]} onChange={goal => update('languages', { goal })} /></>}</>}
        {step === 8 && (answers.languages.course_id !== 'none' ? <><Field label="Минут на занятие"><select value={answers.languages.minutes} onChange={event => update('languages', { minutes: Number(event.target.value) as Survey['languages']['minutes'] })}>{[15, 30, 45, 60].map(n => <option key={n}>{n}</option>)}</select></Field><div className="onboardingField onboardingWide"><span>Дни занятий</span><DayPicker value={answers.languages.weekdays} onChange={weekdays => update('languages', { weekdays })} /></div></> : <p className="onboardingHint">Язык пока пропущен. Позже вы сможете вернуться к выбору.</p>)}
        {step === 9 && <><Field label="Валюта расходов"><select value={answers.finance.currency} onChange={event => update('finance', { currency: event.target.value as Survey['finance']['currency'] })}><option>KZT</option><option>USD</option><option>EUR</option><option>RUB</option></select></Field><Choices label="Первый шаг" value={answers.finance.focus} options={[{ value: 'record', title: 'Записывать расходы' }, { value: 'review', title: 'Разбирать расходы за месяц' }]} onChange={focus => update('finance', { focus })} /></>}
        {step === 10 && <Choices label="Личный фокус" value={answers.personal.focus} options={[{ value: 'journal', title: 'Вести дневник' }, { value: 'habits', title: 'Работать с привычками' }, { value: 'reading', title: 'Размышлять о прочитанном' }]} onChange={focus => update('personal', { focus })} />}
      </section>
      {step <= 2 && sport && <aside className={`onboardingMatch ${quickPreview?.areas.health.sport?.status === 'matched' ? 'isMatched' : ''}`} aria-live="polite"><strong>Подбор тренировки</strong>{!sport.place ? <p>Выберите место занятий на следующем шаге. Тогда покажем подходящую программу.</p> : checking ? <p>Проверяем ваши ответы…</p> : checkError ? <><p role="alert">{checkError}</p><button type="button" className="textButton" onClick={() => setCheckRetry(value => value + 1)}>Проверить ещё раз</button></> : quickPreview?.areas.health.sport?.status === 'matched' ? <p>Подходит: {quickPreview.areas.health.sport.title}</p> : quickPreview?.areas.health.sport?.reason ? <><p>{quickPreview.areas.health.sport.reason}</p>{quickPreview.areas.health.sport.material && <p>Готовый материал: {quickPreview.areas.health.sport.material.title}</p>}{correctionStep(quickPreview.areas.health.sport.reason) !== step && <button type="button" className="textButton" onClick={() => setStep(correctionStep(quickPreview.areas.health.sport!.reason!))}>Перейти к нужному вопросу</button>}</> : null}</aside>}
      <div className="onboardingActions">{step > 0 && <button className="secondaryButton" onClick={() => setStep(step - 1)}>Назад</button>}{hasSavedAnswers && sport && sportFocus && (step === 1 || step === 2) && <button className="secondaryButton" onClick={() => void showPreview()} disabled={busy || loadingSaved || !sport.place}>Посмотреть обновлённый план</button>}<button className="primaryButton" onClick={() => step === steps.length - 1 ? void showPreview() : setStep(step + 1)} disabled={busy || loadingSaved || !!loadError || (step === 1 && !!sport && !sport.place) || (step === 4 && ['reading', 'both', 'go-reading'].includes(answers.education.track) && !answers.education.reading_genres.length)}>{busy ? 'Подбираем…' : step === steps.length - 1 ? 'Посмотреть подбор' : 'Продолжить'}</button></div>
    </> : <><p className="onboardingEyebrow">Ваш подбор</p><h1>Планы и материалы для вас</h1><p className="onboardingLead">Проверьте, что подходит. Если для ответа нет готовой программы, мы скажем об этом прямо.</p>{hasSavedAnswers && sportFocus && <p className="onboardingHint">Пересматривается только спорт. Остальные планы сохранятся.</p>}
      {aiChecking && <p className="onboardingHint" aria-live="polite">Локальный ИИ проверяет варианты…</p>}
      {aiSuggestion?.source === 'local_ai' && (!sportReview || aiSuggestion.recommendations.health?.source === 'local_ai') && <section className="onboardingAi" aria-label="Предложение локального ИИ"><strong>Локальный ИИ предлагает</strong><p>Выбор сделан только из проверенных материалов. Он не сохраняется без вашего подтверждения.</p>{aiSuggestion.progress_considered && <p>Учтены записанные тренировки и занятия за последнюю завершённую неделю.</p>}<ul>{Object.entries(aiSuggestion.recommendations).filter(([sphere, item]) => item.source === 'local_ai' && (!sportReview || sphere === 'health')).map(([sphere, item]) => <li key={sphere}>{preview?.areas[sphere]?.title}: {item.title} · {item.why || item.reason}</li>)}</ul><button type="button" className="secondaryButton" onClick={() => void applyAiSuggestion()}>Выбрать предложение ИИ</button></section>}
      <div className="onboardingResults">{preview && Object.entries(preview.areas).map(([key, area]) => <article className="onboardingResult" key={key}><div className="onboardingResultHeading"><h2>{area.title}</h2><button type="button" className="textButton" onClick={() => setStep(key === 'health' && area.sport?.status === 'unavailable' ? correctionStep(area.sport.reason || '') : sphereStep[key] ?? 0)}>Изменить</button></div>{area.sport && <p>{area.sport.status === 'matched' ? `Программа: ${area.sport.title}` : area.sport.reason}</p>}{area.sport?.material && <p>Готовый материал: <Link to={area.sport.material.route}>{area.sport.material.title}</Link></p>}{area.recipes && <p>Подходящих рецептов: {area.recipes.count}{area.recipes.example ? ` · первым: «${area.recipes.example}»` : ''}</p>}{area.study && <p>{area.study.status === 'matched' ? `Готовый маршрут: ${area.study.lesson_count} уроков` : area.study.reason}</p>}{area.study?.material && <p>Готовый материал: <Link to={area.study.material.route}>{area.study.material.title}</Link></p>}{key === 'education' && ['reading', 'both', 'go-reading'].includes(answers.education.track) && (area.book ? <p>Книга: «{area.book.title}» — {area.book.author}</p> : <p>По выбранным жанрам готовой книги пока нет. <Link to="/education/reading">Открыть всю библиотеку</Link></p>)}{area.guide && <p>{area.guide.title}</p>}</article>)}</div>{preview?.preview_id && <section className="onboardingSelection" aria-label="Выбор планов">{Object.entries(preview.areas).map(([sphere, area]) => { const options = preview.candidates_by_sphere?.[sphere] || []; const isSkipped = skipped.includes(sphere); return <fieldset key={sphere} className="onboardingResult"><legend>{area.title}</legend><label className="onboardingCheck"><input type="checkbox" checked={isSkipped} onChange={event => { setSkipped(previous => event.target.checked ? [...previous, sphere] : previous.filter(item => item !== sphere)); if (event.target.checked) setSelected(previous => { const next = { ...previous }; delete next[sphere]; return next }); else if (options.length) setSelected(previous => ({ ...previous, [sphere]: options[0].id })) }} />Не создавать план</label>{!isSkipped && options.map((item, index) => <label key={item.id} className="onboardingCandidate"><input type="radio" name={`plan-${sphere}`} checked={selected[sphere] === item.id} onChange={() => setSelected(previous => ({ ...previous, [sphere]: item.id }))} /><span><strong>{item.title}</strong><small>{index === 0 ? `Рекомендуем · ${item.reason}` : item.reason}</small></span></label>)}{!isSkipped && (preview.candidate_counts?.[sphere] || 0) > options.length && !showAll.includes(sphere) && <button type="button" className="textButton" onClick={() => void revealChoices(sphere)}>Показать весь список</button>}{!options.length && !isSkipped && <p>Готового плана для этих ответов пока нет.</p>}</fieldset> })}{preview.existing_plans && Object.entries(preview.existing_plans).filter(([sphere]) => !!selected[sphere] && !skipped.includes(sphere)).map(([sphere, title]) => <p key={sphere} className="onboardingHint">Будет заменён: {preview.areas[sphere]?.title} — {title}. Прогресс сохранится.</p>)}<label className="onboardingCheck"><input type="checkbox" checked={confirmReplace} onChange={event => setConfirmReplace(event.target.checked)} />Подтверждаю замену выбранных планов. Прогресс прежних планов останется в истории.</label></section>}<div className="onboardingActions"><button className="primaryButton" onClick={() => void start()} disabled={busy}>{busy ? 'Сохраняем…' : 'Начать'}</button></div></>}
    {reconfirmation && <p role="alert" className="errorMessage">Анкета была создана в прежней версии. Заполните вопросы заново, чтобы подтвердить подбор; старые ответы не будут перенесены автоматически.</p>}
    {error && <p role="alert" className="errorMessage">{error}</p>}
  </div></main>
}
