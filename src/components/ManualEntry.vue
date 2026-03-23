<script setup lang="ts">
import { ref, watch } from 'vue'
import { postEntry, type Entry } from '../services/api'

type Category = 'coursework' | 'work' | 'prayer' | 'rest' | 'social' | 'family' | 'self-study' | 'chores'

const props = defineProps<{
  categories: Array<{ key: Category; label: string; color: string }>
  initialDatetime?: Date
}>()

const emit = defineEmits<{
  entryCreated: [entry: Entry]
}>()

const toLocalInputValue = (date: Date): string => {
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const selectedCategory = ref<Category>(props.categories[0]?.key ?? 'rest')
const selectedDatetime = ref(toLocalInputValue(new Date()))
const isSubmitting = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const selectedColor = () =>
  props.categories.find((c) => c.key === selectedCategory.value)?.color ?? '#6c63ff'

watch(() => props.initialDatetime, (newDate) => {
  if (newDate) {
    selectedDatetime.value = toLocalInputValue(newDate)
  }
})

const handleSubmit = async () => {
  if (!selectedCategory.value || !selectedDatetime.value) return
  errorMessage.value = ''
  successMessage.value = ''
  isSubmitting.value = true

  try {
    const timestamp = new Date(selectedDatetime.value).toISOString()
    const created = await postEntry(selectedCategory.value, timestamp)
    emit('entryCreated', created)
    successMessage.value = `Entry saved: ${props.categories.find((c) => c.key === created.category)?.label ?? created.category}`
    setTimeout(() => (successMessage.value = ''), 3000)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Failed to save entry'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <section class="manual-entry">
    <form class="entry-form" @submit.prevent="handleSubmit">
      <div class="field">
        <label for="me-category">Category</label>
        <div class="select-wrapper" :style="{ '--accent': selectedColor() }">
          <select id="me-category" v-model="selectedCategory">
            <option v-for="cat in categories" :key="cat.key" :value="cat.key">
              {{ cat.label }}
            </option>
          </select>
        </div>
      </div>

      <div class="field">
        <label for="me-datetime">Time</label>
        <input id="me-datetime" type="datetime-local" v-model="selectedDatetime" />
      </div>

      <button type="submit" class="submit-btn" :disabled="isSubmitting">
        {{ isSubmitting ? 'Saving…' : 'Add Entry' }}
      </button>
    </form>

    <p v-if="successMessage" class="feedback success">{{ successMessage }}</p>
    <p v-if="errorMessage" class="feedback error">{{ errorMessage }}</p>
  </section>
</template>

<style scoped>
.manual-entry {
  background: #1a1d23;
  border: 1px solid #2a2d35;
  border-radius: 14px;
  padding: 1.25rem 1.5rem;
  margin: 1.5rem 0;
}

.section-title {
  margin: 0 0 1rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: #b1b7c3;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.entry-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: flex-end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

label {
  font-size: 0.8rem;
  font-weight: 500;
  color: #8890a0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.select-wrapper {
  position: relative;
}

.select-wrapper::after {
  content: '▾';
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--accent, #6c63ff);
  font-size: 0.85rem;
}

select {
  appearance: none;
  background: #0f1115;
  color: #f5f5f5;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  padding: 0.6rem 2.2rem 0.6rem 0.75rem;
  font-size: 0.9rem;
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s;
  min-width: 160px;
  border-left: 3px solid var(--accent, #6c63ff);
}

select:focus {
  border-color: var(--accent, #6c63ff);
}

input[type='datetime-local'] {
  background: #0f1115;
  color: #f5f5f5;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
  color-scheme: dark;
}

input[type='datetime-local']:focus {
  border-color: #6c63ff;
}

.submit-btn {
  background: #6c63ff;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 0.6rem 1.4rem;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.2s;
  white-space: nowrap;
}

.submit-btn:hover:not(:disabled) {
  opacity: 0.88;
  transform: translateY(-1px);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.feedback {
  margin: 0.6rem 0 0;
  font-size: 0.85rem;
  border-radius: 6px;
  padding: 0.4rem 0.75rem;
}

.success {
  color: #00b894;
  background: rgba(0, 184, 148, 0.1);
}

.error {
  color: #e17055;
  background: rgba(225, 112, 85, 0.1);
}
</style>
