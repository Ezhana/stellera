<script setup lang="ts">
import type { IconName } from '@/models'

withDefaults(
  defineProps<{
    name: IconName
    size?: number | string
    strokeWidth?: number
  }>(),
  { size: 20, strokeWidth: 1.8 },
)
</script>

<template>
  <svg
    class="ui-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    :stroke-width="strokeWidth"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-if="name === 'overview'">
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
    </template>

    <template v-else-if="name === 'wallet'">
      <path
        d="M4 7.5A2.5 2.5 0 0 1 6.5 5H19a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H6.5A2.5 2.5 0 0 1 4 16.5v-9Z"
      />
      <path d="M4 8h13" />
      <circle cx="16.5" cy="13" r="1.1" />
    </template>

    <template v-else-if="name === 'orders'">
      <path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5H7a.5.5 0 0 1-.5-.5V4a.5.5 0 0 1 .5-.5Z" />
      <path d="M14 3.5V8h4.5" />
      <path d="M9 12h6M9 15.5h6" />
    </template>

    <template v-else-if="name === 'plaza'">
      <path d="M4 9h16" />
      <path d="M5.5 9v10.5h13V9" />
      <path d="M8 9V6.5a4 4 0 0 1 8 0V9" />
      <path d="M9.5 19.5V15h5v4.5" />
    </template>

    <template v-else-if="name === 'logout'">
      <path d="M10 5H6.5A1.5 1.5 0 0 0 5 6.5v11A1.5 1.5 0 0 0 6.5 19H10" />
      <path d="m14 8 4 4-4 4" />
      <path d="M18 12H9" />
    </template>

    <template v-else-if="name === 'shield'">
      <path d="M12 3.5 19 6v5.2c0 4.4-2.9 7.8-7 9.3-4.1-1.5-7-4.9-7-9.3V6l7-2.5Z" />
      <path d="m9.4 11.9 1.8 1.8 3.5-3.7" />
    </template>

    <template v-else-if="name === 'user'">
      <circle cx="12" cy="8" r="3.4" />
      <path d="M5.2 20c.7-3.3 3.4-5 6.8-5s6.1 1.7 6.8 5" />
    </template>

    <template v-else-if="name === 'mail'">
      <rect x="3.5" y="5.5" width="17" height="13" rx="2" />
      <path d="m4.5 7.5 7.5 5.6 7.5-5.6" />
    </template>

    <template v-else-if="name === 'key'">
      <circle cx="8" cy="15.5" r="3.8" />
      <path d="m10.8 12.7 8-8M16.5 7l2 2M14.5 9l2 2" />
    </template>

    <template v-else-if="name === 'chevron'">
      <path d="m9 6 6 6-6 6" />
    </template>

    <template v-else-if="name === 'eye'">
      <path d="M2.8 12s3.4-6 9.2-6 9.2 6 9.2 6-3.4 6-9.2 6-9.2-6-9.2-6Z" />
      <circle cx="12" cy="12" r="2.6" />
    </template>

    <template v-else-if="name === 'eye-off'">
      <path d="m3.5 3.5 17 17" />
      <path d="M10.6 5.4A10.7 10.7 0 0 1 12 5.3c5.8 0 9.2 6 9.2 6a18 18 0 0 1-3.1 4" />
      <path d="M6.4 7C4.1 8.7 2.8 12 2.8 12s3.4 6 9.2 6a10.5 10.5 0 0 0 4-.8" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </template>
  </svg>
</template>

<style scoped>
.ui-icon {
  flex: none;
}
</style>
