<script setup lang="ts">
type Category = 'coursework' | 'work' | 'prayer' | 'rest' | 'social' | 'family' | 'self-study' | 'chores'

defineProps<{
  categories: Array<{ key: Category; label: string; color: string }>
  lastCategory: Category | null
}>()

const emit = defineEmits<{
  logCategory: [category: Category]
}>()
</script>

<template>
  <section class="controls">
    <button
      v-for="item in categories"
      :key="item.key"
      class="category-button"
      :style="{ backgroundColor: item.color }"
      @click="emit('logCategory', item.key)"
    >
      {{ item.label }}
    </button>
    <p class="last-selection" v-if="lastCategory">
      Last selection: {{ categories.find((item) => item.key === lastCategory)?.label ?? lastCategory }}
    </p>
  </section>
</template>

<style scoped>
.controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin: 2rem 0;
}

@media (max-width: 768px) {
  .controls {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.6rem;
    margin: 1.5rem 0;
  }
}

.last-selection {
  grid-column: 1 / -1;
  margin: 0.5rem 0 0;
  color: #b1b7c3;
  font-size: 0.9rem;
}

.category-button {
  border: none;
  color: #fff;
  font-weight: 600;
  padding: 0.85rem 1rem;
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
}

@media (max-width: 768px) {
  .category-button {
    padding: 0.75rem 0.5rem;
    font-size: 0.9rem;
  }
}

.category-button:hover {
  transform: translateY(-2px);
}
</style>
