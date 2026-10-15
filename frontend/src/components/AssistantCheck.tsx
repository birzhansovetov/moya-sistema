import {isAssistantRoute} from '../assistantLearningTypes'
import {useEffect,useRef,useState} from 'react'
import {api} from '../api'
import {Button} from './ui'
import {Link} from 'react-router-dom'
import type {MaterialRef} from './SectionAssistant'
type Issue={available:boolean;reason?:string;question:{prompt:string;chapter_title:string;options:{id:string;label:string}[]};token:string}
export function AssistantCheck({section,material,studyContext,onContinue}:{section:string;material:MaterialRef;studyContext?:{plan_id:string;lesson_id:string};onContinue?:()=>void}){
 const [issue,setIssue]=useState<Issue|null>(null),[choice,setChoice]=useState(''),[result,setResult]=useState<{correct:boolean;explanation:string;next_actions?:{id:string;label:string;kind:string;to?:string}[]}|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const generation=useRef(0),pending=useRef(false)
 useEffect(()=>{generation.current++;setIssue(null);setChoice('');setResult(null);setError('');pending.current=false;setBusy(false);return()=>{generation.current++}},[section,material.kind,material.id,material.version])
 async function send(answer=false){if(pending.current)return;pending.current=true;setBusy(true);setError('');const current=generation.current
 try{if(answer&&issue){const response=await api<{correct:boolean;explanation:string;next_actions?:{id:string;label:string;kind:string;to?:string}[]}>('/assistant/checks/answer',{method:'POST',body:JSON.stringify({token:issue.token,option_id:choice})});if(current===generation.current)setResult(response)}else{const response=await api<Issue>('/assistant/checks/issue',{method:'POST',body:JSON.stringify({section,material,study_context:studyContext})});if(current===generation.current){setIssue(response);setResult(null);setChoice('')}}}
 catch(e){if(current===generation.current)setError(e instanceof Error?e.message:'Не удалось проверить')}
 finally{if(current===generation.current){pending.current=false;setBusy(false)}}}
 return <section aria-label="Проверка понимания"><h3>Проверить понимание</h3><p>Отдельный вопрос. Он не завершает занятие и не меняет серию активности.</p>
 {!issue&&<Button disabled={busy} onClick={()=>void send()}>Открыть вопрос</Button>}{issue&&!issue.available&&<p role="status">{issue.reason}</p>}
 {issue?.available&&<><p>{issue.question.chapter_title}</p><fieldset disabled={busy||!!result}><legend>{issue.question.prompt}</legend>{issue.question.options.map(option=><label key={option.id} style={{display:'flex',gap:8,marginBlock:12}}><input type="radio" name="assistant-choice" checked={choice===option.id} onChange={()=>setChoice(option.id)}/>{option.label}</label>)}</fieldset>{!result&&<Button disabled={!choice||busy} onClick={()=>void send(true)}>Проверить</Button>}{result&&<div role="status"><strong>{result.correct?'Верно':'Есть неточность'}</strong><p>{result.explanation}</p>{onContinue&&<Button onClick={onContinue}>{result.correct?'Продолжить занятие':'Вернуться к материалу'}</Button>}{result.next_actions?.map(action=>action.kind==='route'&&isAssistantRoute(action.to)?<Link key={action.id} to={action.to}>{action.label}</Link>:null)}<Button variant="secondary" disabled={busy} onClick={()=>void send()}>Попробовать ещё</Button></div>}</>}{busy&&<p role="status">Загрузка…</p>}{error&&<p role="alert">{error}</p>}</section>
}
