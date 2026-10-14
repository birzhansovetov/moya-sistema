import { act, renderHook } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { useLocalToday } from './useLocalToday'

test('local day advances at midnight in the profile time zone without a page event', () => {
  vi.useFakeTimers()
  try {
    vi.setSystemTime(new Date('2026-10-05T18:59:59Z'))
    const { result } = renderHook(() => useLocalToday('Asia/Almaty'))
    expect(result.current).toBe('2026-10-05')
    act(() => vi.advanceTimersByTime(2000))
    expect(result.current).toBe('2026-10-06')
  } finally {
    vi.useRealTimers()
  }
})
