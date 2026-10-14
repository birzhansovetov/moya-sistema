export type PersonalKind = 'diary' | 'event' | 'experiment'
export type PersonalEntry = { id: string; kind: PersonalKind; title: string; body: string; date: string | null; mood: string | null; activity: string; completed: boolean; impression: string; deleted: boolean }
export type PersonalList = {items: PersonalEntry[]; total: number; limit: number; offset: number}
export const kindNames = {diary:'Дневник',event:'Событие',experiment:'Хочу попробовать'}
export const moodNames: Record<string,string> = {great:'Отличное',good:'Хорошее',neutral:'Нейтральное',low:'Грустное',hard:'Тяжёлый день'}
export const activityNames: Record<string,string> = {meeting:'Встреча',hobby:'Хобби',travel:'Поездка',rest:'Отдых',other:'Другое'}
