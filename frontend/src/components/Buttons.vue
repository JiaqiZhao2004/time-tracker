<script setup lang="ts">
import { computed, ref } from 'vue'
import { categoryNameValidationError, normalizeCategoryName } from '../domain/categoryNames'
import { createCategory, setCategoryActive } from '../services/api'
import type { Category, DisplayCategory } from '../types/category'

const props = defineProps<{
  categories: DisplayCategory[]
  lastCategory: DisplayCategory | null
}>()

const emit = defineEmits<{
  logCategory: [categoryId: string]
  categoryChanged: [category: Category]
}>()

const isEditing = ref(false)
const newCategoryName = ref('')
const inputError = ref('')
const operationError = ref('')
const isCreating = ref(false)
const updatingCategoryId = ref<string | null>(null)

const activeCategories = computed(() => props.categories.filter((category) => category.isActive))
const disabledCategories = computed(() => props.categories.filter((category) => !category.isActive))

const toggleEditing = () => {
  isEditing.value = !isEditing.value
  inputError.value = ''
  operationError.value = ''
}

const handleCreateCategory = async () => {
  inputError.value = categoryNameValidationError(newCategoryName.value, props.categories)
  operationError.value = ''
  if (inputError.value) {
    return
  }

  isCreating.value = true
  try {
    const created = await createCategory(normalizeCategoryName(newCategoryName.value))
    emit('categoryChanged', created)
    newCategoryName.value = ''
  } catch (error) {
    operationError.value = error instanceof Error ? error.message : 'Failed to add category'
  } finally {
    isCreating.value = false
  }
}

const updateCategoryStatus = async (category: DisplayCategory, isActive: boolean) => {
  operationError.value = ''
  updatingCategoryId.value = category.categoryId
  try {
    const updated = await setCategoryActive(category.categoryId, isActive)
    emit('categoryChanged', updated)
  } catch (error) {
    operationError.value = error instanceof Error ? error.message : 'Failed to update category'
  } finally {
    updatingCategoryId.value = null
  }
}
</script>

<template>
  <section class="controls" :class="{ editing: isEditing }">
    <div class="controls-header">
      <span v-if="isEditing" class="title">Categories</span>
      <button class="edit-toggle" type="button" @click="toggleEditing">
        {{ isEditing ? 'Done' : 'Edit Categories' }}
      </button>
    </div>

    <form v-if="isEditing" class="add-form" @submit.prevent="handleCreateCategory">
      <label for="new-category-name">Add Category</label>
      <div class="add-row">
        <input
          id="new-category-name"
          v-model="newCategoryName"
          type="text"
          autocomplete="off"
          placeholder="Category name"
          @input="inputError = ''"
        />
        <button class="add-button" type="submit" :disabled="isCreating">
          {{ isCreating ? 'Adding...' : 'Add' }}
        </button>
      </div>
      <p v-if="inputError" class="feedback error">{{ inputError }}</p>
    </form>

    <div v-if="!isEditing" class="category-grid">
      <button
        v-for="item in activeCategories"
        :key="item.categoryId"
        class="category-button"
        :style="{ backgroundColor: item.color }"
        type="button"
        @click="emit('logCategory', item.categoryId)"
      >
        {{ item.name }}
      </button>
      <p v-if="activeCategories.length === 0" class="empty-state">
        No active categories. Edit categories to add or enable one.
      </p>
    </div>

    <template v-else>
      <div class="category-grid">
        <div
          v-for="item in activeCategories"
          :key="item.categoryId"
          class="category-tile"
          :style="{ backgroundColor: item.color }"
        >
          <span>{{ item.name }}</span>
          <button
            class="status-toggle"
            type="button"
            :aria-label="`Disable ${item.name}`"
            :disabled="updatingCategoryId !== null"
            @click="updateCategoryStatus(item, false)"
          >
            -
          </button>
        </div>
      </div>

      <div class="disabled-section">
        <h3>Disabled</h3>
        <div class="category-grid">
          <div
            v-for="item in disabledCategories"
            :key="item.categoryId"
            class="category-tile disabled"
            :style="{ '--category-color': item.color }"
          >
            <span>{{ item.name }}</span>
            <button
              class="status-toggle"
              type="button"
              :aria-label="`Enable ${item.name}`"
              :disabled="updatingCategoryId !== null"
              @click="updateCategoryStatus(item, true)"
            >
              +
            </button>
          </div>
          <p v-if="disabledCategories.length === 0" class="empty-state">No disabled categories.</p>
        </div>
      </div>
    </template>

    <p v-if="operationError" class="feedback error">{{ operationError }}</p>
    <p class="last-selection" v-if="lastCategory">
      Last selection: {{ lastCategory.name }}
    </p>
  </section>
