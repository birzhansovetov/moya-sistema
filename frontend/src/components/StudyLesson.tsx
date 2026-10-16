import {Pronunciation} from './Pronunciation'
import {AssistantMaterialButton} from './SectionAssistant'
import {useRef,useState} from 'react'
import {useMutation,useQuery} from '@tanstack/react-query'
import {api,json} from '../api'
import {StudyHelp} from './StudyHelp'
import {newStudyDraft,type StudyDraftStore} from '../useStudyDrafts'
import {languageCourses,type Attempt,type Lesson,type StudyPlan} from '../studyTypes'
import s from '../pages/Study.module.css'
import f from '../pages/Journal.module.css'
function GrammarPractice({lesson,version,courseId}:{lesson:Lesson;version:string;courseId:string}){
 const [answer,setAnswer]=useState('')
 const check=useMutation({mutationFn:()=>api<{correct:boolean;explanation:string}>('/study/grammar-check',json('POST',{course_id:courseId,version,lesson_id:lesson.id,answer}))})
 const guide=lesson.grammar!
 return <section className={`card ${s.grammarBlock}`}><h3>{guide.kind==='topic_review'?'Повторение темы':'Правило и примеры'}</h3><p>{guide.rule}</p><div className={s.grammarTableWrap}><table><thead><tr>{guide.table.headers.map(head=><th key={head}>{head}</th>)}</tr></thead><tbody>{guide.table.rows.map((row,i)=><tr key={i}>{row.map((cell,j)=><td key={j}>{cell}</td>)}</tr>)}</tbody></table></div><div className={s.grammarExamples}>{guide.examples.map(example=><p key={example} lang="en">{example}</p>)}</div><fieldset className={s.quiz}><legend>{guide.check.prompt}</legend>{guide.check.options.map(option=><label key={option} className={s.option}><input type="radio" name={`grammar-${lesson.id}`} checked={answer===option} onChange={()=>{setAnswer(option);check.reset()}}/>{option}</label>)}</fieldset><button type="button" className="secondaryButton" disabled={!answer||check.isPending} onClick={()=>check.mutate()}>{check.isPending?'Проверяем…':'Проверить правило'}</button>{check.data&&<p role="status" className={check.data.correct?'successMessage':'errorMessage'}>{check.data.correct?'Верно. ':'Попробуйте ещё. '}{check.data.explanation}</p>}{check.isError&&<p role="alert" className="errorMessage">Не удалось проверить ответ. Попробуйте ещё раз.</p>}</section>
}
export function AttemptResult({item}:{item:Attempt}){return <section className={s.history}><h3>{item.passed?'Материал пройден':'Есть что повторить'}</h3><p>Вопросы: {item.score} из {item.total}. {item.assessment}</p>{item.feedback.map((r,i)=><div key={i} className={s.feedback} data-correct={r.correct}><strong>{r.correct?'Верно':'Повторите'}: {r.prompt}</strong><p>Ваш ответ: {r.answer}. Правильный: {r.accepted.join(' / ')}.</p><p>{r.explanation}</p></div>)}{item.feedback.some(r=>!r.correct)&&item.snapshot.retry_practice&&<div className={s.feedback}><h4>Дополнительная практика после ошибки</h4><p>{item.snapshot.retry_practice}</p></div>}</section>}
function Practice({lesson,plan,date,today,drafts}:{lesson:Lesson;plan:StudyPlan;date:string;today:string;drafts:StudyDraftStore}){
 const initial=useRef(newStudyDraft(plan,lesson,date));const key=plan.id+':'+lesson.id
 const draft=drafts.values[key]||initial.current
 const help=useQuery({queryKey:['study-help-availability',plan.id,lesson.id],queryFn:()=>api<{question_indices:number[]}>(`/study/assist/availability?plan_id=${encodeURIComponent(plan.id)}&lesson_id=${encodeURIComponent(lesson.id)}`),retry:false})
 const {answers,evidence,self_checks:checks,date:when,portfolio_url:url}=draft
 function change(changes:Partial<typeof draft>){drafts.update(key,draft,changes)}
 const goal=plan.goal==='work'?'В применении используйте рабочую ситуацию: сообщение коллеге, проверку результата или объяснение решения.':plan.goal==='travel'?'В применении используйте поездку: транспорт, встречу или решение дорожной проблемы.':plan.goal==='project'?'Примените тему к собственному проекту и опишите наблюдаемый результат.':'Выберите знакомую повседневную ситуацию для применения.'
 return <section className="card"><h3>Практика и результат</h3><p>{lesson.practice}</p><p className={s.subtle}>{goal}</p>{lesson.speaking&&<p><strong>Вслух:</strong> {lesson.speaking}</p>}
  <form className="formStack" onSubmit={e=>{e.preventDefault();if(!draft.pending&&!draft.draftPending&&!plan.archived)void drafts.save(key,draft)}}><fieldset className={f.fields} disabled={draft.pending||draft.draftPending||plan.archived}>
    {lesson.quiz.map((q,i)=><fieldset key={i} className={s.quiz}><legend>{i+1}. {q.prompt}</legend>{q.options.map(o=><label className={s.option} key={o}><input type="radio" required name={`answer-${lesson.id}-${i}`} checked={answers[i]===o} onChange={()=>{change({answers:answers.map((v,j)=>j===i?o:v)})}}/>{o}</label>)}{help.data?.question_indices.includes(i)&&<StudyHelp planId={plan.id} lessonId={lesson.id} questionIndex={i} attemptId={draft.result?.id} answerText={evidence}/>}</fieldset>)}
  </fieldset>
    <label>Ваш результат и заметки<textarea readOnly={plan.archived||draft.pending||draft.draftPending} required minLength={20} maxLength={20000} rows={7} value={evidence} onChange={e=>{change({evidence:e.target.value})}} placeholder="Ваше решение, текст или отчёт о практике. Для устного задания добавьте тезисы и то, что нужно повторить."/></label>
  <fieldset className={f.fields} disabled={draft.pending||draft.draftPending||plan.archived}>

    <div className={f.pair}><label>Дата занятия<input type="date" required min={plan.start_date} max={today} value={when} onChange={e=>{change({date:e.target.value})}}/></label><label>Ссылка на результат (необязательно)<input type="url" maxLength={2000} value={url} onChange={e=>{change({portfolio_url:e.target.value})}} placeholder="https://…"/></label></div>
    <div><h4>Самопроверка</h4><p className={s.subtle}>Отмечайте только выполненное. Можно сохранить попытку с ошибками и незавершённой практикой.</p>{lesson.rubric.map((r,i)=><label key={r} className={s.option}><input type="checkbox" checked={checks[i]} onChange={e=>{change({self_checks:checks.map((c,j)=>j===i?e.target.checked:c)})}}/>{r}</label>)}</div>
    {!plan.archived&&<div className={f.actions}>{!draft.result&&<button type="button" className="secondaryButton" onClick={()=>void drafts.saveDraft(key,draft)}>{draft.draftPending?'Сохраняем черновик…':'Сохранить черновик'}</button>}<button className="primaryButton">{draft.pending?'Сохраняем…':'Проверить и сохранить'}</button></div>}
    {!plan.archived&&<p className={s.subtle} role="status">{draft.result?'Результат сохранён; черновик удалён.':draft.saved?'Черновик сохранён на сервере.':'Изменения сохраняются на сервере после нажатия «Сохранить черновик».'}</p>}
    {draft.draftError&&<p role="alert" className="errorMessage">{draft.draftError}</p>}
  </fieldset>{draft.error&&<p role="alert" className="errorMessage">{draft.error}</p>}</form>
  {draft.result&&<div role="status"><p className="successMessage">Результат сохранён.</p><AttemptResult item={draft.result}/></div>}
  <details><summary>Критерии решения и подсказка</summary><p>{lesson.solution}</p></details>
 </section>
}
export function StudyLesson({lesson,plan,date,today,drafts}:{lesson:Lesson;plan:StudyPlan;date:string;today:string;drafts:StudyDraftStore}){
 const [audioError,setAudioError]=useState(false)
 const english=languageCourses.includes(plan.course_id as typeof languageCourses[number])
 const languageTag=({english:"en",kazakh:"kk",korean:"ko",turkish:"tr",spanish:"es"} as Record<string,string>)[plan.course_id] || "en"
 const [step,setStep]=useState(0)
 const steps=['Разобрать тему','Выучить слова','Читать и слушать','Практика и результат']
 return <article id="study-lesson" className={s.reader}>
  <AssistantMaterialButton section={plan.course_id==='java-backend'?'profession':plan.course_id as 'java'} material={{kind:'lesson',id:plan.course_id+':'+lesson.id,version:plan.version}} studyContext={{plan_id:plan.id,lesson_id:lesson.id}} stepId={step===3?'practice':'theory'} handlers={{example:()=>{setStep(0);requestAnimationFrame(()=>document.getElementById('assisted-example-'+lesson.id)?.scrollIntoView({block:'center'}))},practice:()=>{setStep(3);requestAnimationFrame(()=>document.getElementById('assisted-practice-'+lesson.id)?.scrollIntoView({block:'start'}))}}}/>
  {english&&<nav className={s.lessonSteps} aria-label="Шаги урока">{steps.map((label,index)=><button type="button" key={label} aria-current={step===index?'step':undefined} onClick={()=>setStep(index)}><span>{index+1}</span>{label}</button>)}</nav>}
  <div hidden={english&&step!==0}>{english&&lesson.grammar&&<GrammarPractice key={lesson.id} lesson={lesson} version={plan.version} courseId={plan.course_id}/>}<section className="card"><span className="eyebrow">{lesson.chapter||lesson.level} · около {lesson.minutes} минут</span><h2>{lesson.title}</h2><p className={s.subtle}>{english?'Шаг 1 из 4. Разберите объяснение и пример. Затем переходите к словам.':'Разберите объяснение, выполните практику и сохраните результат.'}</p>{plan.minutes<lesson.minutes&&<p className="healthNotice">Ваше окно — {plan.minutes} минут. Начните с объяснения и примера; практику можно закончить в следующем окне. Перед уходом сохраните заполненную попытку.</p>}{lesson.explanation.map((p,i)=><p key={i}>{p}</p>)}<h3 id={'assisted-example-'+lesson.id}>Разобранный пример</h3><pre className={s.code}>{lesson.example}</pre>{lesson.related_source&&<p className={s.subtle}>Дополнительно: <a href={lesson.related_source.url} target="_blank" rel="noreferrer">{lesson.related_source.label}</a>. Основной материал урока находится здесь.</p>}</section></div>
  <div hidden={english&&step!==1}>{!!lesson.vocabulary?.length&&<section className="card"><h3>Слова урока</h3><p>Сначала попробуйте понять слово по примеру. Затем откройте перевод.</p><div className={s.words}>{lesson.vocabulary.map(w=><LessonWord key={w.id} word={w} languageTag={languageTag}/>)}</div><p className={s.subtle}>После сохранения первой попытки эти слова появятся в повторении.</p></section>}</div>
  <div hidden={english&&step!==2}>{lesson.reading&&<section className="card"><h3>Чтение</h3><p className={s.passage} lang={languageTag}>{lesson.reading}</p>{english&&!lesson.audio&&<Pronunciation text={lesson.reading} language={languageTag} label="Прослушать текст"/>}<p className={s.subtle}>Сформулируйте основную мысль своими словами. Вопрос по тексту находится в практике.</p></section>}
  {lesson.audio&&<section className="card"><h3>Аудирование</h3><p>Сначала прослушайте без расшифровки: кто говорит, зачем и какая деталь важна? Затем ответьте на вопрос в практике.</p><audio className={s.audio} controls preload="metadata" src={lesson.audio} aria-label="Аудио урока" onError={()=>setAudioError(true)}/>{audioError&&<p role="alert" className="errorMessage">Аудио не загрузилось. <a href={lesson.audio} target="_blank" rel="noreferrer">Открыть файл отдельно</a>. Не отмечайте аудирование выполненным, пока не прослушали запись.</p>}<p className={s.subtle}>Синтетическая учебная запись на английском. Скорость можно изменить в меню проигрывателя.</p><details><summary>Расшифровка после прослушивания</summary><p className={s.passage} lang={languageTag}>{lesson.transcript}</p></details></section>}</div>
  {plan.archived&&<section className="card"><p>Архивный план: материалы и результаты доступны для чтения. Сохранившийся черновик можно скопировать; новые результаты записываются в действующий план.</p></section>}
  <div id={'assisted-practice-'+lesson.id} hidden={english&&step!==3}>{(!plan.archived||drafts.values[plan.id+':'+lesson.id])&&<Practice key={plan.id+lesson.id} lesson={lesson} plan={plan} date={date} today={today} drafts={drafts}/>}</div>
  {english&&<div className={s.lessonStepActions}>{step>0&&<button type="button" className="secondaryButton" onClick={()=>setStep(step-1)}>Назад</button>}{step<3&&<button type="button" className="primaryButton" onClick={()=>setStep(step+1)}>Далее: {steps[step+1]}</button>}</div>}
 </article>
}

function LessonWord({word,languageTag}:{word:{id:string;word:string;translation:string;example:string};languageTag:string}){
 const [revealed,setRevealed]=useState(false)
 return <div className={s.word}><strong lang={languageTag}>{word.word}</strong><Pronunciation text={word.word} language={languageTag}/><p lang={languageTag}>{word.example}</p>{revealed?<span>{word.translation}</span>:<button type="button" className="textButton" onClick={()=>setRevealed(true)}>Показать перевод</button>}</div>
}
