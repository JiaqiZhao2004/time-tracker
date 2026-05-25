<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Header from './components/Header.vue'
import Buttons from './components/Buttons.vue'
import ManualEntry from './components/ManualEntry.vue'
import Timeline from './components/Timeline.vue'
import Timer from './components/Timer.vue'
import { todayLocalStart } from './utils/dateUtils'
import { fetchCategories, fetchEntriesLocal, postEntry, type EntriesLocalResponse, type Entry } from './services/api'
import { displayCategory, type DisplayCategory } from './types/category'

type Segment = {
  categoryId: string
  start: Date
  end: Date
}

type HourMark = {
  label: string
  left: string
}

const categories = ref<DisplayCategory[]>([])
const entries = ref<Entry[]>([])
const isLoading = ref(false)
const errorMessage = ref('')
const dayStartCategoryId = ref<string | null>(null)
const lastCategoryId = ref<string | null>(null)
const lastTimestamp = ref<string | null>(null)
const now = ref(new Date())
const manualEntryDatetime = ref<Date | undefined>(undefined)
let tickerId: number | undefined

const dayStart = ref(todayLocalStart())
const dayEnd = computed(() => {
  const end = new Date(dayStart.value)
  end.setDate(end.getDate() + 1)
  return end
})

const dayLabel = computed(() => dayStart.value.toLocaleDateString())
const activeCategories = computed(() => categories.value.filter((category) => category.isActive))

const displayCategories = computed<DisplayCategory[]>(() => {
  const indexed = new Map(
    categories.value.map((category) => [category.categoryId, category]),
  )

  for (const entry of entries.value) {
    const storedCategory = indexed.get(entry.categoryId)
    indexed.set(
      entry.categoryId,
      displayCategory({
        categoryId: entry.categoryId,
        name: entry.categoryNameSnapshot,
        isActive: storedCategory?.isActive ?? false,
      }),
    )
  }

  if (dayStartCategoryId.value && !indexed.has(dayStartCategoryId.value)) {
    indexed.set(
      dayStartCategoryId.value,
      displayCategory({
        categoryId: dayStartCategoryId.value,
        name: dayStartCategoryId.value,
        isActive: false,
      }),
    )
  }

  return [...indexed.values()].sort(
    (left, right) => left.name.localeCompare(right.name) || left.categoryId.localeCompare(right.categoryId),
  )
})

const lastCategory = computed(
  () => displayCategories.value.find((category) => category.categoryId === lastCategoryId.value) ?? null,
)

const updateLastFromEntries = (list: Entry[]) => {
  if (list.length === 0) {
    return
  }
  const latest = [...list].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0]
  if (latest) {
    lastCategoryId.value = latest.categoryId
    lastTimestamp.value = latest.timestamp
    localStorage.setItem('lastCategoryId', latest.categoryId)
    localStorage.setItem('lastTimestamp', latest.timestamp)
  }
}

const applyEntries = (data: EntriesLocalResponse) => {
  entries.value = data.entries
  dayStartCategoryId.value = data.prevEntryCategoryId
  updateLastFromEntries(data.entries)
}

const fetchEntriesForLocalDay = async () => {
  isLoading.value = true
  errorMessage.value = ''

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
  const dateStr = dayStart.value.toISOString().split('T')[0]

  try {
    const data = await fetchEntriesLocal(timezone, dateStr!)
    applyEntries(data)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load entries'
  } finally {
    isLoading.value = false
  }
}

const loadInitialData = async () => {
  isLoading.value = true
  errorMessage.value = ''

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
  const dateStr = dayStart.value.toISOString().split('T')[0]

  try {
    const [availableCategories, data] = await Promise.all([
      fetchCategories(),
      fetchEntriesLocal(timezone, dateStr!),
    ])
    categories.value = availableCategories.map(displayCategory)
    applyEntries(data)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load data'
  } finally {
    isLoading.value = false
  }
}

const logCategory = async (categoryId: string) => {
  errorMessage.value = ''
  if (lastCategoryId.value === categoryId) {
    return
  }
  try {
    const created = await postEntry(categoryId, new Date().toISOString())
    lastCategoryId.value = created.categoryId
    lastTimestamp.value = created.timestamp
    localStorage.setItem('lastCategoryId', created.categoryId)
    localStorage.setItem('lastTimestamp', created.timestamp)
    if (!entries.value.some((entry) => entry.id === created.id)) {
      entries.value = [...entries.value, created].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      )
    }
    await fetchEntriesForLocalDay()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to save entry'
  }
}

