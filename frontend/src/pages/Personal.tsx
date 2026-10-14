import { Guides } from '../components/Guides'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from '../api'
import { useAuth } from '../auth'
import { useLocalToday } from '../useLocalToday'
import { dateLabel } from '../financeTypes'
import { activityNames, kindNames, moodNames, type PersonalEntry, type PersonalList } from '../personalTypes'
import { PersonalForm } from '../components/PersonalForm'
import { TaskDialog } from '../components/TaskDialog'
import styles from './Journal.module.css'

export function PersonalPage(){
  const {user}=useAuth();const today=useLocalToday(user?.timezone||'Asia/Almaty');const client=useQueryClient();const [params]=useSearchParams()
  const [kind,setKind]=useState('');const [q,setQ]=useState('');const [deleted,setDeleted]=useState(false);const [offset,setOffset]=useState(0)
  const [start,setStart]=useState('');const [end,setEnd]=useState('')
  const [editing,setEditing]=useState<{entry:PersonalEntry;opener:HTMLElement}|null>(null)
  const [editorPending,setEditorPending]=useState(false)
  const [notice,setNotice]=useState('');const [undo,setUndo]=useState<string|null>(null)
  const validRange=!start||!end||start<=end
  const entries=useQuery({queryKey:['personal',user?.id,kind,q,deleted,start,end,offset],queryFn:()=>api<PersonalList>(`/personal/entries?${new URLSearchParams({...(kind?{kind}:{}),...(start?{start}:{}),...(end?{end}:{}),q,deleted:String(deleted),offset:String(offset),limit:'30'})}`),enabled:validRange})
  const focused=useQuery({queryKey:['personal-entry',user?.id,params.get('entry')],queryFn:()=>api<PersonalEntry>(`/personal/entries/${encodeURIComponent(params.get('entry')!)}`),enabled:!!params.get('entry')})
  async function refresh(){await Promise.all([client.invalidateQueries({queryKey:['personal']}),client.invalidateQueries({queryKey:['personal-entry']}),client.invalidateQueries({queryKey:['calendar']})])}
  const remove=useMutation({mutationFn:(id:string)=>api(`/personal/entries/${id}`,{method:'DELETE'}),onSuccess:async(_,id)=>{setUndo(id);setNotice('Запись перемещена в удалённые.');await refresh()}})
  const restore=useMutation({mutationFn:(id:string)=>api(`/personal/entries/${id}/restore`,json('POST',{})),onSuccess:async()=>{setUndo(null);setNotice('Запись восстановлена.');await refresh()}})
  function saved(){setNotice('Запись сохранена. История учитывает выбранные фильтры.');setUndo(null);void refresh()}
  const busy=remove.isPending||restore.isPending
  const card=(item:PersonalEntry)=><article className={`card ${styles.entry}`} key={item.id}>
    <div className={styles.meta}>{kindNames[item.kind]} · {item.date?dateLabel(item.date):'Без даты'}{item.kind!=='diary'&&` · ${activityNames[item.activity]} · ${item.completed?'Выполнено':'Запланировано'}`}{item.deleted&&' · Удалено'}</div>
    <h3>{item.title||'Запись дневника'}</h3>{item.body&&<p>{item.body}</p>}{item.kind==='diary'&&item.mood&&<p className="muted">Настроение: {moodNames[item.mood]}</p>}{item.impression&&<><h4>Впечатление</h4><p>{item.impression}</p></>}
    <div className={styles.actions}>{item.deleted?<button className="secondaryButton" disabled={busy} onClick={()=>restore.mutate(item.id)}>Восстановить запись</button>:<><button className="textButton" disabled={busy} onClick={event=>setEditing({entry:item,opener:event.currentTarget})}>Изменить запись</button><button className="textButton" disabled={busy} onClick={()=>remove.mutate(item.id)}>Удалить запись</button></>}</div>
  </article>
  return <div className={styles.page}><div className="pageHeader"><div><Link to="/sections" className="textButton">Разделы</Link><h1>Дневник</h1><p>Запишите мысль или событие. Записи видны только вам.</p></div></div>
    {notice&&<div className="successMessage" role="status">{notice} {undo&&<button className="textButton" disabled={busy} onClick={()=>restore.mutate(undo)}>Отменить удаление</button>}</div>}
    {(remove.error||restore.error)&&<p role="alert" className="errorMessage">{(remove.error||restore.error)?.message}</p>}
    <div className={`${styles.workspace} ${styles.diaryWorkspace}`}><section className={`card ${styles.compose}`}><h2>Новая запись</h2><PersonalForm date={params.get('date')&&/^\d{4}-\d{2}-\d{2}$/.test(params.get('date')!)?params.get('date')!:today} onSaved={saved}/></section>
      <section className={styles.stack}><div className={styles.historyHeading}><h2>История</h2><span className="muted">{entries.data ? `${entries.data.total} записей` : ''}</span></div><details className="card secondaryFilters"><summary>Поиск и фильтры</summary><div className={styles.filters}>
        <label>Тип в истории<select value={kind} onChange={event=>{setKind(event.target.value);setOffset(0)}}><option value="">Все записи</option>{Object.entries(kindNames).map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label>
        <label>Поиск по записям<input type="search" maxLength={100} value={q} onChange={event=>{setQ(event.target.value);setOffset(0)}}/></label>
        <label>С<input type="date" value={start} onChange={event=>{setStart(event.target.value);setOffset(0)}}/></label><label>По<input type="date" value={end} onChange={event=>{setEnd(event.target.value);setOffset(0)}}/></label>
        <label>Показывать<select value={String(deleted)} onChange={event=>{setDeleted(event.target.value==='true');setOffset(0)}}><option value="false">Активные</option><option value="true">Удалённые</option></select></label>
      </div></details>
      {params.get('entry')&&<section aria-label="Выбранная запись">{focused.isError?<p role="alert" className="errorMessage">Запись недоступна. <button className="textButton" onClick={()=>void focused.refetch()}>Повторить</button></p>:focused.data?card(focused.data):<p>Загружаем выбранную запись…</p>}</section>}
      {!validRange?<p role="alert" className="errorMessage">Начало периода должно быть не позже конца.</p>:entries.isError?<p role="alert" className="errorMessage">Не удалось загрузить записи. <button className="textButton" onClick={()=>void entries.refetch()}>Повторить</button></p>:!entries.data?<p className="muted">Загружаем записи…</p>:<>
        {!entries.data.items.length&&<p className="muted">По выбранным фильтрам записей пока нет. Создайте первую запись в форме.</p>}{entries.data.items.filter(item=>item.id!==focused.data?.id).map(card)}
        <div className={styles.actions}><span className="muted">Всего: {entries.data.total}</span>{offset>0&&<button className="secondaryButton" onClick={()=>setOffset(Math.max(0,offset-30))}>Назад</button>}{offset+30<entries.data.total&&<button className="secondaryButton" onClick={()=>setOffset(offset+30)}>Далее</button>}</div>
      </>}
    </section></div>
    <div className={styles.guidesLink}><a href="#personal-guides">Гайды по личному развитию</a></div><Guides area="personal" collapsePreferred />
    {editing&&<TaskDialog label="Редактировать запись" returnFocusTo={editing.opener} onClose={()=>{if(!editorPending)setEditing(null)}}><section className={`card ${styles.dialog}`}><h2>Редактировать запись</h2><PersonalForm initial={editing.entry} date={today} onSaved={()=>{setEditing(current=>current===editing?null:current);saved()}} onPendingChange={setEditorPending} onCancel={()=>{if(!editorPending)setEditing(null)}}/></section></TaskDialog>}
  </div>
}