</template>

<style scoped>
.controls {
  margin: 2rem 0;
}

.controls.editing {
  background: #1a1d23;
  border: 1px solid #2a2d35;
  border-radius: 16px;
  padding: 1.25rem;
  box-shadow: 0 20px 35px rgba(0, 0, 0, 0.28);
}

.controls-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 0.75rem;
}

.title {
  margin-right: auto;
  color: #f5f5f5;
  font-size: 1rem;
  font-weight: 600;
}

.edit-toggle {
  background: transparent;
  border: 1px solid #3a3f4b;
  color: #b1b7c3;
  border-radius: 8px;
  padding: 0.45rem 0.85rem;
  font-size: 0.85rem;
}

.edit-toggle:hover {
  color: #f5f5f5;
  border-color: #6c63ff;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
}

.category-button,
.category-tile {
  min-height: 48px;
  color: #fff;
  font-weight: 600;
  padding: 0.85rem 1rem;
  border-radius: 12px;
  box-sizing: border-box;
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
}

.category-button {
  border: none;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.category-button:hover {
  transform: translateY(-2px);
}

.category-tile {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
}

.category-tile.disabled {
  background: #14171c;
  border: 2px solid var(--category-color);
  color: #c4c8d0;
  box-shadow: none;
  opacity: 0.82;
}

.status-toggle {
  position: absolute;
  top: -8px;
  right: -8px;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  width: 25px;
  height: 25px;
  padding: 0;
  background: #f5f5f5;
  border: 2px solid #1a1d23;
  border-radius: 50%;
  color: #1a1d23;
  font-size: 1rem;
  line-height: 1;
  font-weight: 700;
}

.status-toggle:disabled {
  cursor: wait;
  opacity: 0.55;
}

.add-form {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  margin-bottom: 1.25rem;
}

.add-form label,
.disabled-section h3 {
  color: #8890a0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.8rem;
  font-weight: 500;
}

.add-row {
  display: flex;
  gap: 0.6rem;
  width: min(100%, 420px);
}

.add-row input {
  flex: 1;
  min-width: 0;
  background: #0f1115;
  color: #f5f5f5;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
  font-size: 0.9rem;
}

.add-row input:focus {
  outline: none;
  border-color: #6c63ff;
}

.add-button {
  background: #6c63ff;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 0.6rem 1rem;
}

.add-button:disabled {
  opacity: 0.55;
  cursor: wait;
}

.disabled-section {
  border-top: 1px solid #2a2d35;
  margin-top: 1.35rem;
  padding-top: 1rem;
}

.disabled-section h3 {
  margin: 0 0 0.75rem;
}

.empty-state {
  grid-column: 1 / -1;
  margin: 0;
  padding: 0.7rem 0;
  color: #8890a0;
  font-size: 0.9rem;
}

.last-selection {
  margin: 1rem 0 0;
  color: #b1b7c3;
  font-size: 0.9rem;
}

.feedback {
  margin: 0.6rem 0 0;
  font-size: 0.85rem;
  border-radius: 6px;
  padding: 0.4rem 0.75rem;
}

.error {
  color: #e17055;
  background: rgba(225, 112, 85, 0.1);
}

@media (max-width: 768px) {
  .controls {
    margin: 1.5rem 0;
  }

  .category-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.6rem;
  }

  .category-button,
  .category-tile {
    padding: 0.75rem 0.5rem;
    font-size: 0.9rem;
  }
}
</style>
