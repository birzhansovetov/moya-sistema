import {useQuery} from '@tanstack/react-query'
import {Link} from 'react-router-dom'
import {api} from '../api'
import {useAuth} from '../auth'
import type {StudyState} from '../studyTypes'
import type {Book,PageList} from '../readingTypes'
import styles from './Education.module.css'

function useCourseState(courseId:string,userId:string|undefined){
 return useQuery({queryKey:['study-state',userId,courseId,null,0],queryFn:()=>api<StudyState>(`/study/state/${courseId}?history_offset=0`),enabled:!!userId})
}

export function EducationPage(){
 const {user}=useAuth()
 const java=useCourseState('java',user?.id)
 const go=useCourseState('go',user?.id)
 const catalog=useQuery({queryKey:['study-catalog',user?.id],queryFn:()=>api<{items:{id:string;lesson_count:number}[]}>('/study/catalog'),enabled:!!user})
 const books=useQuery({queryKey:['reading-books',user?.id,'daily'],queryFn:()=>api<PageList<Book>>('/reading/books?status=reading&limit=100'),enabled:!!user})
 const activeBook=books.data?.items.find(book=>!book.deleted&&book.status==='reading')
 const courses=[
  {id:'go',title:'Go: от основ до API',description:'Шесть глав, практика и собственный сервис.',chapters:'6 глав',to:'/profession/go',state:go},
  {id:'java',title:'Основы Java',description:'Язык, примеры и упражнения в своём темпе.',chapters:'Основы',to:'/profession/java',state:java},
 ]
 return <div className={styles.page}>
  <div className={styles.header}><Link className="textButton" to="/sections">Разделы</Link><h1>Обучение</h1><p>Выберите курс или продолжите чтение.</p></div>
  <section className={styles.featured} aria-labelledby="education-courses"><div className={styles.sectionHeading}><h2 id="education-courses">Курсы</h2></div><div className={styles.courseGrid}>{courses.map(course=>{
   const state=course.state.data
   const catalogCount=catalog.data?.items.find(item=>item.id===course.id)?.lesson_count
   const total=state?.plan?.lesson_ids.length||catalogCount||0
   const done=state?.completed.length||0
   const percent=state?.plan?Math.round(done/Math.max(total,1)*100):0
   const to=state?.active_plan?`${course.to}?${new URLSearchParams({plan:state.active_plan.id,...(state.next_lesson_id?{lesson:state.next_lesson_id}:{})})}`:course.to
   return <Link to={to} className={styles.courseCard} key={course.id}><div className={styles.cardTop}><span className={styles.courseMark}>{course.id==='go'?'Go':'J'}</span><span className={styles.courseType}>{course.chapters}{total?` · ${total} занятий`:''}</span></div><div><h3>{course.title}</h3><p>{course.description}</p></div><div className={styles.cardBottom}><div className={styles.progressLine}><span>{course.state.isError?'Прогресс недоступен':state?.active_plan?`${done} из ${total} пройдено`:'Можно начать с основ'}</span><strong>{course.state.isError?'':state?.active_plan?`${percent}%`:''}</strong></div><div className={styles.progressTrack} role="progressbar" aria-label={`Прогресс курса ${course.title}`} aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}><span style={{width:`${percent}%`}}/></div><span className={styles.courseAction}>{state?.active_plan?'Продолжить курс':'Посмотреть курс'}</span></div></Link>
  })}</div></section>
  <Link to={activeBook?`/books?book=${activeBook.id}`:'/books'} className={styles.readingCard}><span className={styles.readingMark} aria-hidden="true">К</span><div><span className={styles.eyebrow}>ЧТЕНИЕ</span><h2>{activeBook?activeBook.title:'Книги и дневник чтения'}</h2><p>{books.isError?'Не удалось загрузить прогресс чтения. Библиотеку можно открыть.':activeBook?`Страница ${activeBook.current_page} из ${activeBook.pages}. Продолжайте чтение или запишите мысль.`:'Выберите книгу, настройте темп и сохраняйте заметки.'}</p></div><span className={styles.readingAction}>{activeBook?'Продолжить чтение':'Открыть книги'}</span></Link>
 </div>
}
