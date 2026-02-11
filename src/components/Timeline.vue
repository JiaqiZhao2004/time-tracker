<script setup lang="ts">
import { computed } from 'vue'

type Category = 'coursework' | 'work' | 'prayer' | 'rest' | 'social' | 'family' | 'self-study' | 'chores'

type Segment = {
  category: Category
  start: Date
  end: Date
}

type HourMark = {
  label: string
  left: string
}

const props = defineProps<{
  segments: Segment[]
  hourMarks: HourMark[]
  categories: Array<{ key: Category; label: string; color: string }>
  dayStart: Date
  dayEnd: Date
  isLoading: boolean
  errorMessage: string
}>()

/**
 * Component-specific function: calculates style for timeline segments
 */
const totalDayMs = computed(() => props.dayEnd.getTime() - props.dayStart.getTime())

const segmentStyle = (segment: Segment) => {
  const startOffset = Math.max(0, segment.start.getTime() - props.dayStart.getTime())
  const endOffset = Math.min(totalDayMs.value, segment.end.getTime() - props.dayStart.getTime())
  const left = (startOffset / totalDayMs.value) * 100
  const width = ((endOffset - startOffset) / totalDayMs.value) * 100
  const color = props.categories.find((item) => item.key === segment.category)?.color ?? '#999'
  return {
    left: `${left}%`,
    width: `${width}%`,
    backgroundColor: color,
  }
}
</script>

<template>
  <section class="timeline">
    <div class="timeline-header">
      <h2>Daily Timeline</h2>
      <span v-if="isLoading">Loading...</span>
    </div>
    <div class="timeline-bar">
      <div class="hour-marks">
        <div v-for="mark in hourMarks" :key="mark.label" class="hour-mark" :style="{ left: mark.left }">
          <span class="hour-label">{{ mark.label }}</span>
        </div>
      </div>
      <div
        v-for="(segment, index) in segments"
        :key="`${segment.category}-${index}`"
        class="segment"
        :style="segmentStyle(segment)"
      />
      <div v-if="segments.length === 0" class="empty">No entries yet</div>
    </div>
    <div class="timeline-legend">
      <div v-for="item in categories" :key="item.key" class="legend-item">
        <span class="legend-color" :style="{ backgroundColor: item.color }" />
        {{ item.label }}
      </div>
    </div>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<style scoped>
.timeline {
  background: #151926;
  border-radius: 18px;
  padding: 1.5rem;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.timeline-bar {
  position: relative;
  height: 32px;
  background: #0b0d14;
  border-radius: 999px;
  overflow: hidden;
}

.hour-marks {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.hour-mark {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.12);
}

.hour-mark:first-child,
.hour-mark:last-child {
  background: rgba(255, 255, 255, 0.2);
}

.hour-label {
  position: absolute;
  top: -1.6rem;
  transform: translateX(-50%);
  font-size: 0.72rem;
  color: #8d96a8;
  white-space: nowrap;
}

.segment {
  position: absolute;
  top: 0;
  bottom: 0;
}

.segment:last-child {
  opacity: 0.5;
}

.empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #7c8596;
  font-size: 0.9rem;
}

.timeline-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 1.2rem;
  color: #cbd0da;
  font-size: 0.9rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.error {
  margin-top: 1rem;
  color: #ff7675;
}
</style>
