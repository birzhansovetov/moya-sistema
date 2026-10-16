import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api, json } from '../api'
import { activityNames, kindNames, moodNames, type PersonalEntry, type PersonalKind } from '../personalTypes'
import styles from '../pages/Journal.module.css'

type Draft = Omit<PersonalEntry,'id'|'deleted'>
export function PersonalForm({ initial, date, onSaved, onCancel, onPendingChange }: { initial?:PersonalEntry; date:string; onSaved:(entry:PersonalEntry)=>void; onCancel?:()=>void; onPendingChange?:(pending:boolean)=>void }) {
  const empty = ():Draft => ({kind:'diary',title:'',body:'',date,mood:null,activity:'other',activities:[],completed:false,impression:''})
  const [draft,setDraft]=useState<Draft>(initial || empty)
  const key=useRef(crypto.randomUUID())
  function change(changes:Partial<Draft>){setDraft({...draft,...changes});key.current=crypto.randomUUID();save.reset()}
  const save=useMutation({mutationFn:async()=>{onPendingChange?.(true);try{return await api<PersonalEntry>(initial?`/personal/entries/${initial.id}`:'/personal/entries',json(initial?'PATCH':'POST',{...draft,...(!initial?{create_key:key.current}:{})}))}finally{onPendingChange?.(false)}},onSuccess:entry=>{if(!initial){setDraft(empty());key.current=crypto.randomUUID()}onSaved(entry)}})
  return <form className="formStack" onSubmit={event=>{event.preventDefault();if(!save.isPending)save.mutate()}}><fieldset className={styles.fields} disabled={save.isPending}>
    {draft.kind!=='diary'&&<label>Название<input maxLength={160} required value={draft.title} onChange={event=>change({title:event.target.value})}/></label>}
    {draft.kind==='diary'&&<><div className={styles.quickChoice}><strong>Как вы сегодня?</strong><div className={styles.moodChoices}>{Object.entries(moodNames).map(([value,name])=><button type="button" key={value} aria-pressed={draft.mood===value} onClick={()=>change({mood:draft.mood===value?null:value})}><svg viewBox="0 0 40 40" aria-hidden="true" width="40" height="40"><circle cx="20" cy="20" r="17" fill="none" stroke="currentColor" strokeWidth="2"/><circle cx="14" cy="16" r="1.7" fill="currentColor"/><circle cx="26" cy="16" r="1.7" fill="currentColor"/><path d={value==='great'?'M12 23 Q20 34 28 23 Z':value==='good'?'M12 23 Q20 31 28 23':value==='neutral'?'M13 25 H27':'M12 28 Q20 20 28 28'} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg><span>{({great:'Отлично',good:'Хорошо',neutral:'Обычно',low:'Грустно',hard:'Тяжело'} as Record<string,string>)[value]||name}</span></button>)}</div></div></>}
    <label>{draft.kind==='diary'?'Что хотите записать?':'Текст записи'}<textarea rows={draft.kind==='diary'?3:6} maxLength={20000} placeholder={draft.kind==='diary'?'Необязательно: одна мысль о дне':'Идея, место, детали или план'} value={draft.body} onChange={event=>change({body:event.target.value})}/></label>
    <details className={styles.extraFields} open={draft.kind!=='diary' || !!initial || undefined}><summary>Добавить детали</summary><div className={styles.extraFieldsBody}>    <div className={styles.pair}><label>Тип записи<select value={draft.kind} onChange={event=>change({kind:event.target.value as PersonalKind})}>{Object.entries(kindNames).map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label><label>Дата<input type="date" required={draft.kind==='diary'} value={draft.date||''} onChange={event=>change({date:event.target.value||null})}/></label></div>
{draft.kind==='diary'&&<><fieldset className={styles.activityChoices}><legend>Что было сегодня?</legend><div>{Object.entries(activityNames).filter(([value])=>value!=='other').map(([value,name])=><label key={value}><input type="checkbox" checked={(draft.activities ?? [draft.activity]).includes(value)} onChange={event=>{const current=draft.activities ?? [draft.activity];const activities=event.target.checked?[...current,value]:current.filter(item=>item!==value);change({activities,activity:activities[0]||'other'})}}/>{name}</label>)}</div></fieldset><label>Заголовок<input maxLength={160} value={draft.title} onChange={event=>change({title:event.target.value})}/></label></>}</div></details>
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
