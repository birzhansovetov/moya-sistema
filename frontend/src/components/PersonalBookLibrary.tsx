import {ReaderView} from './ReaderView'
import {useEffect,useState} from 'react'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {api,json} from '../api'
import styles from './PersonalBookLibrary.module.css'

type FileBook={id:string;title:string;format:'epub'|'fb2'|'pdf';original_filename:string;size_bytes:number;page_count:number|null}
type Position={format:FileBook['format'];chapter?:number;position?:number;page?:number}
type ReaderState={location:Position|null;bookmarks:Position[]}
type TextPage={paragraphs:string[];chapters:{title:string;offset:number}[];total:number;next_offset:number|null}

export function PersonalBookLibrary(){
  const client=useQueryClient()
  const [active,setActive]=useState<FileBook|null>(null)
  const [position,setPosition]=useState(0)
  const [fontSize,setFontSize]=useState(18)
  const [warm,setWarm]=useState(false)
  const [message,setMessage]=useState('')
  const status=useQuery({queryKey:['personal-book-storage'],queryFn:()=>api<{enabled:boolean;max_bytes:number}>('/reading/books/uploads/status')})
  const books=useQuery({queryKey:['personal-books'],queryFn:()=>api<{items:FileBook[]}>('/reading/books/uploads'),enabled:status.data?.enabled===true})
  const state=useQuery({queryKey:['personal-book-state',active?.id],queryFn:()=>api<ReaderState>(`/reading/books/uploads/${active!.id}/reader-state`),enabled:!!active})
  useEffect(()=>{if(state.data?.location)setPosition(state.data.location.page??state.data.location.position??0)},[active?.id,state.data?.location])
  const text=useQuery({queryKey:['personal-book-text',active?.id,position],queryFn:()=>api<TextPage>(`/reading/books/uploads/${active!.id}/read?offset=${position}`),enabled:!!active&&active.format!=='pdf'})
  const upload=useMutation({mutationFn:async(file:File)=>{
    const form=new FormData();form.set('file',file);form.set('create_key',crypto.randomUUID())
    return api<FileBook>('/reading/books/uploads',{method:'POST',body:form})
  },onSuccess:async book=>{setMessage('Книга загружена.');await client.invalidateQueries({queryKey:['personal-books']});open(book)}})
  const save=useMutation({mutationFn:({book,location,bookmarks}:{book:FileBook;location:Position;bookmarks:Position[]})=>api<ReaderState>(`/reading/books/uploads/${book.id}/reader-state`,json('PUT',{location,bookmarks})),onSuccess:(_,input)=>{client.setQueryData(['personal-book-state',input.book.id],{location:input.location,bookmarks:input.bookmarks})}})
  const remove=useMutation({mutationFn:(book:FileBook)=>api(`/reading/books/uploads/${book.id}`,{method:'DELETE'}),onSuccess:async()=>{setActive(null);setMessage('Файл удалён.');await client.invalidateQueries({queryKey:['personal-books']})}})
  function open(book:FileBook){setActive(book);setPosition(0);setMessage('')}
  function move(value:number){if(!active)return;const next=Math.max(0,Math.min(active.format==='pdf'?(active.page_count||1)-1:Math.max(0,(text.data?.total||1)-1),value));setPosition(next);save.mutate({book:active,location:active.format==='pdf'?{format:'pdf',page:next}:{format:active.format,chapter:chapterAt(text.data?.chapters,next),position:next},bookmarks:state.data?.bookmarks||[]})}
  function resume(){const saved=state.data?.location;if(saved)setPosition(saved.format==='pdf'?(saved.page||0):(saved.position||0))}
  function bookmark(){if(!active)return;const location=active.format==='pdf'?{format:'pdf' as const,page:position}:{format:active.format,chapter:chapterAt(text.data?.chapters,position),position};save.mutate({book:active,location,bookmarks:[...(state.data?.bookmarks||[]).filter(item=>(item.page??item.position)!==(location.page??location.position)),location].slice(-20)});setMessage('Закладка сохранена.')}
  return <section className={`card ${styles.library}`} aria-labelledby="personal-library-title"><div className={styles.heading}><div><h2 id="personal-library-title">Личная библиотека</h2><p>EPUB, FB2 и PDF доступны только в вашем аккаунте.</p></div>{status.data?.enabled&&<label className="secondaryButton">Загрузить книгу<input className={styles.fileInput} type="file" accept=".epub,.fb2,.pdf" disabled={upload.isPending} onChange={event=>{const file=event.target.files?.[0];if(file)upload.mutate(file);event.target.value=''}}/></label>}</div>
    {status.isLoading&&<p role="status">Проверяем доступность загрузки…</p>}
    {status.isError&&<p role="alert" className="errorMessage">Не удалось проверить хранилище. <button className="textButton" onClick={()=>void status.refetch()}>Повторить</button></p>}
    {status.data&&!status.data.enabled&&<p className="muted">Загрузка файлов пока недоступна. Готовые книги и запись названия доступны ниже.</p>}
    {status.data?.enabled&&<p className="muted">Файл до 15 МБ. Форматы: EPUB, FB2, PDF. Сохраняется и место чтения. Ваши загруженные файлы не входят в скачиваемую резервную копию.</p>}
    {upload.isPending&&<p role="status">Сохраняем книгу…</p>}
    {(upload.error||books.error||text.error||state.error||save.error||remove.error)&&<p role="alert" className="errorMessage">{(upload.error||books.error||text.error||state.error||save.error||remove.error)?.message}</p>}
    {message&&<p role="status" className="successMessage">{message}</p>}
    {status.data?.enabled&&<>{books.data?.items.length===0&&<p className="muted">Здесь появятся ваши книги после загрузки.</p>}<div className={styles.shelf}>{books.data?.items.map(book=><button key={book.id} className={`${styles.book} ${active?.id===book.id?styles.selected:''}`} onClick={()=>open(book)} aria-pressed={active?.id===book.id}><span className={styles.format}>{book.format.toUpperCase()}</span><strong>{book.title}</strong><span>{(book.size_bytes/1024/1024).toFixed(1)} МБ</span></button>)}</div></>}
    {active&&<ReaderView title={active.title} onClose={()=>setActive(null)}><div className={styles.reader}><div className={styles.readerHeader}><div><h3>{active.title}</h3></div><div className={styles.controls}><button className="secondaryButton" onClick={resume} disabled={!state.data?.location}>Продолжить</button><button className="secondaryButton" onClick={bookmark} disabled={save.isPending}>Добавить закладку</button><button className="textButton" onClick={()=>setActive(null)}>Закрыть</button></div></div>
      {active.format==='pdf'?<div className={styles.pdf}><iframe title={`Книга ${active.title}`} src={`/api/reading/books/uploads/${active.id}/file#page=${position+1}`}/></div>:<div className={`${styles.paper} ${warm?styles.warm:''}`} style={{fontSize:`${fontSize}px`}}>{text.isLoading?<p role="status">Открываем текст…</p>:text.data?.paragraphs.map((paragraph,index)=><p key={`${position}-${index}`}>{paragraph}</p>)}</div>}
      <div className={styles.readerFooter}><div className={styles.controls}><button className="secondaryButton" onClick={()=>move(active.format==='pdf'?position-1:Math.max(0,position-60))} disabled={position===0}>Назад</button><span>{active.format==='pdf'?`Страница ${position+1} из ${active.page_count}`:`Фрагмент ${position+1} из ${text.data?.total||'…'}`}</span><button className="secondaryButton" onClick={()=>move(active.format==='pdf'?position+1:(text.data?.next_offset??position))} disabled={active.format==='pdf'?position+1>=(active.page_count||1):text.data?.next_offset==null}>Далее</button></div>{active.format!=='pdf'&&<div className={styles.controls}><button className="textButton" onClick={()=>setFontSize(Math.max(16,fontSize-2))} aria-label="Уменьшить шрифт">А−</button><button className="textButton" onClick={()=>setFontSize(Math.min(28,fontSize+2))} aria-label="Увеличить шрифт">А+</button><button className="textButton" onClick={()=>setWarm(!warm)} aria-pressed={warm}>Тёплый фон</button></div>}</div>
      <div className={styles.bottom}><button className="textButton" onClick={()=>{if(window.confirm(`Удалить файл «${active.title}» из личной библиотеки?`))remove.mutate(active)}} disabled={remove.isPending}>Удалить файл</button>{!!state.data?.bookmarks?.length&&<div className={styles.bookmarks}><span>Закладки:</span>{state.data?.bookmarks.map((mark,index)=><button key={index} className="textButton" onClick={()=>setPosition(mark.page??mark.position??0)}>{active.format==='pdf'?`Страница ${(mark.page||0)+1}`:`Фрагмент ${(mark.position||0)+1}`}</button>)}</div>}</div>
    </div></ReaderView>}
  </section>
}

function chapterAt(chapters:TextPage['chapters']|undefined,position:number){let index=0;chapters?.forEach((chapter,i)=>{if(chapter.offset<=position)index=i});return index}
