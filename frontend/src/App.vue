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
import { displayCategories, type Category, type DisplayCategory } from './types/category'
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
    categories.value = displayCategories(availableCategories)
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
  const updatedCategories = [
    ...categories.value.filter((existing) => existing.categoryId !== category.categoryId),
    category,
  ].sort(
    (left, right) => left.name.localeCompare(right.name) || left.categoryId.localeCompare(right.categoryId),
  )
  categories.value = displayCategories(updatedCategories)
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
    <div class="auth-copy">
      <p class="eyebrow">Trace</p>
      <h1>Your day, made visible.</h1>
      <p>Loading your workspace...</p>
    </div>
  </div>

  <div v-else-if="authStatus === 'signedOut'" class="app auth-screen">
    <div class="auth-copy">
      <p class="eyebrow">Trace</p>
      <h1>Your day, made visible.</h1>
      <p>See where your time goes, spot the shape of your work, and add entries without breaking focus.</p>
      <div class="auth-actions">
        <button class="primary-auth" type="button" @click="handleSignIn">Sign in with Google</button>
        <button class="secondary-auth" type="button" @click="handleTryGuest">Try as guest</button>
      </div>
      <p v-if="authErrorMessage" class="auth-error">{{ authErrorMessage }}</p>
    </div>
    <div class="product-preview" aria-hidden="true">
      <div class="preview-toolbar">
        <span></span>
        <span></span>
        <span></span>
      </div>
      <div class="preview-title-row">
        <div>
          <span class="preview-kicker">Today</span>
          <strong>8h 20m tracked</strong>
        </div>
        <span class="preview-pill">Live</span>
      </div>
      <div class="preview-timeline">
        <span class="block plan"></span>
        <span class="block build"></span>
        <span class="block focus"></span>
        <span class="block break"></span>
      </div>
      <div class="preview-grid">
        <span>Design</span>
        <span>Deep Work</span>
        <span>Admin</span>
        <span>Break</span>
      </div>
    </div>
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
  min-height: 100svh;
  overflow-x: clip;
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background:
    radial-gradient(circle at 18% 12%, rgba(78, 201, 176, 0.14), transparent 28rem),
    radial-gradient(circle at 86% 4%, rgba(255, 196, 87, 0.1), transparent 24rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.026) 0 1px, transparent 1px 12px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.022) 0 1px, transparent 1px 84px),
    #0d1117;
  background-attachment: fixed;
  color: #f5f5f5;
}

:global(body::before) {
  content: '';
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background:
    linear-gradient(120deg, rgba(13, 17, 23, 0.16), rgba(13, 17, 23, 0.84) 55%),
    radial-gradient(circle at 50% 100%, rgba(108, 99, 255, 0.07), transparent 36rem);
}

.app {
  max-width: 1100px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
  box-sizing: border-box;
  min-height: 100svh;
}

.auth-screen {
  width: min(100%, 1180px);
  min-height: 100svh;
  box-sizing: border-box;
  padding: clamp(1.5rem, 5vh, 3.5rem) 1.5rem;
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(320px, 0.68fr);
  align-items: center;
  gap: clamp(2rem, 5vw, 4rem);
}

.auth-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1rem;
}

.eyebrow {
  margin: 0;
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
  color: #f4d17a;
  padding: 0.28rem 0.66rem;
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.auth-screen h1 {
  margin: 0;
  max-width: 10ch;
  font-size: clamp(2.8rem, 6.7vw, 5.4rem);
  line-height: 0.98;
  letter-spacing: 0;
}

.auth-screen p {
  margin: 0;
  max-width: 38rem;
  color: #b1b7c3;
  font-size: 1rem;
}

.auth-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  margin-top: 0.4rem;
}

.primary-auth {
  border: 0;
  background: linear-gradient(135deg, #efd87d, #6fd8c5);
  color: #10151c;
  padding: 0.72rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 800;
  box-shadow: 0 12px 24px rgba(64, 211, 190, 0.12);
}

.secondary-auth {
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.06);
  color: #f5f5f5;
  padding: 0.72rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 700;
}

.auth-error {
  color: #ffb4b4;
}

.product-preview {
  position: relative;
  overflow: hidden;
  min-height: 320px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.09), rgba(255, 255, 255, 0.035)),
    rgba(15, 20, 28, 0.82);
  box-shadow: 0 22px 56px rgba(0, 0, 0, 0.26);
  padding: 1rem;
}

.product-preview::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: linear-gradient(to bottom, black, transparent 82%);
  pointer-events: none;
}

.preview-toolbar,
.preview-title-row,
.preview-timeline,
.preview-grid {
  position: relative;
  z-index: 1;
}

.preview-toolbar {
  display: flex;
  gap: 0.45rem;
  margin-bottom: 2.7rem;
}

.preview-toolbar span {
  width: 0.62rem;
  height: 0.62rem;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.28);
}

.preview-title-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.preview-title-row strong {
  display: block;
  margin-top: 0.25rem;
  font-size: 1.65rem;
  line-height: 1;
}

.preview-kicker {
  color: #a8b0bd;
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.preview-pill {
  border: 1px solid rgba(92, 224, 199, 0.36);
  border-radius: 999px;
  background: rgba(92, 224, 199, 0.13);
  color: #8af2df;
  padding: 0.3rem 0.6rem;
  font-size: 0.76rem;
  font-weight: 800;
}

.preview-timeline {
  display: grid;
  grid-template-columns: 0.75fr 1.55fr 1.1fr 0.45fr;
  height: 46px;
  overflow: hidden;
  margin: 1.6rem 0 1.1rem;
  border-radius: 999px;
  background: rgba(5, 8, 13, 0.66);
  padding: 0.35rem;
  gap: 0.35rem;
}

.block {
  border-radius: 999px;
}

.plan {
  background: #f4c95d;
}

.build {
  background: #5ce0c7;
}

.focus {
  background: #8b7dff;
}

.break {
  background: #ff8b6d;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.preview-grid span {
  min-height: 54px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.048);
  display: grid;
  place-items: center;
  color: #e8ebef;
  font-weight: 800;
}

@media (max-width: 860px) {
  .auth-screen {
    grid-template-columns: 1fr;
    align-items: start;
    padding-top: 2rem;
    padding-bottom: 2rem;
  }

  .product-preview {
    min-height: 280px;
  }
}
</style>
