import { useEffect, useState } from 'react'
import { localDate } from './taskTypes'

function untilNextLocalDay(timezone: string, now: number) {
  const current = localDate(timezone, new Date(now))
  let low = now
  let high = now + 48 * 60 * 60 * 1000
  while (high - low > 1000) {
    const middle = Math.floor((low + high) / 2)
    if (localDate(timezone, new Date(middle)) === current) low = middle
    else high = middle
  }
  return Math.max(1000, high - now)
}

export function useLocalToday(timezone: string) {
  const [today, setToday] = useState(() => localDate(timezone))
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    function refresh() {
      clearTimeout(timer)
      setToday(localDate(timezone))
      timer = setTimeout(refresh, untilNextLocalDay(timezone, Date.now()))
    }
    refresh()
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [timezone])
  return today
}
