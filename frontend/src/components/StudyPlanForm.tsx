import {useRef,useState} from 'react'
import {useMutation,useQuery} from '@tanstack/react-query'
import {api,json} from '../api'
import {goalNames,levelNames,type Course,type PlanDraft,type StudyPlan,type Preview,type Quiz} from '../studyTypes'
import s from '../pages/Study.module.css'
import f from '../pages/Journal.module.css'
function Diagnostic({onLevel}:{onLevel:(level:string)=>void}){
 const questions=useQuery({queryKey:['study-diagnostic'],queryFn:()=>api<{questions:Quiz[];limitation:string}>('/study/diagnostic')})
 const [answers,setAnswers]=useState<string[]>(Array(6).fill(''))
 const check=useMutation({mutationFn:()=>api<{score:number;total:number;level:string;below_scope:boolean;message:string;feedback:{prompt:string;accepted:string[];explanation:string}[]}>('/study/diagnostic',json('POST',{answers}))})
 return <section className="card"><h3>Ориентир по уровню</h3>{questions.isError?<p role="alert">Проверка недоступна. <button type="button" onClick={()=>void questions.refetch()}>Повторить</button></p>:questions.data?<><p>{questions.data.limitation}</p>{questions.data.questions.map((q,i)=><label key={i}>{q.prompt}<select value={answers[i]} onChange={e=>{setAnswers(answers.map((a,n)=>n===i?e.target.value:a));check.reset()}}><option value="">Выберите ответ</option>{q.options.map(o=><option key={o}>{o}</option>)}</select></label>)}<button type="button" className="secondaryButton" disabled={check.isPending||answers.some(a=>!a)} onClick={()=>check.mutate()}>Проверить уровень</button>{check.error&&<p role="alert">{check.error.message}</p>}{check.data&&<><p>{check.data.score}/{check.data.total}. {check.data.message}</p><details><summary>Разбор ответов</summary>{check.data.feedback.map((v,i)=><p key={i}>{v.prompt}: {v.accepted.join(' / ')}. {v.explanation}</p>)}</details><button type="button" className="secondaryButton" onClick={()=>onLevel(check.data!.level)}>Выбрать блок {check.data.level}</button></>}</>:<p>Загрузка вопросов…</p>}</section>
}
export function StudyPlanForm({course,active,today,onSaved,onPendingChange}:{course:Course;active:StudyPlan|null;today:string;onSaved:(plan:StudyPlan)=>void;onPendingChange?:(pending:boolean)=>void}){
 const [draft,setDraft]=useState<PlanDraft>({course_id:course.id,version:course.version,level:active?.level||course.levels[0],goal:active?.goal||'general',minutes:active?.minutes||30,weekdays:active?.weekdays||[0,2,4],start_date:today})
 const [diagnostic,setDiagnostic]=useState(false);const key=useRef(crypto.randomUUID())
 const preview=useMutation({mutationFn:(request:{draft:PlanDraft;expectedPlanId:string|null})=>api<Preview>('/study/preview',json('POST',request.draft))})
 const save=useMutation({mutationFn:async()=>{onPendingChange?.(true);try{return await api<StudyPlan>('/study/plans',json('POST',{...preview.variables!.draft,expected_plan_id:preview.variables!.expectedPlanId,create_key:key.current}))}finally{onPendingChange?.(false)}},onSuccess:onSaved})
 const stalePreview=!!preview.data&&preview.variables?.expectedPlanId!==(active?.id||null)
 function change(p:Partial<PlanDraft>){setDraft({...draft,...p});key.current=crypto.randomUUID();preview.reset();save.reset()}
 return <form className="formStack" onSubmit={e=>{e.preventDefault();if(!preview.isPending&&!save.isPending){key.current=crypto.randomUUID();save.reset();preview.mutate({draft:{...draft},expectedPlanId:active?.id||null})}}}><fieldset className={f.fields} disabled={preview.isPending||save.isPending}>
  <details className="secondarySection"><summary>Что нужно для занятий</summary><p>{course.prerequisite}</p></details><div className={f.pair}><label>Начальный блок<select value={draft.level} onChange={e=>change({level:e.target.value})}>{course.levels.map(l=><option key={l} value={l}>{levelNames[l]||l}</option>)}</select></label><label>Цель<select value={draft.goal} onChange={e=>change({goal:e.target.value})}>{['general','work',course.area==='languages'?'travel':'project'].map(g=><option key={g} value={g}>{goalNames[g]}</option>)}</select></label></div>
  {course.id==='english'&&<><button type="button" className="textButton" onClick={()=>setDiagnostic(!diagnostic)}>Не уверен в уровне</button>{diagnostic&&<Diagnostic onLevel={level=>{change({level});setDiagnostic(false)}}/>}</>}
  <div className={f.pair}><label>Время на занятие<select value={draft.minutes} onChange={e=>change({minutes:Number(e.target.value)})}>{[15,30,45,60].map(n=><option key={n} value={n}>{n} минут</option>)}</select></label><label>Начало плана<input type="date" required min={today} value={draft.start_date} onChange={e=>change({start_date:e.target.value})}/></label></div>
  <div><p>Дни занятий</p><div className={s.days}>{['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map((day,i)=><label key={day}><input type="checkbox" checked={draft.weekdays.includes(i)} onChange={()=>change({weekdays:draft.weekdays.includes(i)?draft.weekdays.filter(d=>d!==i):[...draft.weekdays,i]})}/>{day}</label>)}</div></div>
  <button className="primaryButton" disabled={!draft.weekdays.length}>{preview.isPending?'Подбираем…':'Посмотреть план'}</button>
  {preview.error&&<p role="alert" className="errorMessage">{preview.error.message}</p>}
  {preview.data&&<section className="healthNotice"><h3>Ваш маршрут: {preview.data.lesson_count} занятий</h3><p>{preview.data.reason}</p><p>Один урок может занять несколько учебных окон. Продвигайтесь после практики; срок достижения уровня не обещается.</p>{active&&<p><strong>Будет создан новый план. История текущего плана останется в архиве; отметки нового плана начнутся с нуля. Повторение уже изученных слов сохранится.</strong></p>}<button type="button" className="primaryButton" disabled={save.isPending||stalePreview} onClick={()=>{if(!stalePreview)save.mutate()}}>{save.isPending?'Сохраняем…':active?'Подтвердить замену плана':'Начать этот план'}</button></section>}
  {stalePreview&&<p role="alert" className="errorMessage">План изменился в другом окне. Повторите предпросмотр перед подтверждением.</p>}
  {save.error&&<p role="alert" className="errorMessage">{save.error.message}</p>}
 </fieldset></form>
}
