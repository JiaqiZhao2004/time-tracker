<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  dayLabel: string
  displayName: string
  profileErrorMessage: string
  isProfileSaving: boolean
}>()

const emit = defineEmits<{
  shiftDay: [direction: -1 | 1]
  goToToday: []
  signOut: []
  displayNameChange: [displayName: string]
}>()

const isEditingProfile = ref(false)
const draftDisplayName = ref('')
const appTitle = computed(() => {
  const name = props.displayName.trim()
  return name ? `${name}'s Trace` : 'Your Trace'
})

watch(
  () => props.displayName,
  (value) => {
    if (!isEditingProfile.value) {
      draftDisplayName.value = value
    }
  },
  { immediate: true },
)

const startProfileEdit = () => {
  draftDisplayName.value = props.displayName
  isEditingProfile.value = true
}

const cancelProfileEdit = () => {
  draftDisplayName.value = props.displayName
  isEditingProfile.value = false
}

const saveProfile = () => {
  const nextName = draftDisplayName.value.trim()
  if (!nextName || nextName === props.displayName) {
    cancelProfileEdit()
    return
  }
  emit('displayNameChange', nextName)
  isEditingProfile.value = false
}
</script>

<template>
  <header class="header">
    <div class="title">
      <h1>{{ appTitle }}</h1>
      <p>See where your time goes and how your days take shape.</p>
    </div>
    <div class="day-controls">
      <button class="ghost" @click="emit('shiftDay', -1)">Previous</button>
      <span class="day-label">{{ dayLabel }}</span>
      <button class="ghost" @click="emit('shiftDay', 1)">Next</button>
      <button class="ghost" @click="emit('goToToday')">Today</button>
    </div>
    <div class="profile">
      <form v-if="isEditingProfile" class="profile-form" @submit.prevent="saveProfile">
        <input
          v-model="draftDisplayName"
          type="text"
          autocomplete="name"
          aria-label="Display name"
          :disabled="isProfileSaving"
        />
        <button class="ghost" type="submit" :disabled="isProfileSaving">Save</button>
        <button class="ghost" type="button" :disabled="isProfileSaving" @click="cancelProfileEdit">
          Cancel
        </button>
      </form>
      <template v-else>
        <button class="profile-name" type="button" @click="startProfileEdit">
          {{ displayName }}
        </button>
        <button class="ghost" type="button" @click="emit('signOut')">Sign out</button>
      </template>
      <p v-if="profileErrorMessage" class="profile-error">{{ profileErrorMessage }}</p>
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
  border-radius: 8px;
  cursor: pointer;
}

.ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.profile {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.6rem;
  align-items: center;
}

.profile-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.profile-form input {
  min-width: 10rem;
  border: 1px solid #2f3645;
  background: #151923;
  color: #f5f5f5;
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
}

.profile-name {
  border: 1px solid #2f3645;
  background: #1b1f2a;
  color: #f5f5f5;
  padding: 0.45rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 700;
}

.profile-error {
  flex-basis: 100%;
  margin: 0;
  color: #ffb4b4;
  text-align: right;
}

@media (max-width: 720px) {
  .header {
    flex-direction: column;
    align-items: flex-start;
  }

  .profile {
    justify-content: flex-start;
  }

  .profile-error {
    text-align: left;
  }
}
</style>
