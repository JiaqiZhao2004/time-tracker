<script setup lang="ts">
import { computed } from 'vue'
import type { TimelineSummary } from '../domain/dailyTimeline'
import type { EntriesPeriod } from '../services/api'

const props = defineProps<{
  period: EntriesPeriod
  summaries: TimelineSummary[]
  totalElapsedDurationMs: number
  isLoading: boolean
  errorMessage: string
}>()

const emit = defineEmits<{
  periodChange: [period: EntriesPeriod]
}>()

const periodLabel = computed(() => props.period === 'week' ? 'Selected Week' : 'Selected Day')

/**
 * Convert milliseconds to hours and minutes
 */
const formatTime = (ms: number): string => {
  const totalMinutes = Math.floor(ms / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  
  if (hours === 0) {
    return `${minutes}m`
  }
  return `${hours}h ${minutes}m`
}

</script>

<template>
  <section class="timer">
    <div class="timer-header">
      <div class="timer-title">
        <h2>Time Spent: {{ periodLabel }}</h2>
        <div class="period-toggle" role="group" aria-label="Summary period">
          <button
            :class="{ active: period === 'day' }"
            :aria-pressed="period === 'day'"
            @click="emit('periodChange', 'day')"
          >
            Day
          </button>
          <button
            :class="{ active: period === 'week' }"
            :aria-pressed="period === 'week'"
            @click="emit('periodChange', 'week')"
          >
            Week
          </button>
        </div>
      </div>
      <div class="total-time">Total: {{ formatTime(totalElapsedDurationMs) }}</div>
    </div>

    <p v-if="errorMessage" class="timer-error">{{ errorMessage }}</p>

    <div v-if="isLoading && summaries.length === 0" class="no-data">
      Loading {{ period === 'week' ? 'weekly' : 'daily' }} activity...
    </div>

    <div v-else-if="!errorMessage && summaries.length === 0" class="no-data">
      No activity tracked for the selected {{ period }}
    </div>

    <div v-else class="category-list">
      <div
        v-for="summary in summaries"
        :key="summary.category.categoryId"
        class="category-item"
      >
        <div class="category-info">
          <div class="category-color" :style="{ backgroundColor: summary.category.color }"></div>
          <div class="category-name">{{ summary.category.name }}</div>
        </div>
        <div class="category-stats">
          <div class="category-time">{{ formatTime(summary.elapsedDurationMs) }}</div>
          <div class="category-percentage">{{ summary.percentage }}%</div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.timer {
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.052), rgba(255, 255, 255, 0.022)),
    rgba(16, 21, 29, 0.86);
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 14px;
  padding: 1.5rem;
  margin-top: 2rem;
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(8px);
}

.timer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.timer-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
}

.timer-header h2 {
  margin: 0;
  font-size: 1.32rem;
  font-weight: 600;
  color: #f5f5f5;
}

.period-toggle {
  display: inline-flex;
  padding: 0.2rem;
  background: rgba(5, 8, 13, 0.66);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
}

.period-toggle button {
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  padding: 0.4rem 0.8rem;
  font-weight: 600;
}

.period-toggle button.active {
  background: #65d6c3;
  color: #071018;
}

.total-time {
  font-size: 1.25rem;
  font-weight: 600;
  color: #65d6c3;
  white-space: nowrap;
}

.timer-error {
  margin: 0 0 1rem;
  color: #ff7675;
}

.no-data {
  text-align: center;
  padding: 2rem;
  color: #6b7280;
  font-size: 0.95rem;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.category-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.875rem 1rem;
  background: rgba(255, 255, 255, 0.055);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 8px;
  transition: background 0.2s ease, transform 0.2s ease;
}

.category-item:hover {
  background: rgba(255, 255, 255, 0.07);
  transform: none;
}

.category-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.category-color {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  flex-shrink: 0;
}

.category-name {
  font-size: 1rem;
  font-weight: 500;
  color: #e5e7eb;
}

.category-stats {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.category-time {
  font-size: 1rem;
  font-weight: 600;
  color: #f5f5f5;
  min-width: 80px;
  text-align: right;
}

.category-percentage {
  font-size: 0.875rem;
  font-weight: 500;
  color: #9ca3af;
  min-width: 45px;
  text-align: right;
}
</style>
