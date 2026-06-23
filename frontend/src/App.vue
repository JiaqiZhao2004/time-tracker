<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Header from './components/Header.vue'
import Buttons from './components/Buttons.vue'
import ManualEntry from './components/ManualEntry.vue'
import Timeline from './components/Timeline.vue'
import Timer from './components/Timer.vue'
import { projectDailyTimeline, projectTimelineRange } from './domain/dailyTimeline'
import { resolveDisplayEntries } from './domain/displayEntries'
import { localDayContaining, localWeekContaining, localWeekDates, shiftLocalDay, todayLocalDay } from './domain/localDay'
import { completeSignIn, getSignedInUser, isAuthConfigured, signIn, signOut } from './services/auth'
import { clearGuestMode, enableGuestMode, fetchCategories, fetchEntriesLocal, fetchEntriesLocalWeek, fetchMe, isGuestMode, postEntry, updateMe, type EntriesLocalResponse, type EntriesPeriod, type UserProfile } from './services/api'
import { displayCategory, type Category, type DisplayCategory } from './types/category'
import type { Entry } from './types/entry'

type HourMark = {
  label: string
  left: string
}

type AuthStatus = 'checking' | 'signedOut' | 'signedIn' | 'guest'

const authStatus = ref<AuthStatus>('checking')
const authErrorMessage = ref('')
const profile = ref<UserProfile | null>(null)
const profileErrorMessage = ref('')
const isProfileSaving = ref(false)
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
const summaryPeriod = ref<EntriesPeriod>('day')
const weeklyEntriesByStart = ref<Record<string, EntriesLocalResponse>>({})
const weeklyIsLoading = ref(false)
const weeklyErrorMessage = ref('')
const pendingWeeklyRequests = new Map<string, number>()
let weeklyRequestId = 0

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
const selectedWeek = computed(() => localWeekContaining(selectedDay.value))
const selectedWeekData = computed(() => weeklyEntriesByStart.value[selectedWeek.value.date])
const weeklyDisplayEntries = computed(() =>
  resolveDisplayEntries(selectedWeekData.value?.entries ?? [], categories.value),
)
const weeklyTimeline = computed(() =>
  projectTimelineRange({
    range: selectedWeek.value,
    now: now.value,
    entries: weeklyDisplayEntries.value,
    precedingCategoryId: selectedWeekData.value?.prevEntryCategoryId ?? null,
    categories: categories.value,
  }),
)
const timerTimeline = computed(() => summaryPeriod.value === 'week' ? weeklyTimeline.value : timeline.value)

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

const fetchEntriesForSelectedWeek = async (force = false) => {
  const week = selectedWeek.value
  const key = week.date
  if (!force && (weeklyEntriesByStart.value[key] || pendingWeeklyRequests.has(key))) {
    weeklyIsLoading.value = pendingWeeklyRequests.has(key)
    return
  }

  const requestId = ++weeklyRequestId
  pendingWeeklyRequests.set(key, requestId)
  weeklyIsLoading.value = true
  weeklyErrorMessage.value = ''

  try {
    const data = await fetchEntriesLocalWeek(week.timezone, localWeekDates(week))
    if (pendingWeeklyRequests.get(key) !== requestId) {
      return
    }
    weeklyEntriesByStart.value = { ...weeklyEntriesByStart.value, [key]: data }
  } catch (error) {
    if (pendingWeeklyRequests.get(key) === requestId && selectedWeek.value.date === key) {
      weeklyErrorMessage.value = error instanceof Error ? error.message : 'Failed to load weekly entries'
    }
  } finally {
    if (pendingWeeklyRequests.get(key) === requestId) {
      pendingWeeklyRequests.delete(key)
      if (selectedWeek.value.date === key) {
        weeklyIsLoading.value = false
      }
    }
  }
}

const refreshVisibleWeeklySummaryForEntry = async (entry: Entry) => {
  const entryWeekKey = localWeekContaining(
    localDayContaining(new Date(entry.timestamp), selectedDay.value.timezone),
  ).date
  const entriesByStart = { ...weeklyEntriesByStart.value }
  delete entriesByStart[entryWeekKey]
  weeklyEntriesByStart.value = entriesByStart

  if (summaryPeriod.value === 'week' && selectedWeek.value.date === entryWeekKey) {
    await fetchEntriesForSelectedWeek(true)
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
    const created = await postEntry(categoryId)
    lastCategoryId.value = created.categoryId
    lastTimestamp.value = created.timestamp
    localStorage.setItem('lastCategoryId', created.categoryId)
    localStorage.setItem('lastTimestamp', created.timestamp)
    if (!entries.value.some((entry) => entry.id === created.id)) {
      entries.value = [...entries.value, created].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      )
    }
    await Promise.all([fetchEntriesForLocalDay(), refreshVisibleWeeklySummaryForEntry(created)])
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
  await Promise.all([fetchEntriesForLocalDay(), refreshVisibleWeeklySummaryForEntry(entry)])
}

const handleCategoryChanged = (category: Category) => {
  const updated = displayCategory(category)
  categories.value = [
    ...categories.value.filter((existing) => existing.categoryId !== updated.categoryId),
    updated,
  ].sort(
    (left, right) => left.name.localeCompare(right.name) || left.categoryId.localeCompare(right.categoryId),
  )
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
  if (summaryPeriod.value === 'week') {
    weeklyErrorMessage.value = ''
    weeklyIsLoading.value = pendingWeeklyRequests.has(selectedWeek.value.date)
    fetchEntriesForSelectedWeek()
  }
}

