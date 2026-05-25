import { describe, expect, it } from 'vitest'
import { displayCategory } from '../types/category'
import type { DisplayEntry } from '../types/entry'
import { projectDailyTimeline, projectTimelineRange } from './dailyTimeline'
import { localDayContaining, localWeekContaining } from './localDay'

const HOUR_MS = 60 * 60 * 1000
const day = localDayContaining(new Date(2026, 4, 20, 12))

const categories = [
  displayCategory({ categoryId: 'work', name: 'Work', isActive: true }),
  displayCategory({ categoryId: 'rest', name: 'Rest', isActive: true }),
]

const at = (hour: number): Date => {
  const instant = new Date(day.start)
  instant.setHours(hour, 0, 0, 0)
  return instant
}

const entry = (categoryId: string, name: string, hour: number): DisplayEntry => ({
  id: `${categoryId}-${hour}`,
  categoryId,
  categoryName: name,
  timestamp: at(hour).toISOString(),
})

describe('Daily Timeline', () => {
  it('continues a preceding category across a historical day without entries', () => {
    const projection = projectDailyTimeline({
      day,
      now: new Date(day.end.getTime() + HOUR_MS),
      entries: [],
      precedingCategoryId: 'work',
      categories,
    })

    expect(projection.segments).toEqual([
      { categoryId: 'work', start: day.start, end: day.end, projected: false },
    ])
    expect(projection.totalElapsedDurationMs).toBe(24 * HOUR_MS)
  })

  it('orders entries before constructing historical segments', () => {
    const projection = projectDailyTimeline({
      day,
      now: new Date(day.end.getTime() + HOUR_MS),
      entries: [entry('rest', 'Rest', 12), entry('work', 'Work', 9)],
      precedingCategoryId: null,
      categories,
    })

    expect(projection.segments.map((segment) => [segment.categoryId, segment.start.getHours(), segment.end.getHours()]))
      .toEqual([
        ['work', 9, 12],
        ['rest', 12, 0],
      ])
  })

  it('renders a faded continuation but excludes it from elapsed totals', () => {
    const projection = projectDailyTimeline({
      day,
      now: at(12),
      entries: [],
      precedingCategoryId: 'work',
      categories,
    })

    expect(projection.segments).toEqual([
      { categoryId: 'work', start: day.start, end: at(12), projected: false },
      { categoryId: 'work', start: at(12), end: day.end, projected: true },
    ])
    expect(projection.totalElapsedDurationMs).toBe(12 * HOUR_MS)
    expect(projection.summaries).toEqual([
      expect.objectContaining({ elapsedDurationMs: 12 * HOUR_MS, percentage: 100 }),
    ])
  })

  it('uses a resolved fallback name for missing display categories', () => {
    const projection = projectDailyTimeline({
      day,
      now: new Date(day.end.getTime() + HOUR_MS),
      entries: [entry('archived', 'archived', 9)],
      precedingCategoryId: null,
      categories,
    })

    expect(projection.visibleCategories.find((category) => category.categoryId === 'archived')?.name)
      .toBe('archived')
    expect(projection.summaries[0]?.category.name).toBe('archived')
  })
})

describe('Range Timeline', () => {
  it('aggregates categories across a historical selected week', () => {
    const week = localWeekContaining(day)
    const mondayMorning = new Date(week.start)
    mondayMorning.setHours(8)
    const tuesdayMorning = new Date(week.start)
    tuesdayMorning.setDate(tuesdayMorning.getDate() + 1)
    tuesdayMorning.setHours(8)

    const projection = projectTimelineRange({
      range: week,
      now: new Date(week.end.getTime() + HOUR_MS),
      entries: [
        {
          id: 'work-monday',
          categoryId: 'work',
          categoryName: 'Work',
          timestamp: mondayMorning.toISOString(),
        },
        {
          id: 'rest-tuesday',
          categoryId: 'rest',
          categoryName: 'Rest',
          timestamp: tuesdayMorning.toISOString(),
        },
      ],
      precedingCategoryId: null,
      categories,
    })

    expect(projection.totalElapsedDurationMs).toBe(6 * 24 * HOUR_MS + 16 * HOUR_MS)
    expect(projection.summaries.map((summary) => summary.category.categoryId)).toEqual(['rest', 'work'])
  })

  it('counts a running current-week category only through now', () => {
    const week = localWeekContaining(day)
    const now = new Date(week.start)
    now.setDate(now.getDate() + 2)
    now.setHours(12)

    const projection = projectTimelineRange({
      range: week,
      now,
      entries: [],
      precedingCategoryId: 'work',
      categories,
    })

    expect(projection.totalElapsedDurationMs).toBe(60 * HOUR_MS)
    expect(projection.segments[projection.segments.length - 1]?.projected).toBe(true)
  })
})
