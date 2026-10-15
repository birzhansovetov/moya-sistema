import {Guides} from '../components/Guides'
import {BookSuggestions,type Suggestion} from '../components/BookSuggestions'
import {PersonalBookLibrary} from '../components/PersonalBookLibrary'
import {useRef,useState} from 'react'
import {Link,useSearchParams} from 'react-router-dom'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {api,json} from '../api'
import {useAuth} from '../auth'
import {useLocalToday} from '../useLocalToday'
import {dateLabel} from '../financeTypes'
import {bookStatuses,reflectionNames,type Book,type ReadingLog,type PageList} from '../readingTypes'
import {BookForm} from '../components/BookForm'
import {ReadingLogForm} from '../components/ReadingLogForm'
import {TaskDialog} from '../components/TaskDialog'
import styles from './Journal.module.css'

export function ReadingPage(){
  const {user}=useAuth();const today=useLocalToday(user?.timezone||'Asia/Almaty');const client=useQueryClient();const [params,setParams]=useSearchParams();const bookId=params.get('book')
  const [q,setQ]=useState('');const [deleted,setDeleted]=useState(false);const [offset,setOffset]=useState(0)
  const [logSearch,setLogSearch]=useState('');const [logDeleted,setLogDeleted]=useState(false);const [logOffset,setLogOffset]=useState(0)
  const [bookEditor,setBookEditor]=useState<{book?:Book;suggestion?:Suggestion;opener:HTMLElement}|null>(null);const [logEditor,setLogEditor]=useState<{log:ReadingLog;opener:HTMLElement}|null>(null)
  const [bookPending,setBookPending]=useState(false);const [logPending,setLogPending]=useState(false)
  const bookEditorRef=useRef(bookEditor);bookEditorRef.current=bookEditor
  const [notice,setNotice]=useState('');const [undo,setUndo]=useState<string|null>(null)
  const books=useQuery({queryKey:['reading-books',user?.id,q,deleted,offset],queryFn:()=>api<PageList<Book>>(`/reading/books?${new URLSearchParams({q,deleted:String(deleted),offset:String(offset)})}`)})
  const bookQuery=useQuery({queryKey:['reading-book',user?.id,bookId],queryFn:()=>api<Book>(`/reading/books/${encodeURIComponent(bookId!)}`),enabled:!!bookId})
  const logs=useQuery({queryKey:['reading-logs',user?.id,bookId,logSearch,logDeleted,logOffset],queryFn:()=>api<PageList<ReadingLog>>(`/reading/books/${encodeURIComponent(bookId!)}/logs?${new URLSearchParams({q:logSearch,deleted:String(logDeleted),offset:String(logOffset)})}`),enabled:!!bookId})
  async function refresh(){await Promise.all(['reading-books','reading-book','reading-logs'].map(key=>client.invalidateQueries({queryKey:[key]})))}
  const remove=useMutation({mutationFn:(path:string)=>api(path,{method:'DELETE'}),onSuccess:async(_,path)=>{setNotice('Перемещено в удалённые.');setUndo(path);await refresh()}})
  const restore=useMutation({mutationFn:(path:string)=>api(path+'/restore',json('POST',{})),onSuccess:async()=>{setNotice('Восстановлено.');setUndo(null);await refresh()}})
  const book=bookQuery.data;const busy=remove.isPending||restore.isPending
  function select(id:string){setParams({book:id,...(params.get('date')?{date:params.get('date')!}:{})});setLogOffset(0);setLogSearch('');setLogDeleted(false)}
  function savedBook(item:Book,origin:typeof bookEditor){if(bookEditorRef.current===origin){setBookEditor(null);select(item.id)}setNotice('Книга сохранена.');setUndo(null);void refresh()}
  function savedLog(){setNotice('Чтение сохранено.');setUndo(null);void refresh()}
  return <div className={styles.page}><div className="pageHeader"><div><Link className="textButton" to="/education">Обучение</Link><h1>Книги и чтение</h1><p>Выберите книгу из библиотеки или запишите название той, которую читаете.</p></div><button className="primaryButton" onClick={event=>setBookEditor({opener:event.currentTarget})}>Записать свою книгу</button></div>
    {notice&&<div role="status" className="successMessage">{notice} {undo&&<button className="textButton" disabled={busy} onClick={()=>restore.mutate(undo)}>Отменить удаление</button>}</div>}
    {(remove.error||restore.error)&&<p className="errorMessage" role="alert">{(remove.error||restore.error)?.message}</p>}
    <div className={styles.workspace}><section className={styles.stack}><h2>Моя полка</h2><details className="card secondaryFilters"><summary>Поиск и фильтры книг</summary><div className={styles.filters}><label>Поиск книг<input type="search" maxLength={100} value={q} onChange={event=>{setQ(event.target.value);setOffset(0)}}/></label><label>Показывать книги<select value={String(deleted)} onChange={event=>{setDeleted(event.target.value==='true');setOffset(0)}}><option value="false">Активные</option><option value="true">Удалённые</option></select></label></div></details>
      {books.isError?<p role="alert" className="errorMessage">Не удалось загрузить книги. <button className="textButton" onClick={()=>void books.refetch()}>Повторить</button></p>:!books.data?<p>Загружаем книги…</p>:<>{!books.data.items.length&&<p className="muted">Книг по этим фильтрам пока нет. Добавьте книгу или выберите её в подборке ниже.</p>}{books.data.items.map(item=><article key={item.id} className={`card ${styles.entry}`}><h3>{item.title}</h3><p className="muted">{item.author} · {bookStatuses[item.status]}</p>{item.pages>0?<p>{item.current_page} из {item.pages} страниц</p>:<p className="muted">Количество страниц пока не указано</p>}<button className="secondaryButton" aria-pressed={bookId===item.id} onClick={()=>select(item.id)}>Открыть «{item.title}»</button></article>)}<div className={styles.actions}><span>Всего: {books.data.total}</span>{offset>0&&<button className="secondaryButton" onClick={()=>setOffset(Math.max(0,offset-30))}>Назад</button>}{offset+30<books.data.total&&<button className="secondaryButton" onClick={()=>setOffset(offset+30)}>Далее</button>}</div></>}
    </section><section className={styles.stack}>
      {!bookId?<section className="card"><h2>Выберите книгу</h2><p>Откройте книгу на полке. Здесь появятся ваш план чтения, заметки и история страниц.</p></section>:<>
        {bookQuery.isError&&<p role="alert" className="errorMessage">Не удалось обновить книгу. <button className="textButton" onClick={()=>void bookQuery.refetch()}>Повторить</button></p>}
        {!book?!bookQuery.isError&&<p>Загружаем книгу…</p>:<>
          <section className={`card ${styles.entry}`}><h2>{book.title}</h2><p className="muted">{book.author} · {bookStatuses[book.status]}{book.deleted&&' · Удалена'}</p>
            {book.cover_url&&<a className="textButton" href={book.cover_url} target="_blank" rel="noreferrer">Открыть обложку</a>}
            {book.pages>0?<><p>{book.current_page} / {book.pages} страниц</p><progress aria-label="Прогресс чтения" max={book.pages} value={book.current_page}/></>:<p className="muted">Книга добавлена по названию. Для отслеживания страниц укажите их количество в настройках.</p>}
            {book.start_date&&<p className="muted">Начало: {dateLabel(book.start_date)}</p>}{book.end_date&&<p className="muted">Завершение: {dateLabel(book.end_date)}</p>}
            {book.status==='reading'&&!book.deleted&&book.pages>0&&<div className="healthNotice"><h3>Следующее занятие</h3>{book.current_page<book.pages?<><strong>Страницы {book.current_page+1}–{book.next_page}</strong><p>Прочитайте в удобном темпе, затем запишите одну мысль своими словами и отметьте страницу.</p></>:<p>Все страницы отмечены. Запишите итоговое впечатление и измените статус на «Прочитал».</p>}</div>}
            {book.final_impression&&<><h3>Итоговое впечатление</h3><p>{book.final_impression}</p></>}
            <div className={styles.actions}>{book.deleted?<button className="secondaryButton" disabled={busy} onClick={()=>restore.mutate(`/reading/books/${book.id}`)}>Восстановить книгу</button>:<><button className="textButton" onClick={event=>setBookEditor({book,opener:event.currentTarget})}>Настроить книгу и план</button><button className="textButton" disabled={busy} onClick={()=>remove.mutate(`/reading/books/${book.id}`)}>Удалить книгу</button></>}</div>
          </section>
          {!book.deleted&&<section className="card"><h2>Запись чтения</h2><ReadingLogForm key={book.id} book={book} date={params.get('date')&&/^\d{4}-\d{2}-\d{2}$/.test(params.get('date')!)?params.get('date')!:today} today={today} onSaved={savedLog}/></section>}
          <section className={styles.stack}><h2>Дневник чтения</h2><details className="card secondaryFilters"><summary>Поиск и фильтры заметок</summary><div className={styles.filters}><label>Поиск по заметкам<input type="search" maxLength={100} value={logSearch} onChange={event=>{setLogSearch(event.target.value);setLogOffset(0)}}/></label><label>Показывать заметки<select value={String(logDeleted)} onChange={event=>{setLogDeleted(event.target.value==='true');setLogOffset(0)}}><option value="false">Активные</option><option value="true">Удалённые</option></select></label></div></details>
            {logs.isError?<p className="errorMessage" role="alert">Не удалось загрузить заметки. <button className="textButton" onClick={()=>void logs.refetch()}>Повторить</button></p>:!logs.data?<p>Загружаем заметки…</p>:<>{!logs.data.items.length&&<p className="muted">По этим фильтрам заметок пока нет.</p>}{logs.data.items.map(item=><article className={`card ${styles.entry}`} key={item.id}><div className={styles.meta}>{dateLabel(item.date)}{item.page!==null&&` · страница ${item.page}`}{item.chapter&&` · ${item.chapter}`}</div>{item.text&&<p>{item.text}</p>}{Object.entries(item.reflection).map(([field,value])=><div key={field}><h4>{reflectionNames[field]}</h4><p>{value}</p></div>)}<div className={styles.actions}>{item.deleted?<button className="textButton" disabled={busy||book.deleted} onClick={()=>restore.mutate(`/reading/books/${book.id}/logs/${item.id}`)}>Восстановить заметку</button>:<><button className="textButton" disabled={book.deleted} onClick={event=>setLogEditor({log:item,opener:event.currentTarget})}>Изменить заметку</button><button className="textButton" disabled={busy||book.deleted} onClick={()=>remove.mutate(`/reading/books/${book.id}/logs/${item.id}`)}>Удалить заметку</button></>}</div></article>)}<div className={styles.actions}><span>Всего: {logs.data.total}</span>{logOffset>0&&<button className="secondaryButton" onClick={()=>setLogOffset(Math.max(0,logOffset-30))}>Назад</button>}{logOffset+30<logs.data.total&&<button className="secondaryButton" onClick={()=>setLogOffset(logOffset+30)}>Далее</button>}</div></>}
          </section>
        </>}
      </>}
    </section></div>
    <PersonalBookLibrary />
    <Guides area="reading" />
    <BookSuggestions onChoose={(suggestion,opener)=>setBookEditor({suggestion,opener})} />
    {bookEditor&&<TaskDialog label={bookEditor.book?'Настроить книгу':'Добавить книгу'} returnFocusTo={bookEditor.opener} onClose={()=>{if(!bookPending)setBookEditor(null)}}><section className={`card ${styles.dialog}`}><h2>{bookEditor.book?'Книга и план чтения':'Новая книга'}</h2><BookForm suggestion={bookEditor.suggestion} initial={bookEditor.book} onSaved={item=>savedBook(item,bookEditor)} onPendingChange={setBookPending} onCancel={()=>{if(!bookPending)setBookEditor(null)}}/></section></TaskDialog>}
    {logEditor&&book&&<TaskDialog label="Изменить заметку чтения" returnFocusTo={logEditor.opener} onClose={()=>{if(!logPending)setLogEditor(null)}}><section className={`card ${styles.dialog}`}><h2>Изменить заметку</h2><ReadingLogForm initial={logEditor.log} book={book} date={today} today={today} onSaved={()=>{setLogEditor(current=>current===logEditor?null:current);savedLog()}} onPendingChange={setLogPending} onCancel={()=>{if(!logPending)setLogEditor(null)}}/></section></TaskDialog>}
  </div>
}