const shiftDay = (direction: -1 | 1) => {
  const shifted = shiftLocalDay(selectedDay.value, direction, todayLocalDay(now.value, selectedDay.value.timezone))
  if (shifted === selectedDay.value) {
    return
  }
  selectedDay.value = shifted
  fetchEntriesForLocalDay()
  if (summaryPeriod.value === 'week') {
    weeklyErrorMessage.value = ''
    weeklyIsLoading.value = pendingWeeklyRequests.has(selectedWeek.value.date)
    fetchEntriesForSelectedWeek()
  }
}

const setSummaryPeriod = (period: EntriesPeriod) => {
  summaryPeriod.value = period
  if (period === 'week') {
    weeklyErrorMessage.value = ''
    weeklyIsLoading.value = pendingWeeklyRequests.has(selectedWeek.value.date)
    fetchEntriesForSelectedWeek()
  }
}

const initializeAuthenticatedApp = async () => {
  authStatus.value = 'signedIn'
  profile.value = await fetchMe()
  await loadInitialData()
}

const initializeGuestApp = async () => {
  authStatus.value = 'guest'
  profile.value = await fetchMe()
  await loadInitialData()
}

const initializeAuth = async () => {
  authErrorMessage.value = ''
  if (isGuestMode()) {
    await initializeGuestApp()
    return
  }

  if (!isAuthConfigured) {
    authStatus.value = 'signedOut'
    authErrorMessage.value = 'Authentication is not configured'
    return
  }

  try {
    const callbackParams = new URLSearchParams(window.location.search)
    if (callbackParams.has('code') && callbackParams.has('state')) {
      await completeSignIn()
      window.history.replaceState({}, document.title, '/')
    }

    const user = await getSignedInUser()
    if (!user) {
      authStatus.value = 'signedOut'
      return
    }

    await initializeAuthenticatedApp()
  } catch (error) {
    authStatus.value = 'signedOut'
    authErrorMessage.value = error instanceof Error ? error.message : 'Failed to sign in'
  }
}

const handleSignIn = async () => {
  authErrorMessage.value = ''
  try {
    clearGuestMode()
    await signIn()
  } catch (error) {
    authErrorMessage.value = error instanceof Error ? error.message : 'Failed to start sign in'
  }
}

const handleTryGuest = async () => {
  authErrorMessage.value = ''
  enableGuestMode()
  try {
    await initializeGuestApp()
  } catch (error) {
    clearGuestMode()
    authStatus.value = 'signedOut'
    authErrorMessage.value = error instanceof Error ? error.message : 'Failed to start guest mode'
  }
}

const handleSignOut = async () => {
  authErrorMessage.value = ''
  try {
    if (authStatus.value === 'guest') {
      clearGuestMode()
      authStatus.value = 'signedOut'
      profile.value = null
      categories.value = []
      entries.value = []
      return
    }

    clearGuestMode()
    await signOut()
  } catch (error) {
    authErrorMessage.value = error instanceof Error ? error.message : 'Failed to sign out'
  }
}

const handleProfileUpdate = async (displayName: string) => {
  profileErrorMessage.value = ''
  isProfileSaving.value = true
  try {
    profile.value = await updateMe(displayName)
  } catch (error) {
    profileErrorMessage.value = error instanceof Error ? error.message : 'Failed to update profile'
  } finally {
    isProfileSaving.value = false
  }
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
  tickerId = window.setInterval(() => {
    now.value = new Date()
  }, 1000)
  initializeAuth()
})

onUnmounted(() => {
  if (tickerId) {
    window.clearInterval(tickerId)
  }
})
</script>

<template>
  <div v-if="authStatus === 'checking'" class="app auth-screen">
    <h1>Trace</h1>
    <p>Loading...</p>
  </div>

  <div v-else-if="authStatus === 'signedOut'" class="app auth-screen">
    <h1>Trace</h1>
    <p>See where your time goes and how your days take shape.</p>
    <button class="primary-auth" type="button" @click="handleSignIn">Sign in with Google</button>
    <button class="secondary-auth" type="button" @click="handleTryGuest">Try as guest</button>
    <p v-if="authErrorMessage" class="auth-error">{{ authErrorMessage }}</p>
  </div>

  <div v-else class="app">
    <Header
      :dayLabel="selectedDay.label"
      :displayName="profile?.displayName ?? ''"
      :profileErrorMessage="profileErrorMessage"
      :isProfileSaving="isProfileSaving"
      :isGuest="authStatus === 'guest'"
      @shiftDay="shiftDay"
      @goToToday="goToToday"
      @signOut="handleSignOut"
      @displayNameChange="handleProfileUpdate"
    />

    <Buttons
      :categories="categories"
      :lastCategory="lastCategory"
      :isGuest="authStatus === 'guest'"
      @logCategory="logCategory"
      @categoryChanged="handleCategoryChanged"
    />

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

    <Timer
      :period="summaryPeriod"
      :summaries="timerTimeline.summaries"
      :totalElapsedDurationMs="timerTimeline.totalElapsedDurationMs"
      :isLoading="summaryPeriod === 'week' && weeklyIsLoading"
      :errorMessage="summaryPeriod === 'week' ? weeklyErrorMessage : ''"
      @periodChange="setSummaryPeriod"
    />
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

.auth-screen {
  min-height: 80vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  gap: 1rem;
}

.auth-screen h1 {
  margin: 0;
  font-size: 2.2rem;
}

.auth-screen p {
  margin: 0;
  color: #b1b7c3;
}

.primary-auth {
  border: 0;
  background: #f5f5f5;
  color: #0f1115;
  padding: 0.7rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 700;
}

.secondary-auth {
  border: 1px solid #3a3f4b;
  background: transparent;
  color: #f5f5f5;
  padding: 0.7rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 700;
}

.auth-error {
  color: #ffb4b4;
}
</style>
