import {Pronunciation} from './Pronunciation'
import { useEffect, useState } from 'react'
import { englishChapters } from '../englishChapters'
import type { Lesson } from '../studyTypes'
import { StudyCards } from './StudyCards'
import s from '../pages/Study.module.css'

export function EnglishVocabulary({ lessons, currentLessonId, version }: { lessons: Lesson[]; currentLessonId: string | null; version: string }) {
  const chapters = englishChapters(lessons)
  const currentChapter = chapters.find(chapter => chapter.lessons.some(lesson => lesson.id === currentLessonId))
  const [chapterId, setChapterId] = useState(currentChapter?.id || chapters[0]?.id || '')
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const chapter = chapters.find(item => item.id === chapterId) || chapters[0]
  const words = chapter?.lessons.flatMap(lesson => lesson.vocabulary || []) || []
  const card = words[index]
  useEffect(() => { if (!chapterId && currentChapter) setChapterId(currentChapter.id) }, [chapterId, currentChapter])
  function chooseChapter(id: string) { setChapterId(id); setIndex(0); setRevealed(false) }
  function move(delta: number) { setIndex(value => (value + delta + words.length) % words.length); setRevealed(false) }
  return <section className={s.vocabularyPage}>
    <div><h2>Словарь по главам</h2><p>Слова взяты из уроков этого курса. Откройте карточку, вспомните значение и составьте своё предложение.</p></div>
    {chapters.length > 0 && <div className={s.chapterPicker} role="group" aria-label="Главы словаря">{chapters.map(item => <button type="button" key={item.id} aria-pressed={item.id === chapter?.id} onClick={() => chooseChapter(item.id)}>{item.level} · {item.title}</button>)}</div>}
    {card ? <div className={`card ${s.vocabularyCard}`}><p>Глава «{chapter.title}» · слово {index + 1} из {words.length}</p><h3 lang="en">{card.word}</h3><Pronunciation text={card.word} language="en"/>{revealed ? <div className={s.vocabularyAnswer}><strong>{card.translation}</strong><p lang="en">{card.example}</p></div> : <button type="button" className="primaryButton" onClick={() => setRevealed(true)}>Показать значение</button>}<div className={s.vocabularyControls}><button type="button" className="secondaryButton" onClick={() => move(-1)}>Предыдущее слово</button><button type="button" className="secondaryButton" onClick={() => move(1)}>Следующее слово</button></div></div> : <p>В этой главе пока нет слов.</p>}
    <details className={s.vocabularyReview}><summary>Повторить изученные слова по сроку</summary><StudyCards courseId="english" version={version} /></details>
  </section>
}
