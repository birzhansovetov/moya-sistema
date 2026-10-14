import type { Lesson } from './studyTypes'

export type EnglishChapter = { id: string; title: string; level: string; lessons: Lesson[] }

const titles: Record<string, string[]> = {
  A2: ['Повседневные ситуации', 'Уверенное общение', 'Итоговая практика'],
  B1: ['Истории и планы', 'Объяснять и аргументировать', 'Итоговая практика'],
  B2: ['Точные мысли', 'Сложные задачи', 'Итоговая практика'],
}

export function englishChapters(lessons: Lesson[]): EnglishChapter[] {
  return ['A2', 'B1', 'B2'].flatMap(level => {
    const atLevel = lessons.filter(lesson => lesson.level === level)
    const chapters: EnglishChapter[] = []
    for (let index = 0; index < atLevel.length; index += 4) {
      const number = Math.floor(index / 4)
      chapters.push({
        id: `${level.toLowerCase()}-${number + 1}`,
        title: titles[level]?.[number] || `Темы ${number + 1}`,
        level,
        lessons: atLevel.slice(index, index + 4),
      })
    }
    return chapters
  })
}
