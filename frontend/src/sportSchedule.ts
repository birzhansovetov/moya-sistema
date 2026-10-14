import { dateOffset } from './taskTypes'

export type SportWeek = { number: number; sessions: Array<{ date: string; sessionId: string }> }

function isoWeekday(value: string) {
  const day = new Date(`${value}T12:00:00Z`).getUTCDay()
  return day === 0 ? 7 : day
}

export function buildSportWeeks(startedOn: string, weekdays: number[], sessionIds: string[], durationWeeks: number): SportWeek[] {
  const monday = dateOffset(startedOn, 1 - isoWeekday(startedOn))
  return Array.from({ length: durationWeeks }, (_, index) => ({
    number: index + 1,
    sessions: weekdays.map((weekday, position) => ({ date: dateOffset(monday, index * 7 + weekday - 1), sessionId: sessionIds[position] }))
      .filter(item => item.date >= startedOn && !!item.sessionId),
  }))
}

export function weeklySportAdvice(logs: Array<{ session_id: string; difficulty: number }>, sessionIds: string[]): string {
  if (!logs.length) return 'Запишите тренировки этой недели, чтобы получить совет на следующую.'
  if (sessionIds.some(id => !logs.some(log => log.session_id === id))) return 'Выполнены не все занятия: повторите нагрузку этой недели без ускорения.'
  if (logs.some(log => log.difficulty >= 8)) return 'Нагрузка была высокой: повторите этот уровень или уменьшите объём, если восстановление недостаточное.'
  if (logs.every(log => log.difficulty <= 6)) return 'Если техника была устойчивой, добавьте по одному повторению в пределах диапазона; вес увеличивайте только после уверенного выполнения всех подходов.'
  return 'Продолжайте с той же нагрузкой и техникой; сравните записи в конце следующей недели.'
}
