import {useState} from 'react'
import {api} from '../api'
import {Button} from './ui'
import styles from './StudyHelp.module.css'

type Stage='explain'|'hint'|'next_step'|'review'
type Result={request_id:string;source:'authored'|'local_ai'|'cloud_ai';stage:Stage;text:string;next_stage_token:string|null;allow_local_answer?:boolean}

export function StudyHelp({planId,lessonId,questionIndex,attemptId,answerText}:{planId:string;lessonId:string;questionIndex:number;attemptId?:string;answerText:string}){
 const [format,setFormat]=useState('default')
 const [result,setResult]=useState<Result|null>(null)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const [share,setShare]=useState(false)
 const [rated,setRated]=useState(false)
 async function ask(stage:Stage){
  if(busy)return
  const previousToken=result?.next_stage_token
  setBusy(true);setError('');setResult(null)
  try{
   const includeAnswer=stage==='review'&&!!attemptId&&share
   const response=await api<Result>('/study/assist',{method:'POST',body:JSON.stringify({plan_id:planId,lesson_id:lessonId,question_index:questionIndex,stage,format,attempt_id:attemptId??null,answer_text:includeAnswer?answerText.slice(0,2000):null,include_answer:includeAnswer,stage_token:stage==='next_step'||stage==='review'?previousToken:null})})
   setResult(response);setRated(false)
  }catch(e){setError(e instanceof Error?e.message:'Подсказка сейчас недоступна')}
  finally{setBusy(false)}
 }
 async function rate(helped:boolean){
  if(!result||rated||busy)return
  setBusy(true);setError('')
  try{await api('/study/assist/feedback',{method:'POST',body:JSON.stringify({request_id:result.request_id,helped})});setRated(true)}
  catch(e){setError(e instanceof Error?e.message:'Не удалось сохранить оценку')}
  finally{setBusy(false)}
 }
 return <div className={styles.help}>
  <div className={styles.actions} aria-label="Формат подсказки">{[['simple','Проще'],['example','На примере'],['steps','Пошагово'],['brief','Коротко']].map(([value,label])=><Button key={value} disabled={busy} variant={format===value?'primary':'secondary'} aria-pressed={format===value} onClick={()=>{setFormat(value);setResult(null)}}>{label}</Button>)}</div>
  <div className={styles.actions}>
   <button type="button" className="secondaryButton" disabled={busy} onClick={()=>void ask('hint')}>{busy?'Подождите…':'Намёк'}</button>
   {result?.stage==='hint'&&<button type="button" className="secondaryButton" disabled={busy} onClick={()=>void ask('next_step')}>Следующий шаг</button>}
   {result?.stage==='next_step'&&attemptId&&<button type="button" className="secondaryButton" disabled={busy} onClick={()=>void ask('review')}>Разобрать ошибку</button>}
   <button type="button" className="textButton" disabled={busy} onClick={()=>void ask('explain')}>Объяснить иначе</button>
  </div>
  {result?.stage==='next_step'&&attemptId&&result.allow_local_answer&&<label className={styles.consent}><input type="checkbox" checked={share} onChange={event=>setShare(event.target.checked)}/> При разборе передать мой текст решения локальной модели этого компьютера</label>}
  {result&&<div className={styles.result} role="status"><strong>{result.source==='authored'?'Готовое объяснение из урока':result.source==='cloud_ai'?'Объяснение ИИ · Gemini':'Ответ локальной модели'}</strong><p>{result.text}</p></div>}
  {result&&(rated?<p role="status">Спасибо за оценку</p>:<div className={styles.actions} aria-label="Оценить подсказку"><button type="button" className="textButton" disabled={busy} onClick={()=>void rate(true)}>Помогло</button><button type="button" className="textButton" disabled={busy} onClick={()=>void rate(false)}>Не помогло</button></div>)}
  {error&&<p role="alert" className="errorMessage">{error}</p>}
 </div>
}
