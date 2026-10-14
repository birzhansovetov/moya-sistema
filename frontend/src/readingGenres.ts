export const readingGenres = [
  { id: 'classic', label: 'Классическая литература' },
  { id: 'detective', label: 'Детективы' },
  { id: 'horror', label: 'Ужасы и страшные истории' },
  { id: 'fiction', label: 'Художественная литература' },
  { id: 'self_development', label: 'Саморазвитие' },
] as const

export type ReadingGenre = typeof readingGenres[number]['id']
