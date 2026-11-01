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
    <template v-if="name === 'orders'">
      <path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5H7a.5.5 0 0 1-.5-.5V4a.5.5 0 0 1 .5-.5Z" />
      <path d="M14 3.5V8h4.5" />
      <path d="M9 12h6M9 15.5h6" />
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

    <template v-else-if="name === 'intro'">
      <circle cx="12" cy="12" r="8.5" />
      <path d="m15.6 8.4-2.2 5-5 2.2 2.2-5 5-2.2Z" />
    </template>

    <template v-else-if="name === 'briefcase'">
      <rect x="3.2" y="7.3" width="17.6" height="12.2" rx="2" />
      <path d="M8.6 7.3V6a2 2 0 0 1 2-2h2.8a2 2 0 0 1 2 2v1.3" />
      <path d="M3.2 12h17.6M10 12v2h4v-2" />
    </template>

    <template v-else-if="name === 'live'">
      <circle cx="12" cy="18" r="1.4" />
      <path d="M7.9 14.3a6 6 0 0 1 8.2 0" />
      <path d="M4.9 10.9a10.3 10.3 0 0 1 14.2 0" />
    </template>

    <template v-else-if="name === 'spark'">
      <path
        d="M12 3.4c.7 4.3 2.9 6.5 7.1 7.2-4.2.7-6.4 2.9-7.1 7.2-.7-4.3-2.9-6.5-7.1-7.2 4.2-.7 6.4-2.9 7.1-7.2Z"
      />
    </template>

    <template v-else-if="name === 'target'">
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1" />
    </template>

    <template v-else-if="name === 'clock'">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </template>

    <template v-else-if="name === 'coins'">
      <ellipse cx="12" cy="6.4" rx="6.4" ry="2.5" />
      <path d="M5.6 6.4v5c0 1.4 2.9 2.5 6.4 2.5s6.4-1.1 6.4-2.5v-5" />
      <path d="M5.6 11.4v5c0 1.4 2.9 2.5 6.4 2.5s6.4-1.1 6.4-2.5v-5" />
    </template>

    <template v-else-if="name === 'plus'">
      <path d="M12 5v14M5 12h14" />
    </template>

    <template v-else-if="name === 'filter'">
      <path d="M4 6.5h16M7 12h10M10 17.5h4" />
    </template>

    <template v-else-if="name === 'refresh'">
      <path d="M19 12a7 7 0 1 1-2.05-4.95" />
      <path d="M19 4.5V9h-4.5" />
    </template>

    <template v-else-if="name === 'logs'">
      <path d="M6.5 3.5h7l4 4V20a.5.5 0 0 1-.5.5H6.5a.5.5 0 0 1-.5-.5V4a.5.5 0 0 1 .5-.5Z" />
      <path d="M13.5 3.5V8H18" />
      <path d="M9.5 12h5M9.5 15h5M9.5 18h3" />
    </template>

    <template v-else-if="name === 'check'">
      <path d="m5 12.5 4.5 4.5L19 7" />
    </template>

    <template v-else-if="name === 'close'">
      <path d="m6 6 12 12M18 6 6 18" />
    </template>

    <template v-else-if="name === 'arrow-left'">
      <path d="M19 12H5" />
      <path d="m10 7-5 5 5 5" />
    </template>

    <template v-else-if="name === 'arrow-right'">
      <path d="M5 12h14" />
      <path d="m14 7 5 5-5 5" />
    </template>

    <template v-else-if="name === 'building'">
      <path d="M3.5 20.5h17" />
      <path d="M6 20.5V5.5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v15" />
      <path d="M14 9.5h3a1 1 0 0 1 1 1v10" />
      <path d="M9 8h2M9 11.5h2M9 15h2" />
    </template>

    <template v-else-if="name === 'wrench'">
      <path
        d="M11.4 6.6a4.5 4.5 0 0 1 5.2-5.2l-2.9 2.9 2 2 2.9-2.9a4.5 4.5 0 0 1-5.2 5.2l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-5.9Z"
      />
    </template>
  </svg>
</template>

<style scoped>
.ui-icon {
  flex: none;
}
</style>
