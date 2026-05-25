<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Header from './components/Header.vue'
import Buttons from './components/Buttons.vue'
import ManualEntry from './components/ManualEntry.vue'
import Timeline from './components/Timeline.vue'
import Timer from './components/Timer.vue'
import { projectDailyTimeline } from './domain/dailyTimeline'
import { resolveDisplayEntries } from './domain/displayEntries'
import { shiftLocalDay, todayLocalDay } from './domain/localDay'
import { fetchCategories, fetchEntriesLocal, postEntry, type EntriesLocalResponse } from './services/api'
import { displayCategory, type DisplayCategory } from './types/category'
import type { Entry } from './types/entry'

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

const selectedDay = ref(todayLocalDay())

const activeCategories = computed(() => categories.value.filter((category) => category.isActive))
const displayEntries = computed(() => resolveDisplayEntries(entries.value, categories.value))
const timeline = computed(() =>
  projectDailyTimeline({
    day: selectedDay.value,
    now: now.value,
    entries: displayEntries.value,
    precedingCategoryId: dayStartCategoryId.value,
    categories: categories.value,
  }),
)

const lastCategory = computed(
  () =>
    timeline.value.visibleCategories.find((category) => category.categoryId === lastCategoryId.value) ??
    categories.value.find((category) => category.categoryId === lastCategoryId.value) ??
    null,
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

  try {
    const data = await fetchEntriesLocal(selectedDay.value.timezone, selectedDay.value.date)
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

  try {
    const [availableCategories, data] = await Promise.all([
      fetchCategories(),
      fetchEntriesLocal(selectedDay.value.timezone, selectedDay.value.date),
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
  selectedDay.value = todayLocalDay()
  fetchEntriesForLocalDay()
}

const shiftDay = (direction: -1 | 1) => {
  const shifted = shiftLocalDay(selectedDay.value, direction, todayLocalDay(now.value, selectedDay.value.timezone))
  if (shifted === selectedDay.value) {
    return
  }
  selectedDay.value = shifted
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
    <Header :dayLabel="selectedDay.label" @shiftDay="shiftDay" @goToToday="goToToday" />

    <Buttons :categories="activeCategories" :lastCategory="lastCategory" @logCategory="logCategory" />

    <ManualEntry :categories="activeCategories" :initialDatetime="manualEntryDatetime" @entryCreated="handleEntryCreated" />

    <Timeline
      :segments="timeline.segments"
      :hourMarks="hourMarks"
      :categories="timeline.visibleCategories"
      :day="selectedDay"
      :isLoading="isLoading"
      :errorMessage="errorMessage"
      @timeClick="handleTimeClick"
    />

    <Timer :summaries="timeline.summaries" :totalElapsedDurationMs="timeline.totalElapsedDurationMs" />
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
