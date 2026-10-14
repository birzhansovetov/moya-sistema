import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api, json } from '../api'
import { activityNames, kindNames, moodNames, type PersonalEntry, type PersonalKind } from '../personalTypes'
import styles from '../pages/Journal.module.css'

type Draft = Omit<PersonalEntry,'id'|'deleted'>
export function PersonalForm({ initial, date, onSaved, onCancel, onPendingChange }: { initial?:PersonalEntry; date:string; onSaved:(entry:PersonalEntry)=>void; onCancel?:()=>void; onPendingChange?:(pending:boolean)=>void }) {
  const empty = ():Draft => ({kind:'diary',title:'',body:'',date,mood:null,activity:'other',completed:false,impression:''})
  const [draft,setDraft]=useState<Draft>(initial || empty)
  const key=useRef(crypto.randomUUID())
  function change(changes:Partial<Draft>){setDraft({...draft,...changes});key.current=crypto.randomUUID();save.reset()}
  const save=useMutation({mutationFn:async()=>{onPendingChange?.(true);try{return await api<PersonalEntry>(initial?`/personal/entries/${initial.id}`:'/personal/entries',json(initial?'PATCH':'POST',{...draft,...(!initial?{create_key:key.current}:{})}))}finally{onPendingChange?.(false)}},onSuccess:entry=>{if(!initial){setDraft(empty());key.current=crypto.randomUUID()}onSaved(entry)}})
  return <form className="formStack" onSubmit={event=>{event.preventDefault();if(!save.isPending)save.mutate()}}><fieldset className={styles.fields} disabled={save.isPending}>
    <div className={styles.pair}><label>Тип записи<select value={draft.kind} onChange={event=>change({kind:event.target.value as PersonalKind})}>{Object.entries(kindNames).map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label><label>Дата<input type="date" required={draft.kind==='diary'} value={draft.date||''} onChange={event=>change({date:event.target.value||null})}/></label></div>
    {draft.kind!=='diary'&&<label>Название<input maxLength={160} required value={draft.title} onChange={event=>change({title:event.target.value})}/></label>}
    <label>{draft.kind==='diary'?'Что хотите записать?':'Текст записи'}<textarea rows={6} maxLength={20000} placeholder={draft.kind==='diary'?'Что произошло сегодня? Что вы почувствовали?':'Идея, место, детали или план'} value={draft.body} onChange={event=>change({body:event.target.value})}/></label>
    {draft.kind==='diary'&&<details className={styles.extraFields} open={!!(initial?.mood || initial?.title) || undefined}><summary>Настроение и заголовок</summary><div className={styles.extraFieldsBody}><label>Настроение<select value={draft.mood||''} onChange={event=>change({mood:event.target.value||null})}><option value="">Не указывать</option>{Object.entries(moodNames).map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label><label>Заголовок<input maxLength={160} value={draft.title} onChange={event=>change({title:event.target.value})}/></label></div></details>}
    {draft.kind!=='diary'&&<>
      <label>Направление<select value={draft.activity} onChange={event=>change({activity:event.target.value})}>{Object.entries(activityNames).map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label>
      <label className={styles.check}><input type="checkbox" checked={draft.completed} onChange={event=>change({completed:event.target.checked})}/>Выполнено</label>
      <label>Впечатление<textarea rows={3} maxLength={10000} value={draft.impression} onChange={event=>change({impression:event.target.value})}/></label>
      <p className="muted">Без даты запись останется идеей. С датой она появится в календаре и «Моём дне».</p>
    </>}
    {save.error&&<p role="alert" className="errorMessage">{save.error.message}</p>}
    <div className={styles.actions}><button className="primaryButton" type="submit">{save.isPending?'Сохраняем…':initial?'Сохранить изменения':'Сохранить запись'}</button>{onCancel&&<button type="button" className="secondaryButton" onClick={onCancel}>Отмена</button>}</div>
  </fieldset></form>
}
