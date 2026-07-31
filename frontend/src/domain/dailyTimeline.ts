import type { LocalDay, LocalRange } from './localDay'
import { displayCategories, displayCategory, type DisplayCategory } from '../types/category'
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

export type TimelineProjection = {
  segments: TimelineSegment[]
  visibleCategories: DisplayCategory[]
  summaries: TimelineSummary[]
  totalElapsedDurationMs: number
}

type CommonProjectionInput = {
  now: Date
  entries: DisplayEntry[]
  precedingCategoryId: string | null
  categories: DisplayCategory[]
}

type DailyProjectionInput = CommonProjectionInput & {
  day: LocalDay
}

type RangeProjectionInput = CommonProjectionInput & {
  range: LocalRange
}

const sortedDisplayCategories = (categories: Map<string, DisplayCategory>): DisplayCategory[] =>
  [...categories.values()].sort(
    (left, right) => left.name.localeCompare(right.name) || left.categoryId.localeCompare(right.categoryId),
  )

export const projectTimelineRange = ({
  range,
  now,
  entries,
  precedingCategoryId,
  categories,
}: RangeProjectionInput): TimelineProjection => {
  const categoryDefinitions = new Map(
    categories.map(({ categoryId, name, isActive }) => [categoryId, { categoryId, name, isActive }]),
  )
  const datedEntries = entries
    .map((entry) => ({ ...entry, instant: new Date(entry.timestamp) }))
    .filter((entry) => entry.instant >= range.start && entry.instant < range.end)
    .sort((left, right) => left.instant.getTime() - right.instant.getTime())

  for (const entry of datedEntries) {
    if (categoryDefinitions.has(entry.categoryId)) {
      continue
    }
    categoryDefinitions.set(
      entry.categoryId,
      {
        categoryId: entry.categoryId,
        name: entry.categoryName,
        isActive: false,
      },
    )
  }

  if (precedingCategoryId && !categoryDefinitions.has(precedingCategoryId)) {
    categoryDefinitions.set(
      precedingCategoryId,
      {
        categoryId: precedingCategoryId,
        name: precedingCategoryId,
        isActive: false,
      },
    )
  }

  const resolvedCategories = displayCategories([...categoryDefinitions.values()])
  const displayCategoryMap = new Map(resolvedCategories.map((category) => [category.categoryId, category]))

  const segments: TimelineSegment[] = []
  let categoryId = precedingCategoryId
  let cursor = range.start

  for (const entry of datedEntries) {
    if (categoryId && entry.instant > cursor) {
      segments.push({ categoryId, start: cursor, end: entry.instant, projected: false })
    }
    categoryId = entry.categoryId
    cursor = entry.instant
  }

  if (categoryId && range.end > cursor) {
    const isCurrentRange = now >= range.start && now < range.end
    if (isCurrentRange) {
      if (now > cursor) {
        segments.push({ categoryId, start: cursor, end: now, projected: false })
      }
      const projectedStart = now > cursor ? now : cursor
      if (projectedStart < range.end) {
        segments.push({ categoryId, start: projectedStart, end: range.end, projected: true })
      }
    } else {
      segments.push({ categoryId, start: cursor, end: range.end, projected: false })
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
        displayCategoryMap.get(summaryCategoryId) ??
        displayCategory(
          { categoryId: summaryCategoryId, name: summaryCategoryId, isActive: false },
          resolvedCategories,
        ),
      elapsedDurationMs,
      percentage:
        totalElapsedDurationMs === 0 ? 0 : Math.round((elapsedDurationMs / totalElapsedDurationMs) * 100),
    }))
    .sort((left, right) => right.elapsedDurationMs - left.elapsedDurationMs)

  const usedCategoryIds = new Set(segments.map((segment) => segment.categoryId))
  const visibleCategories = sortedDisplayCategories(displayCategoryMap).filter(
    (category) => category.isActive || usedCategoryIds.has(category.categoryId),
  )

  return { segments, visibleCategories, summaries, totalElapsedDurationMs }
}

export const projectDailyTimeline = ({ day, ...input }: DailyProjectionInput): TimelineProjection =>
  projectTimelineRange({ range: day, ...input })
