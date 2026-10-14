import { useRef,useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api,json } from '../api'
import {reflectionNames,type Book,type ReadingLog} from '../readingTypes'
import styles from '../pages/Journal.module.css'
export function ReadingLogForm({book,date,today,initial,onSaved,onCancel,onPendingChange}:{book:Book;date:string;today:string;initial?:ReadingLog;onSaved:()=>void;onCancel?:()=>void;onPendingChange?:(pending:boolean)=>void}){
  const empty=()=>({date,page:'',chapter:'',text:'',reflection:{} as Record<string,string>})
  const [draft,setDraft]=useState(initial?{...initial,page:initial.page===null?'':String(initial.page)}:empty)
  const key=useRef(crypto.randomUUID())
  function change(changes:Partial<typeof draft>){setDraft({...draft,...changes});key.current=crypto.randomUUID();save.reset()}
  const save=useMutation({mutationFn:async()=>{onPendingChange?.(true);try{return await api<ReadingLog>(`/reading/books/${book.id}/logs${initial?'/'+initial.id:''}`,json(initial?'PATCH':'POST',{...draft,page:draft.page===''?null:Number(draft.page),...(!initial?{create_key:key.current}:{})}))}finally{onPendingChange?.(false)}},onSuccess:()=>{if(!initial){setDraft(empty());key.current=crypto.randomUUID()}onSaved()}})
  return <form className="formStack" onSubmit={event=>{event.preventDefault();if(!save.isPending)save.mutate()}}><fieldset className={styles.fields} disabled={save.isPending}>
    <div className={styles.pair}><label>Дата чтения<input required type="date" max={today} value={draft.date} onChange={event=>change({date:event.target.value})}/></label><label>Страница (необязательно)<input type="number" min={0} max={book.pages} value={draft.page} onChange={event=>change({page:event.target.value})}/></label></div>
    <label>Глава (необязательно)<input maxLength={200} value={draft.chapter} onChange={event=>change({chapter:event.target.value})}/></label>
    <label>Свободная заметка<textarea rows={5} maxLength={20000} placeholder="Можно написать только свободный текст. Остальные поля необязательны." value={draft.text} onChange={event=>change({text:event.target.value})}/></label>
    <details><summary>Вопросы для размышления (необязательно)</summary><div className={styles.stack}>{Object.entries(reflectionNames).map(([field,name])=><label key={field}>{name}<textarea rows={2} maxLength={5000} value={draft.reflection[field]||''} onChange={event=>change({reflection:{...draft.reflection,[field]:event.target.value}})}/></label>)}</div></details>
    {save.error&&<p role="alert" className="errorMessage">{save.error.message}</p>}
    <div className={styles.actions}><button className="primaryButton">{save.isPending?'Сохраняем…':initial?'Сохранить изменения':'Сохранить чтение'}</button>{onCancel&&<button type="button" className="secondaryButton" onClick={onCancel}>Отмена</button>}</div>
  </fieldset></form>
}
