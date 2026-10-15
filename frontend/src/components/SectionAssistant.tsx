import {isAssistantRoute} from '../assistantLearningTypes'
import {createContext,useContext,useEffect,useRef,useState,type ReactNode} from 'react'
import {Link,useLocation} from 'react-router-dom'
import {useAuth} from '../auth'
import {api} from '../api'
import {sectionForPath,sectionNames,type SectionCode} from '../assistantSections'
import {Button,Dialog,Input,Card} from './ui'
import styles from './SectionAssistant.module.css'
import {AssistantCheck} from './AssistantCheck'
export type MaterialRef={kind:string;id:string;version:string}
type Material=MaterialRef&{title:string}
type Topic={id:string;label:string}
type Topics={topics:Topic[];materials:Material[]}
type Result={example_available?:boolean;check_available?:boolean;next_actions?:{id:string;label:string;kind:string;to?:string}[];request_id:string|null;source:'authored'|'cloud_ai';text:string;material:Material|null;links:{label:string;to:string}[];notice:string|null}
type MaterialChoice=Omit<MaterialRef,'version'>&{version?:string}
type OpenArgs={section:SectionCode;material?:MaterialChoice;stepId?:string;studyContext?:{plan_id:string;lesson_id:string};handlers?:Partial<Record<'practice'|'example'|'technique'|'sets'|'rest'|'ingredients'|'next_step',()=>void>>}
const AssistantOpenState=createContext(false)
export function useAssistantOpen(){return useContext(AssistantOpenState)}
const AssistantContext=createContext<((args:OpenArgs)=>void)|null>(null)
export function AssistantProvider({children}:{children:ReactNode}){
 const {user}=useAuth();const {pathname,search:routeSearch,hash}=useLocation()
 const [opened,setOpened]=useState<OpenArgs|null>(null)
 const [data,setData]=useState<Topics|null>(null)
 const [result,setResult]=useState<Result|null>(null)
 const [selected,setSelected]=useState<MaterialRef|null>(null)
 const [format,setFormat]=useState('default')
 const [search,setSearch]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [rated,setRated]=useState(false)
 const generation=useRef(0);const focus=useRef<HTMLElement|null>(null);const inFlight=useRef(false)
 function close(){generation.current++;inFlight.current=false;setOpened(null);setData(null);setResult(null);setBusy(false);setError('');setSelected(null)}
 useEffect(()=>{close()},[pathname,routeSearch,hash,user?.id])
 async function load(args:OpenArgs){
  const current=++generation.current
  setData(null);setResult(null);setError('');setBusy(true);inFlight.current=true;setSearch('');setSelected(args.material?.version?args.material as MaterialRef:null);setRated(false)
  try{const response=await api<Topics>('/assistant/topics?section='+args.section);if(generation.current===current){setData(response);if(args.material){const found=response.materials.find(x=>x.kind===args.material!.kind&&x.id===args.material!.id&&(!args.material!.version||x.version===args.material!.version));if(found)setSelected({kind:found.kind,id:found.id,version:found.version});else{setSelected(null);setError('Материал обновлён или недоступен. Выберите его из списка.')}}}}
  catch(e){if(generation.current===current)setError(e instanceof Error?e.message:'Не удалось загрузить помощь')}
  finally{if(generation.current===current){setBusy(false);inFlight.current=false}}
 }
 function open(args:OpenArgs){focus.current=document.activeElement instanceof HTMLElement?document.activeElement:null;setOpened(args);setFormat('default');void load(args)}
 async function ask(topic:Topic,selectedFormat=format){
  if(!opened||inFlight.current)return
  const current=++generation.current;inFlight.current=true;setBusy(true);setResult(null);setError('');setRated(false)
  try{const response=await api<Result>('/assistant/explain',{method:'POST',body:JSON.stringify({section:opened.section,topic_id:topic.id,material:selected,format:selectedFormat,step_id:opened.stepId})});if(generation.current===current)setResult(response)}
  catch(e){if(generation.current===current){setError(e instanceof Error?e.message:'Не удалось получить объяснение');setResult(null)}}
  finally{if(generation.current===current){setBusy(false);inFlight.current=false}}
 }
 async function rate(helped:boolean){
  if(!result?.request_id||inFlight.current||rated)return
  const current=generation.current;inFlight.current=true;setBusy(true);setError('')
  try{await api('/assistant/feedback',{method:'POST',body:JSON.stringify({request_id:result.request_id,helped})});if(generation.current===current)setRated(true)}
  catch(e){if(generation.current===current)setError(e instanceof Error?e.message:'Не удалось сохранить оценку')}
  finally{if(generation.current===current){setBusy(false);inFlight.current=false}}
 }
 return <AssistantContext.Provider value={open}><AssistantOpenState.Provider value={!!opened}>{children}<Dialog open={!!opened} title={'Помощник · '+(opened?sectionNames[opened.section]:'')} onClose={close} returnFocusTo={focus.current} className={styles.dialog}>
  <header className={styles.header}><h2>Помощник · {opened?sectionNames[opened.section]:''}</h2><Button variant="quiet" onClick={close}>Закрыть</Button></header>
  <div className={styles.body}>
   <p className={styles.muted}>Помощь по материалам и функциям. Личные записи не передаются ИИ.</p>
   {!data&&busy&&<p role="status">Загружаем помощь…</p>}
   {data&&<>
    {data.materials.length>0&&<details className={styles.materials} ><summary>Выбрать материал{selected?' · выбран':''}</summary>
     <Input label="Найти материал" placeholder="Название материала" value={search} onChange={e=>setSearch(e.target.value)}/>
     <div className={styles.materialList}><Button variant="quiet" disabled={busy} onClick={()=>{setOpened({section:opened!.section});setSelected(null);setResult(null)}}>Общие вопросы раздела</Button>
      {data.materials.filter(x=>x.title.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(x=><Button key={x.kind+':'+x.id} variant={selected?.kind===x.kind&&selected.id===x.id?'primary':'secondary'} disabled={busy} onClick={()=>{setOpened({section:opened!.section});setSelected({kind:x.kind,id:x.id,version:x.version});setResult(null);setRated(false)}}>{x.title}</Button>)}
     </div>
    </details>}
    {selected&&<p className={styles.selected}>{data.materials.find(x=>x.kind===selected.kind&&x.id===selected.id)?.title}<br/><span className={styles.muted}>Выберите вопрос ниже — объяснение будет по этому материалу.</span></p>}
    <div className={styles.questions} aria-label="Формат объяснения">{[['simple','Проще'],['example','На примере'],['steps','Пошагово'],['brief','Коротко']].map(([value,label])=><Button key={value} variant={format===value?'primary':'secondary'} disabled={busy} aria-pressed={format===value} onClick={()=>{setFormat(value);if(data.topics[0])void ask(data.topics[0],value)}}>{label}</Button>)}</div>
    <div className={styles.questions}>{(selected?data.topics.slice(0,1):data.topics).map(topic=><Button key={topic.id} variant="secondary" disabled={busy} onClick={()=>void ask(topic)}>{selected?'Объяснить материал':topic.label}{selected&&<span className={styles.srOnly}> · {topic.label}</span>}</Button>)}</div>
   </>}
   {busy&&data&&<p role="status">Готовим объяснение…</p>}
   {error&&<div role="alert"><p className="errorMessage">{error}</p>{opened&&<Button variant="secondary" disabled={busy} onClick={()=>void load({section:opened.section})}>{data?'Обновить материалы':'Повторить загрузку'}</Button>}</div>}
   {result&&<Card className={styles.answer}><div role="status"><strong>{result.source==='cloud_ai'?'Объяснение ИИ · Gemini':'Готовая подсказка'}</strong>{result.material&&<p className={styles.muted}>{result.material.title}</p>}<p className={styles.answerText}>{result.text}</p></div>
    {selected?.kind==='recipe'&&opened?.stepId&&<p>Объяснение относится к исходному рецепту. Граммы для выбранных порций показаны в режиме готовки.</p>}
    {format==='example'&&!result.example_available&&<p>Готовый пример пока отсутствует. Показан исходный материал.</p>}
    {opened?.handlers&&Object.entries(opened.handlers).map(([id,handler])=><Button key={id} onClick={()=>{close();requestAnimationFrame(()=>handler?.())}}>{({practice:'Перейти к практике',example:'Открыть пример',technique:'Показать технику',sets:'Вернуться к подходам',rest:'Вернуться к таймеру',ingredients:'Показать ингредиенты',next_step:'Следующий шаг'} as Record<string,string>)[id]}</Button>)}
    {selected&&opened&&result.check_available&&<AssistantCheck key={selected.kind+selected.id+selected.version} section={opened.section} material={selected} studyContext={opened.studyContext} onContinue={()=>{const handler=opened.handlers?.practice??opened.handlers?.sets;close();requestAnimationFrame(()=>handler?.())}}/>}
    {selected&&!result.check_available&&<p>Дополнительный вопрос пока не подготовлен.{['book','guide'].includes(selected.kind)?' Для самостоятельного повторения: назовите главную мысль материала и один способ применить её.':''}</p>}
    {result.next_actions?.map(action=>action.kind==='route'&&isAssistantRoute(action.to)?<Link key={action.id} to={action.to} onClick={close}>{action.label}</Link>:null)}
    {result.notice&&<p className={styles.muted}>{result.notice}</p>}
    {result.links.map(link=><Link key={link.to} to={link.to} onClick={close}>{link.label}</Link>)}
    {result.request_id&&(rated?<p role="status">Спасибо за оценку</p>:<div className={styles.feedback}><Button variant="quiet" disabled={busy} onClick={()=>void rate(true)}>Помогло</Button><Button variant="quiet" disabled={busy} onClick={()=>void rate(false)}>Не помогло</Button></div>)}
   </Card>}
  </div>
 </Dialog></AssistantOpenState.Provider></AssistantContext.Provider>
}
export function SectionAssistant({section}:{section?:SectionCode}){
 const open=useContext(AssistantContext);const {pathname}=useLocation();const current=section??sectionForPath(pathname)
 if(!open||!current)return null
 return <div className={styles.trigger}><Button variant="quiet" onClick={()=>open({section:current})}>Помощник</Button></div>
}
export function AssistantMaterialButton({section,material,stepId,handlers,studyContext}:{section:SectionCode;material:MaterialChoice;stepId?:string;studyContext?:{plan_id:string;lesson_id:string};handlers?:OpenArgs['handlers']}){
 const open=useContext(AssistantContext)
 return open?<Button variant="quiet" onClick={()=>open({section,material,stepId,handlers,studyContext})}>Объяснить</Button>:null
}
