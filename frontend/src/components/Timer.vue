<script setup lang="ts">
import { computed } from 'vue'
import type { Category } from '../types/category'

type Segment = {
  category: Category
  start: Date
  end: Date
}

const props = defineProps<{
  segments: Segment[]
  categories: Array<{ key: Category; label: string; color: string }>
  end: Date
}>()

/**
 * Calculate time spent on each category in milliseconds
 */
const categoryTimes = computed(() => {
  const times: Record<Category, number> = {
    coursework: 0,
    work: 0,
    prayer: 0,
    rest: 0,
    social: 0,
    family: 0,
    'self-study': 0,
    chores: 0,
    exercise: 0,
  }

  for (const segment of props.segments) {
    const endTime = segment.end > props.end ? props.end : segment.end
    const duration = endTime.getTime() - segment.start.getTime()
    if (duration > 0) {
      times[segment.category] = (times[segment.category] || 0) + duration
    }
  }

  return times
})

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

/**
 * Get sorted categories by time spent (descending)
 */
const sortedCategories = computed(() => {
  return props.categories
    .map((cat) => ({
      ...cat,
      time: categoryTimes.value[cat.key],
    }))
    .filter((cat) => cat.time > 0)
    .sort((a, b) => b.time - a.time)
})

/**
 * Calculate total time tracked
 */
const totalTime = computed(() => {
  return Object.values(categoryTimes.value).reduce((sum, time) => sum + time, 0)
})

/**
 * Calculate percentage for each category
 */
const getPercentage = (time: number): number => {
  if (totalTime.value === 0) return 0
  return Math.round((time / totalTime.value) * 100)
}
</script>

<template>
  <section class="timer">
    <div class="timer-header">
      <h2>Time Spent Today</h2>
      <div class="total-time">Total: {{ formatTime(totalTime) }}</div>
    </div>
    
    <div v-if="sortedCategories.length === 0" class="no-data">
      No activity tracked yet today
    </div>
    
    <div v-else class="category-list">
      <div
        v-for="cat in sortedCategories"
        :key="cat.key"
        class="category-item"
      >
        <div class="category-info">
          <div class="category-color" :style="{ backgroundColor: cat.color }"></div>
          <div class="category-name">{{ cat.label }}</div>
        </div>
        <div class="category-stats">
          <div class="category-time">{{ formatTime(cat.time) }}</div>
          <div class="category-percentage">{{ getPercentage(cat.time) }}%</div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.timer {
  background: #1a1d24;
  border-radius: 12px;
  padding: 1.5rem;
  margin-top: 2rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.timer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #2a2e38;
}

.timer-header h2 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: #f5f5f5;
}

.total-time {
  font-size: 1.25rem;
  font-weight: 600;
  color: #6c63ff;
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
  background: #21252e;
  border-radius: 8px;
  transition: background 0.2s ease;
}

.category-item:hover {
  background: #272b36;
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
