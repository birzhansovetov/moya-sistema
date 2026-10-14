import { useRef,useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api,json } from '../api'
import {bookStatuses,type Book,type BookStatus} from '../readingTypes'
import styles from '../pages/Journal.module.css'
export function BookForm({initial,suggestion,onSaved,onCancel,onPendingChange}:{initial?:Book;suggestion?:{title:string;author:string};onSaved:(book:Book)=>void;onCancel:()=>void;onPendingChange?:(pending:boolean)=>void}){
  const [draft,setDraft]=useState({title:initial?.title||suggestion?.title||'',author:initial?.author||suggestion?.author||'',pages:String(initial?.pages||''),current_page:String(initial?.current_page||0),daily_pages:String(initial?.daily_pages||10),status:initial?.status||(suggestion?'want':'reading') as BookStatus,start_date:initial?.start_date||'',end_date:initial?.end_date||'',cover_url:initial?.cover_url||'',final_impression:initial?.final_impression||''})
  const key=useRef(crypto.randomUUID())
  function change(changes:Partial<typeof draft>){setDraft({...draft,...changes});key.current=crypto.randomUUID();save.reset()}
  const save=useMutation({mutationFn:async()=>{onPendingChange?.(true);try{return await api<Book>(initial?`/reading/books/${initial.id}`:'/reading/books',json(initial?'PATCH':'POST',{...draft,pages:Number(draft.pages),current_page:Number(draft.current_page),daily_pages:Number(draft.daily_pages),start_date:draft.start_date||null,end_date:draft.end_date||null,...(!initial?{create_key:key.current}:{})}))}finally{onPendingChange?.(false)}},onSuccess:onSaved})
  return <form className="formStack" onSubmit={event=>{event.preventDefault();if(!save.isPending)save.mutate()}}><fieldset className={styles.fields} disabled={save.isPending}>
    <label>Название книги<input required maxLength={200} value={draft.title} onChange={event=>change({title:event.target.value})}/></label>
    <label>Автор<input maxLength={160} value={draft.author} onChange={event=>change({author:event.target.value})}/></label>
    <details><summary>Настроить чтение (необязательно)</summary><div className={styles.pair}><label>Количество страниц<input type="number" min={1} max={100000} value={draft.pages} onChange={event=>change({pages:event.target.value})}/></label><label>Страниц за занятие<input type="number" min={1} max={10000} value={draft.daily_pages} onChange={event=>change({daily_pages:event.target.value})}/></label></div>
    {!initial&&<label>Уже прочитано страниц<input required type="number" min={0} max={Number(draft.pages)||100000} value={draft.current_page} onChange={event=>change({current_page:event.target.value})}/></label>}
    <label>Статус книги<select value={draft.status} onChange={event=>change({status:event.target.value as BookStatus})}>{Object.entries(bookStatuses).map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label>
    <div className={styles.pair}><label>Дата начала<input type="date" value={draft.start_date} onChange={event=>change({start_date:event.target.value})}/></label><label>Дата завершения<input type="date" min={draft.start_date||undefined} value={draft.end_date} onChange={event=>change({end_date:event.target.value})}/></label></div>
    <label>Обложка: HTTPS-ссылка (необязательно)<input type="url" maxLength={2000} value={draft.cover_url} onChange={event=>change({cover_url:event.target.value})}/></label>
    <label>Итоговое впечатление<textarea rows={4} maxLength={20000} value={draft.final_impression} onChange={event=>change({final_impression:event.target.value})}/></label></details>
    {save.error&&<p role="alert" className="errorMessage">{save.error.message}</p>}
    <div className={styles.actions}><button className="primaryButton">{save.isPending?'Сохраняем…':'Сохранить книгу'}</button><button type="button" className="secondaryButton" onClick={onCancel}>Отмена</button></div>
  </fieldset></form>
}
