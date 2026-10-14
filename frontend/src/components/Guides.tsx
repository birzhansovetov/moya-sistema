import {useQuery} from '@tanstack/react-query'
import {MaterialFit} from './MaterialFit'
import {api} from '../api'
import {useAuth} from '../auth'
import styles from '../pages/Journal.module.css'
type Guide={id:string;title:string;version:number;intro:string;steps:string[];example:string;check:string[];sources?:string[]}
export function Guides({area}:{area:'personal'|'reading'|'finance'|'sport'}){
  const {user}=useAuth()
  const query=useQuery({queryKey:['guides',user?.id,area],queryFn:()=>api<{items:Guide[]}>(`/library/guides?area=${area}`)})
  const onboarding=useQuery({queryKey:['onboarding',user?.id],queryFn:()=>api<{answers:{finance:{focus:string};personal:{focus:string}}|null}>('/onboarding'),enabled:user?.onboarding_complete===true})
  const preferred=area==='finance'?(onboarding.data?.answers?.finance.focus==='review'?'finance-month':'finance-entry'):area==='personal'?({journal:'personal-day',habits:'personal-habits',reading:'personal-reading'}[onboarding.data?.answers?.personal.focus||'journal']):area==='sport'?window.location.hash.slice(1):undefined
  const items=query.data?.items.slice().sort((a,b)=>Number(b.id===preferred)-Number(a.id===preferred))
  return <section id={`${area}-guides`} className={`card ${styles.guides}`}><h2>Готовые гайды</h2>{query.isError?<p role="alert" className="errorMessage">Не удалось загрузить материалы. <button className="textButton" onClick={()=>void query.refetch()}>Повторить загрузку гайдов</button></p>:!items?<p className="muted">Загружаем материалы…</p>:items.map(item=><details id={item.id} key={item.id} open={item.id===preferred?true:undefined}><summary>{item.title}{item.id===preferred?' · ваш выбор':''}</summary><p>{item.intro}</p><ol>{item.steps.map(step=><li key={step}>{step}</li>)}</ol><div className={styles.example}>{item.example}</div><h3>Проверить себя</h3><ul>{item.check.map(check=><li key={check}>{check}</li>)}</ul>{item.sources?.length? <p className="muted">Источники: {item.sources.map((source,index)=><a key={source} href={source} target="_blank" rel="noreferrer">{index+1}{index<item.sources!.length?', ':''}</a>)}</p>:null}<MaterialFit title={item.title} reasons={['other','goal']} alternatives={(items||[]).filter(other=>other.id!==item.id).map(other=>({id:other.id,title:other.title,onSelect:()=>{const current=document.getElementById(item.id) as HTMLDetailsElement|null;const next=document.getElementById(other.id) as HTMLDetailsElement|null;if(current)current.open=false;if(next){next.open=true;next.scrollIntoView?.({behavior:'smooth',block:'start'})}}}))} configureTo="/onboarding"/></details>)}</section>
}
