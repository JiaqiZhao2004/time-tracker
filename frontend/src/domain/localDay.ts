export type LocalDay = {
  start: Date
  end: Date
  date: string
  timezone: string
  label: string
}

const pad = (value: number): string => value.toString().padStart(2, '0')

const runtimeTimezone = (): string => Intl.DateTimeFormat().resolvedOptions().timeZone

const localCalendarDate = (date: Date): string =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`

export const localDayContaining = (instant: Date, timezone: string = runtimeTimezone()): LocalDay => {
  const start = new Date(instant)
  start.setHours(0, 0, 0, 0)

  const end = new Date(start)
  end.setDate(end.getDate() + 1)

  return {
    start,
    end,
    date: localCalendarDate(start),
    timezone,
    label: start.toLocaleDateString(),
  }
}

export const todayLocalDay = (now: Date = new Date(), timezone?: string): LocalDay =>
  localDayContaining(now, timezone)

export const shiftLocalDay = (
  day: LocalDay,
  direction: -1 | 1,
  latestDay: LocalDay = todayLocalDay(new Date(), day.timezone),
): LocalDay => {
  const candidateStart = new Date(day.start)
  candidateStart.setDate(candidateStart.getDate() + direction)
  const candidate = localDayContaining(candidateStart, day.timezone)

  return candidate.start > latestDay.start ? day : candidate
}

export const formatLocalDatetimeInput = (instant: Date): string =>
  `${localCalendarDate(instant)}T${pad(instant.getHours())}:${pad(instant.getMinutes())}`

export const instantAtTimelinePosition = (day: LocalDay, fraction: number): Date => {
  const boundedFraction = Math.min(1, Math.max(0, fraction))
  const duration = day.end.getTime() - day.start.getTime()
  return new Date(day.start.getTime() + boundedFraction * duration)
}
