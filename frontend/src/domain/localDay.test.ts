import { env } from 'node:process'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import {
  formatLocalDatetimeInput,
  instantAtTimelinePosition,
  localDayContaining,
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
