import {useRef,useState} from 'react'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {api,json} from '../api'
import {useLocalToday} from '../useLocalToday'
import {useAuth} from '../auth'
import type {Word} from '../studyTypes'
import s from '../pages/Study.module.css'
type Card=Word&{review_id:string|null;due_date:string}
function ReviewCard({card,courseId,version,onSaved}:{card:Card;courseId:string;version:string;onSaved:()=>void}){
 const [revealed,setRevealed]=useState(false);const key=useRef(crypto.randomUUID());const [rating,setRating]=useState<string|null>(null)
 const save=useMutation({mutationFn:(value:string)=>api<{due_date:string}>('/study/reviews',json('POST',{course_id:courseId,version,card_id:card.id,rating:value,expected_review_id:card.review_id,create_key:key.current})),onSuccess:onSaved})
 function submit(value:string){if(rating!==value){key.current=crypto.randomUUID();setRating(value)}save.mutate(value)}
 return <section className={`card ${s.cardReview}`}><p className={s.subtle}>Вспомните перевод и составьте предложение</p><h3 lang="en">{card.word}</h3>{!revealed?<button className="secondaryButton" onClick={()=>setRevealed(true)}>Показать перевод</button>:<><strong>{card.translation}</strong><p lang="en">{card.example}</p><div className="healthActions"><button className="secondaryButton" disabled={save.isPending||save.isSuccess} onClick={()=>submit('again')}>Повторить завтра</button><button className="primaryButton" disabled={save.isPending||save.isSuccess} onClick={()=>submit('remembered')}>Вспомнил</button></div></>}{save.error&&<p role="alert" className="errorMessage">{save.error.message}</p>}{save.data&&<p role="status">Сохранено. Следующее повторение: {save.data.due_date}.</p>}</section>
}
export function StudyCards({courseId,version}:{courseId:string;version:string}){
 const {user}=useAuth();const client=useQueryClient();const today=useLocalToday(user?.timezone||'Asia/Almaty')
 const query=useQuery({queryKey:['study-cards',user?.id,courseId,version,user?.timezone,today],queryFn:()=>api<{items:Card[];total_learned:number;today:string}>(`/study/cards/${courseId}?version=${version}`)})
 return <section><h2>Повторение слов</h2><p>После успешного воспоминания интервал растёт: 1, 3, 7, 14, 30 дней. Если слово забыто — снова завтра. Даты учитывают ваш часовой пояс.</p>{query.isError&&<p role="alert" className="errorMessage">Не удалось обновить карточки. <button className="textButton" onClick={()=>void query.refetch()}>Повторить загрузку слов</button></p>}{!query.data?!query.isError&&<p>Загружаем слова…</p>:<><p className={s.subtle}>Изучено карточек: {query.data.total_learned}. К повторению: {query.data.items.length}.</p>{query.data.items[0]?<ReviewCard key={query.data.items[0].id+query.data.items[0].review_id} card={query.data.items[0]} courseId={courseId} version={version} onSaved={()=>void client.invalidateQueries({queryKey:['study-cards']})}/>:<p className="healthNotice">{query.data.total_learned?'На сегодня всё повторено. Вернитесь в следующий день повторения.':'Сначала сохраните результат урока — его слова появятся здесь.'}</p>}</>}</section>
}
