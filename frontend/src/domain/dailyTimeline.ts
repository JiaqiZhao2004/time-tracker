import type { LocalDay } from './localDay'
import { displayCategory, type DisplayCategory } from '../types/category'
import type { DisplayEntry } from '../types/entry'

export type TimelineSegment = {
  categoryId: string
  start: Date
  end: Date
  projected: boolean
}

export type TimelineSummary = {
  category: DisplayCategory
  elapsedDurationMs: number
  percentage: number
}

export type DailyTimelineProjection = {
  segments: TimelineSegment[]
  visibleCategories: DisplayCategory[]
  summaries: TimelineSummary[]
  totalElapsedDurationMs: number
}

type ProjectionInput = {
  day: LocalDay
  now: Date
  entries: DisplayEntry[]
  precedingCategoryId: string | null
  categories: DisplayCategory[]
}

const sortedDisplayCategories = (categories: Map<string, DisplayCategory>): DisplayCategory[] =>
  [...categories.values()].sort(
    (left, right) => left.name.localeCompare(right.name) || left.categoryId.localeCompare(right.categoryId),
  )

export const projectDailyTimeline = ({
  day,
  now,
  entries,
  precedingCategoryId,
  categories,
}: ProjectionInput): DailyTimelineProjection => {
  const displayCategories = new Map(categories.map((category) => [category.categoryId, category]))
  const datedEntries = entries
    .map((entry) => ({ ...entry, instant: new Date(entry.timestamp) }))
    .filter((entry) => entry.instant >= day.start && entry.instant < day.end)
    .sort((left, right) => left.instant.getTime() - right.instant.getTime())

  for (const entry of datedEntries) {
    if (displayCategories.has(entry.categoryId)) {
      continue
    }
    displayCategories.set(
      entry.categoryId,
      displayCategory({
        categoryId: entry.categoryId,
        name: entry.categoryName,
        isActive: false,
      }),
    )
  }

  if (precedingCategoryId && !displayCategories.has(precedingCategoryId)) {
    displayCategories.set(
      precedingCategoryId,
      displayCategory({
        categoryId: precedingCategoryId,
        name: precedingCategoryId,
        isActive: false,
      }),
    )
  }

  const segments: TimelineSegment[] = []
  let categoryId = precedingCategoryId
  let cursor = day.start

  for (const entry of datedEntries) {
    if (categoryId && entry.instant > cursor) {
      segments.push({ categoryId, start: cursor, end: entry.instant, projected: false })
    }
    categoryId = entry.categoryId
    cursor = entry.instant
  }

  if (categoryId && day.end > cursor) {
    const isCurrentDay = now >= day.start && now < day.end
    if (isCurrentDay) {
      if (now > cursor) {
        segments.push({ categoryId, start: cursor, end: now, projected: false })
      }
      const projectedStart = now > cursor ? now : cursor
      if (projectedStart < day.end) {
        segments.push({ categoryId, start: projectedStart, end: day.end, projected: true })
      }
    } else {
      segments.push({ categoryId, start: cursor, end: day.end, projected: false })
    }
  }

  const elapsedTimes = new Map<string, number>()
  for (const segment of segments) {
    if (!segment.projected) {
      const duration = segment.end.getTime() - segment.start.getTime()
      if (duration > 0) {
        elapsedTimes.set(segment.categoryId, (elapsedTimes.get(segment.categoryId) ?? 0) + duration)
      }
    }
  }

  const totalElapsedDurationMs = [...elapsedTimes.values()].reduce((sum, duration) => sum + duration, 0)
  const summaries = [...elapsedTimes.entries()]
    .map(([summaryCategoryId, elapsedDurationMs]) => ({
      category:
        displayCategories.get(summaryCategoryId) ??
        displayCategory({ categoryId: summaryCategoryId, name: summaryCategoryId, isActive: false }),
      elapsedDurationMs,
      percentage:
        totalElapsedDurationMs === 0 ? 0 : Math.round((elapsedDurationMs / totalElapsedDurationMs) * 100),
    }))
    .sort((left, right) => right.elapsedDurationMs - left.elapsedDurationMs)

  const usedCategoryIds = new Set(segments.map((segment) => segment.categoryId))
  const visibleCategories = sortedDisplayCategories(displayCategories).filter(
    (category) => category.isActive || usedCategoryIds.has(category.categoryId),
  )

  return { segments, visibleCategories, summaries, totalElapsedDurationMs }
}
