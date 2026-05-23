<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Header from './components/Header.vue'
import Buttons from './components/Buttons.vue'
import ManualEntry from './components/ManualEntry.vue'
import Timeline from './components/Timeline.vue'
import Timer from './components/Timer.vue'
import { todayLocalStart } from './utils/dateUtils'
import { fetchEntriesLocal, postEntry, type Entry } from './services/api'
import type { Category } from './types/category'

type Segment = {
  category: Category
  start: Date
  end: Date
}

type HourMark = {
  label: string
  left: string
}

const categories: Array<{ key: Category; label: string; color: string }> = [
  { key: 'coursework', label: 'Coursework', color: '#6c63ff' },
  { key: 'work', label: 'Work', color: '#00b894' },
  { key: 'prayer', label: 'Prayer', color: '#fdcb6e' },
  { key: 'rest', label: 'Rest', color: '#0984e3' },
  { key: 'social', label: 'Social', color: '#e17055' },
  { key: 'family', label: 'Family', color: '#d63031' },
  { key: 'self-study', label: 'Self Study', color: '#a29bfe' },
  { key: 'chores', label: 'Chores', color: '#fd79a8' },
  { key: 'exercise', label: 'Exercise', color: '#00cec9' },
]

const entries = ref<Entry[]>([])
const isLoading = ref(false)
const errorMessage = ref('')
const dayStartCategory = ref<Category | null>(null)
const lastCategory = ref<Category | null>(null)
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

const updateLastFromEntries = (list: Entry[]) => {
  if (list.length === 0) {
    return
  }
  const latest = [...list].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0]
  if (latest) {
    lastCategory.value = latest.category
    lastTimestamp.value = latest.timestamp
    localStorage.setItem('lastCategory', latest.category)
    localStorage.setItem('lastTimestamp', latest.timestamp)
  }
}

const fetchEntriesForLocalDay = async () => {
  isLoading.value = true
  errorMessage.value = ''

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
  const dateStr = dayStart.value.toISOString().split('T')[0]

  try {
    const data = await fetchEntriesLocal(timezone, dateStr!)
    entries.value = data.entries
    console.log('Fetched entries:', data)
    if (data.prevEntryCategory) {
      dayStartCategory.value = data.prevEntryCategory
    }
    updateLastFromEntries(data.entries)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load entries'
  } finally {
    isLoading.value = false
  }
}

const logCategory = async (category: Category) => {
  errorMessage.value = ''
  if (lastCategory.value === category) {
    return
  }
  try {
    const created = await postEntry(category, new Date().toISOString())
    lastCategory.value = created.category
    lastTimestamp.value = created.timestamp
    localStorage.setItem('lastCategory', created.category)
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

  let currentCategory: Category = dayStartCategory.value || 'rest'
  let cursor = new Date(start)

  for (const item of sorted) {
    if (item.date > cursor) {
      segmentsList.push({ category: currentCategory, start: cursor, end: item.date })
    }
    currentCategory = item.category
    cursor = item.date
  }

  if (currentCategory && end > cursor) {
    segmentsList.push({ category: currentCategory, start: cursor, end: new Date() })
    segmentsList.push({ category: currentCategory, start: new Date(), end })
  }
  return segmentsList
}

const segments = computed<Segment[]>(() => buildSegments(dayEnd.value))

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
  const stored = localStorage.getItem('lastCategory') as Category | null
  if (stored && categories.some((item) => item.key === stored)) {
    lastCategory.value = stored
  }
  const storedTimestamp = localStorage.getItem('lastTimestamp')
  if (storedTimestamp) {
    lastTimestamp.value = storedTimestamp
  }
  fetchEntriesForLocalDay()
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

    <Buttons :categories="categories" :lastCategory="lastCategory" @logCategory="logCategory" />

    <ManualEntry :categories="categories" :initialDatetime="manualEntryDatetime" @entryCreated="handleEntryCreated" />

    <Timeline
      :segments="segments"
      :hourMarks="hourMarks"
      :categories="categories"
      :dayStart="dayStart"
      :dayEnd="dayEnd"
      :isLoading="isLoading"
      :errorMessage="errorMessage"
      @timeClick="handleTimeClick"
    />

    <Timer :segments="segments" :categories="categories" :end="dayEnd < now ? dayEnd : now" />
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
