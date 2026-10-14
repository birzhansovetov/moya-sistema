import { expect, test } from 'vitest'
import { englishChapters } from './englishChapters'
import type { Lesson } from './studyTypes'

test('english lessons form named four-lesson chapters without losing their words', () => {
  const lessons = Array.from({ length: 24 }, (_, index) => ({
    id: `lesson-${index}`,
    level: index < 8 ? 'A2' : index < 16 ? 'B1' : 'B2',
    vocabulary: [{ id: `word-${index}`, word: `word${index}`, translation: 'значение', example: 'Example.' }],
  })) as Lesson[]
  const chapters = englishChapters(lessons)
  expect(chapters).toHaveLength(6)
  expect(chapters.map(chapter => chapter.lessons.length)).toEqual([4, 4, 4, 4, 4, 4])
  expect(chapters[0].title).toBe('Повседневные ситуации')
  expect(chapters[5].level).toBe('B2')
  expect(chapters.flatMap(chapter => chapter.lessons.flatMap(lesson => lesson.vocabulary || [])).map(word => word.id)).toHaveLength(24)
})
