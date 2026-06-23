<script setup lang="ts">
import { computed, ref } from 'vue'
import { instantAtTimelinePosition, type LocalDay } from '../domain/localDay'
import type { TimelineSegment } from '../domain/dailyTimeline'
import type { DisplayCategory } from '../types/category'

type HourMark = {
  label: string
  left: string
}

const props = defineProps<{
  segments: TimelineSegment[]
  hourMarks: HourMark[]
  categories: DisplayCategory[]
  day: LocalDay
  isLoading: boolean
  errorMessage: string
}>()

const emit = defineEmits<{
  timeClick: [date: Date]
}>()

/**
 * Component-specific function: calculates style for timeline segments
 */
const totalDayMs = computed(() => props.day.end.getTime() - props.day.start.getTime())

const segmentStyle = (segment: TimelineSegment) => {
  const startOffset = Math.max(0, segment.start.getTime() - props.day.start.getTime())
  const endOffset = Math.min(totalDayMs.value, segment.end.getTime() - props.day.start.getTime())
  const left = (startOffset / totalDayMs.value) * 100
  const width = ((endOffset - startOffset) / totalDayMs.value) * 100
  const color = props.categories.find((item) => item.categoryId === segment.categoryId)?.color ?? '#999'
  return {
    left: `${left}%`,
    width: `${width}%`,
    backgroundColor: color,
  }
}

const tooltipVisible = ref(false)
const tooltipLeft = ref(0)
const tooltipTime = ref('')

const handleMouseMove = (e: MouseEvent) => {
  const bar = e.currentTarget as HTMLElement
  const rect = bar.getBoundingClientRect()
  const x = Math.min(rect.width, Math.max(0, e.clientX - rect.left))
  const pct = x / rect.width
  const timeAtCursor = instantAtTimelinePosition(props.day, pct)
  const hh = timeAtCursor.getHours().toString().padStart(2, '0')
  const mm = timeAtCursor.getMinutes().toString().padStart(2, '0')
  tooltipTime.value = `${hh}:${mm}`
  tooltipLeft.value = x
  tooltipVisible.value = true
}

const handleMouseLeave = () => {
  tooltipVisible.value = false
}

const handleClick = (e: MouseEvent) => {
  const bar = e.currentTarget as HTMLElement
  const rect = bar.getBoundingClientRect()
  const x = Math.min(rect.width, Math.max(0, e.clientX - rect.left))
  const pct = x / rect.width
  const timeAtCursor = instantAtTimelinePosition(props.day, pct)
  emit('timeClick', timeAtCursor)
}
</script>

<template>
  <section class="timeline">
    <div class="timeline-header">
      <h2>Daily Timeline</h2>
      <span v-if="isLoading">Loading...</span>
    </div>
    <div class="timeline-bar" @mousemove="handleMouseMove" @mouseleave="handleMouseLeave" @click="handleClick">
      <div class="timeline-bar-track">
        <div class="hour-marks">
          <div v-for="mark in hourMarks" :key="mark.label" class="hour-mark" :style="{ left: mark.left }">
            <span class="hour-label">{{ mark.label }}</span>
          </div>
        </div>
        <div
          v-for="(segment, index) in segments"
          :key="`${segment.categoryId}-${index}`"
          :class="segment.projected ? 'segment-projected' : 'segment'"
          :style="segmentStyle(segment)"
        />
        <div v-if="segments.length === 0" class="empty">No entries yet</div>
      </div>
      <div v-if="tooltipVisible" class="timeline-tooltip" :style="{ left: tooltipLeft + 'px' }">
        {{ tooltipTime }}
      </div>
    </div>
    <div class="timeline-legend">
      <div v-for="item in categories" :key="item.categoryId" class="legend-item">
        <span class="legend-color" :style="{ backgroundColor: item.color }" />
        {{ item.name }}
      </div>
    </div>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<style scoped>
.timeline {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.058), rgba(255, 255, 255, 0.022)),
    rgba(15, 20, 30, 0.86);
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 14px;
  padding: 1.5rem;
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.24);
  backdrop-filter: blur(8px);
}

.timeline::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.028) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.028) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(to bottom, black, transparent 74%);
  pointer-events: none;
}

.timeline > * {
  position: relative;
  z-index: 1;
}

@media (max-width: 768px) {
  .timeline {
    padding: 1rem;
    border-radius: 12px;
  }
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.timeline-header h2 {
  margin: 0;
  font-size: 1.18rem;
}

.timeline-bar {
  position: relative;
  height: 34px;
  overflow: visible;
  cursor: crosshair;
}

.timeline-bar-track {
  position: absolute;
  inset: 0;
  background: rgba(5, 8, 13, 0.74);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  overflow: hidden;
}

.timeline-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  transform: translateX(-50%);
  background: #1a1d23;
  border: 1px solid #3a3d4a;
  border-radius: 7px;
  padding: 0.2rem 0.55rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: #f5f5f5;
  pointer-events: none;
  white-space: nowrap;
  z-index: 10;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
  letter-spacing: 0.03em;
}

.timeline-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: #3a3d4a;
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

.segment, .segment-projected {
  position: absolute;
  top: 0;
  bottom: 0;
}

.segment-projected {
  opacity: 0.2;
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
  gap: 0.7rem;
  margin-top: 1.2rem;
  color: #cbd0da;
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .timeline-legend {
    gap: 0.6rem;
    font-size: 0.8rem;
  }
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.034);
  padding: 0.34rem 0.6rem;
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
