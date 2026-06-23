<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  dayLabel: string
  displayName: string
  profileErrorMessage: string
  isProfileSaving: boolean
  isGuest: boolean
}>()

const emit = defineEmits<{
  shiftDay: [direction: -1 | 1]
  goToToday: []
  signOut: []
  displayNameChange: [displayName: string]
}>()

const isEditingProfile = ref(false)
const draftDisplayName = ref('')

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

const guestProfileNotice = 'Guest mode uses a shared profile. Sign in to personalize your Trace.'
</script>

<template>
  <header class="header">
    <div class="title">
      <span class="product-mark">Trace</span>
      <h1>Trace</h1>
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
        <span
          v-if="isGuest"
          class="locked-control profile-lock"
          :data-tooltip="guestProfileNotice"
          tabindex="0"
        >
          <button class="profile-name" type="button" disabled>
            {{ displayName }}
          </button>
        </span>
        <button
          v-else
          class="profile-name"
          type="button"
          title="Edit display name"
          @click="startProfileEdit"
        >
          {{ displayName }}
        </button>
        <button class="ghost" type="button" @click="emit('signOut')">
          {{ isGuest ? 'Leave guest' : 'Sign out' }}
        </button>
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
  margin-bottom: 1.5rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 22px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.095), rgba(255, 255, 255, 0.035)),
    rgba(14, 18, 25, 0.78);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.28);
  padding: 1.25rem;
  backdrop-filter: blur(18px);
}

.header .title {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.3rem;
}

.header h1 {
  margin: 0;
  font-size: clamp(2rem, 4vw, 3rem);
  line-height: 1;
  letter-spacing: 0;
}

.product-mark {
  border: 1px solid rgba(244, 209, 122, 0.22);
  border-radius: 999px;
  background: rgba(244, 209, 122, 0.08);
  color: #f4d17a;
  padding: 0.25rem 0.6rem;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
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
  background: rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  font-weight: 600;
}

.ghost {
  border: 1px solid rgba(255, 255, 255, 0.13);
  background: rgba(255, 255, 255, 0.045);
  color: #f5f5f5;
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  cursor: pointer;
}

.ghost:hover {
  border-color: rgba(92, 224, 199, 0.42);
  background: rgba(92, 224, 199, 0.08);
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
  border: 1px solid rgba(255, 255, 255, 0.13);
  background: rgba(255, 255, 255, 0.08);
  color: #f5f5f5;
  padding: 0.45rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 700;
}

.profile-name:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.locked-control {
  position: relative;
  display: inline-flex;
}

.locked-control::after {
  content: attr(data-tooltip);
  position: absolute;
  right: 0;
  bottom: calc(100% + 0.55rem);
  z-index: 5;
  width: min(18rem, 70vw);
  padding: 0.5rem 0.65rem;
  border: 1px solid #3a3f4b;
  border-radius: 8px;
  background: #151923;
  color: #f5f5f5;
  font-size: 0.78rem;
  font-weight: 500;
  line-height: 1.35;
  text-align: left;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.32);
  opacity: 0;
  pointer-events: none;
  transform: translateY(0.25rem);
  transition: opacity 0.14s ease, transform 0.14s ease;
}

.locked-control:hover::after,
.locked-control:focus-visible::after {
  opacity: 1;
  transform: translateY(0);
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
