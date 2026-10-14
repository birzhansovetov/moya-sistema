import { describe, expect, it } from 'vitest'
import { buildSportWeeks, weeklySportAdvice } from './sportSchedule'

describe('home training schedule', () => {
  it('shows every week and places sessions on the chosen weekdays after the start date', () => {
    const weeks = buildSportWeeks('2026-10-06', [1, 4], ['A', 'B'], 8)
    expect(weeks).toHaveLength(8)
    expect(weeks[0].sessions).toEqual([{ date: '2026-10-08', sessionId: 'B' }])
    expect(weeks[1].sessions).toEqual([{ date: '2026-10-12', sessionId: 'A' }, { date: '2026-10-15', sessionId: 'B' }])
  })

  it('uses recorded completion and difficulty for next-week guidance', () => {
    expect(weeklySportAdvice([{ session_id: 'A', difficulty: 5 }, { session_id: 'B', difficulty: 6 }], ['A', 'B']))
      .toMatch(/повторени/)
    expect(weeklySportAdvice([{ session_id: 'A', difficulty: 9 }, { session_id: 'B', difficulty: 8 }], ['A', 'B']))
      .toMatch(/повторите/)
    expect(weeklySportAdvice([{ session_id: 'A', difficulty: 5 }], ['A', 'B']))
      .toMatch(/не все занятия/)
  })
})