const handleEntryCreated = async (entry: Entry) => {
  if (!entries.value.some((e) => e.id === entry.id)) {
    entries.value = [...entries.value, entry].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
  }
  await fetchEntriesForLocalDay()
}

const handleTimeClick = (date: Date) => {
  manualEntryDatetime.value = date
}

const buildSegments = (endBoundary: Date): Segment[] => {
  const augmented = [...entries.value]

  const sorted = augmented
    .map((entry) => ({ ...entry, date: new Date(entry.timestamp) }))
    .sort((a, b) => a.date.getTime() - b.date.getTime())

  const start = dayStart.value
  const end = endBoundary
  const segmentsList: Segment[] = []

  let currentCategoryId = dayStartCategoryId.value
  let cursor = new Date(start)

  for (const item of sorted) {
    if (currentCategoryId && item.date > cursor) {
      segmentsList.push({ categoryId: currentCategoryId, start: cursor, end: item.date })
    }
    currentCategoryId = item.categoryId
    cursor = item.date
  }

  if (currentCategoryId && end > cursor) {
    const currentTime = new Date()
    const trackedEnd = currentTime > cursor && currentTime < end ? currentTime : end
    segmentsList.push({ categoryId: currentCategoryId, start: cursor, end: trackedEnd })
    if (trackedEnd < end) {
      segmentsList.push({ categoryId: currentCategoryId, start: trackedEnd, end })
    }
  }
  return segmentsList
}

const segments = computed<Segment[]>(() => buildSegments(dayEnd.value))
const timelineCategories = computed(() => {
  const usedCategoryIds = new Set(segments.value.map((segment) => segment.categoryId))
  return displayCategories.value.filter(
    (category) => category.isActive || usedCategoryIds.has(category.categoryId),
  )
})

const hourMarks = computed<HourMark[]>(() => {
  const marks: HourMark[] = []
  for (let hour = 0; hour <= 24; hour += 4) {
    const left = (hour / 24) * 100
    const label = `${hour.toString().padStart(2, '0')}:00`
    marks.push({ label, left: `${left}%` })
  }
  return marks
})

const goToToday = () => {
  dayStart.value = todayLocalStart()
  fetchEntriesForLocalDay()
}

const shiftDay = (direction: -1 | 1) => {
  const next = new Date(dayStart.value)
  next.setDate(next.getDate() + direction)
  if (next > todayLocalStart()) {
    return
  }
  dayStart.value = next
  fetchEntriesForLocalDay()
}

onMounted(() => {
  const storedCategoryId = localStorage.getItem('lastCategoryId')
  if (storedCategoryId) {
    lastCategoryId.value = storedCategoryId
  }
  const storedTimestamp = localStorage.getItem('lastTimestamp')
  if (storedTimestamp) {
    lastTimestamp.value = storedTimestamp
  }
  loadInitialData()
  tickerId = window.setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onUnmounted(() => {
  if (tickerId) {
    window.clearInterval(tickerId)
  }
})
</script>

<template>
  <div class="app">
    <Header :dayLabel="dayLabel" @shiftDay="shiftDay" @goToToday="goToToday" />

    <Buttons :categories="activeCategories" :lastCategory="lastCategory" @logCategory="logCategory" />

    <ManualEntry :categories="activeCategories" :initialDatetime="manualEntryDatetime" @entryCreated="handleEntryCreated" />

    <Timeline
      :segments="segments"
      :hourMarks="hourMarks"
      :categories="timelineCategories"
      :dayStart="dayStart"
      :dayEnd="dayEnd"
      :isLoading="isLoading"
      :errorMessage="errorMessage"
      @timeClick="handleTimeClick"
    />

    <Timer :segments="segments" :categories="displayCategories" :end="dayEnd < now ? dayEnd : now" />
  </div>
</template>

<style scoped>
:global(body) {
  margin: 0;
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #0f1115;
  color: #f5f5f5;
}

.app {
  max-width: 1100px;
  margin: 0 auto;
  padding: 2.5rem 1.5rem 4rem;
}
</style>
