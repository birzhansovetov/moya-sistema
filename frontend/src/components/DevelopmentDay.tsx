import {Link} from 'react-router-dom'
import {useQuery} from '@tanstack/react-query'
import {api} from '../api'
import {useAuth} from '../auth'
import type {Book,PageList} from '../readingTypes'
import type {PersonalCalendarItem} from '../taskTypes'
export function PersonalDayLinks({items,date}:{items:PersonalCalendarItem[];date:string}){
  return <div className="healthDayMeals">{items.map(item=><div className="healthDayItem" key={item.id}><Link to={`/personal?${new URLSearchParams({entry:item.id,date})}`}>{item.title}</Link><span className="muted">{item.completed?'Выполнено':item.kind==='experiment'?'Эксперимент':'Событие'}</span></div>)}</div>
}
export function DevelopmentDay({date,personalItems,personalError=false}:{date:string;personalItems:PersonalCalendarItem[];personalError?:boolean}){
  const {user}=useAuth()
  const books=useQuery({queryKey:['reading-books',user?.id,'daily'],queryFn:()=>api<PageList<Book>>('/reading/books?status=reading&limit=100'),enabled:!!user})
  const active=(books.data?.items||[]).filter(book=>!book.deleted&&book.status==='reading'&&(!book.start_date||book.start_date<=date)&&(!book.end_date||book.end_date>=date))
  return <section className="card healthDay todayPersonal"><h2>Личное и чтение</h2><p className="muted">Быстрые записи на выбранную дату</p><div className="todayQuickActions"><Link to={`/personal?date=${date}`} className="secondaryButton">Дневник</Link><Link to={`/education/reading?date=${date}`} className="secondaryButton">Чтение</Link></div>
    <h3>События</h3>{personalError?<p className="errorMessage">Личные события недоступны. Повторите загрузку календаря.</p>:personalItems.length?<PersonalDayLinks items={personalItems} date={date}/>:<p className="muted">Событий на эту дату пока нет. Датированные встречи и эксперименты появятся здесь из раздела «Личное».</p>}
    <h3>Книга в работе</h3>
    {books.isError?<p role="alert" className="errorMessage">Не удалось загрузить чтение. <button className="textButton" onClick={()=>void books.refetch()}>Повторить чтение</button></p>:!books.data?<p className="muted">Загружаем книги…</p>:!active.length?<p className="muted">Выберите книгу со статусом «Читаю» и настройте темп в разделе «Обучение / Книги».</p>:active.map(book=><div className="healthDayItem" key={book.id}><div><h3>{book.title}</h3><p>{book.current_page<book.pages?`Следующий отрезок: страницы ${book.current_page+1}–${book.next_page}`:'Все страницы отмечены — запишите итоговое впечатление.'}</p></div><Link to={`/education/reading?${new URLSearchParams({book:book.id,date})}`}>Открыть «{book.title}»</Link></div>)}
    {!!books.data&&books.data.total>100&&<Link to="/education/reading">Все читаемые книги</Link>}
    <Link to="/finance" className="todayFinanceLink">Записать расход в финансах</Link>
  </section>
}
