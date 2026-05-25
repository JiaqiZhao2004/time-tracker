import { env } from 'node:process'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import {
  formatLocalDatetimeInput,
  instantAtTimelinePosition,
  localDayContaining,
  localWeekContaining,
  localWeekDates,
  shiftLocalDay,
} from './localDay'

const originalTimezone = env.TZ

describe('Local Day', () => {
  beforeAll(() => {
    env.TZ = 'Pacific/Auckland'
  })

  afterAll(() => {
    if (originalTimezone === undefined) {
      delete env.TZ
    } else {
      env.TZ = originalTimezone
    }
  })

  it('keeps a positive-offset local calendar date for requests', () => {
    const day = localDayContaining(new Date(2026, 4, 24, 12), 'Pacific/Auckland')

    expect(day.date).toBe('2026-05-24')
    expect(day.start.toISOString()).toBe('2026-05-23T12:00:00.000Z')
  })

  it('shifts days without allowing navigation past the latest day', () => {
    const latest = localDayContaining(new Date(2026, 4, 24), 'Pacific/Auckland')
    const previous = shiftLocalDay(latest, -1, latest)

    expect(previous.date).toBe('2026-05-23')
    expect(shiftLocalDay(latest, 1, latest)).toBe(latest)
  })

  it('finds the Monday-starting local week containing a selected day', () => {
    const selectedDay = localDayContaining(new Date(2026, 4, 24), 'Pacific/Auckland')
    const week = localWeekContaining(selectedDay)

    expect(week.date).toBe('2026-05-18')
    expect(week.start.getDay()).toBe(1)
    expect(week.end.getDate()).toBe(25)
  })

  it('keeps local-midnight week boundaries across daylight saving changes', () => {
    const selectedDay = localDayContaining(new Date(2026, 8, 23), 'Pacific/Auckland')
    const week = localWeekContaining(selectedDay)

    expect(week.date).toBe('2026-09-21')
    expect(week.end.getHours()).toBe(0)
    expect(week.end.getTime() - week.start.getTime()).toBe(167 * 60 * 60 * 1000)
  })

  it('lists each request date inside a selected week', () => {
    const week = localWeekContaining(localDayContaining(new Date(2026, 8, 23), 'Pacific/Auckland'))

    expect(localWeekDates(week)).toEqual([
      '2026-09-21',
      '2026-09-22',
      '2026-09-23',
      '2026-09-24',
      '2026-09-25',
      '2026-09-26',
      '2026-09-27',
    ])
  })

  it('formats manual entry values in local calendar time', () => {
    expect(formatLocalDatetimeInput(new Date(2026, 4, 24, 9, 5))).toBe('2026-05-24T09:05')
  })

  it('maps positions inside the selected local day to instants', () => {
    const day = localDayContaining(new Date(2026, 4, 24), 'Pacific/Auckland')

    expect(instantAtTimelinePosition(day, 0.5).getHours()).toBe(12)
    expect(instantAtTimelinePosition(day, -1)).toEqual(day.start)
    expect(instantAtTimelinePosition(day, 2)).toEqual(day.end)
  })
})
