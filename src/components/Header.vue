<script setup lang="ts">
defineProps<{
  dayLabel: string
}>()

const emit = defineEmits<{
  shiftDay: [direction: -1 | 1]
  goToToday: []
}>()
</script>

<template>
  <header class="header">
    <div class="title">
      <h1>Time Tracker</h1>
      <p>UTC-backed, local-day timeline</p>
    </div>
    <div class="day-controls">
      <button class="ghost" @click="emit('shiftDay', -1)">Previous</button>
      <span class="day-label">{{ dayLabel }}</span>
      <button class="ghost" @click="emit('shiftDay', 1)">Next</button>
      <button class="ghost" @click="emit('goToToday')">Today</button>
    </div>
  </header>
</template>

<style scoped>
.header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 1.5rem;
  align-items: center;
}

.header .title {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.3rem;
}

.header h1 {
  margin: 0;
  font-size: 2.2rem;
}

@media (max-width: 768px) {
  .header h1 {
    font-size: 1.8rem;
  }
}

.header p {
  margin: 0.4rem 0 0;
  color: #b1b7c3;
}

.day-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
}

.day-label {
  padding: 0.4rem 0.8rem;
  background: #1b1f2a;
  border-radius: 999px;
  font-weight: 600;
}

.ghost {
  border: 1px solid #2f3645;
  background: transparent;
  color: #f5f5f5;
  padding: 0.45rem 0.85rem;
  border-radius: 999px;
  cursor: pointer;
}

@media (max-width: 720px) {
  .header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
