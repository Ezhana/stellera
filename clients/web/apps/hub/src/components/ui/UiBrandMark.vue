<script setup lang="ts">
withDefaults(
  defineProps<{
    /** Rendered width/height in pixels (or any CSS length). */
    size?: number | string
    /** Accessible name. When omitted the mark is decorative. */
    title?: string
  }>(),
  { size: 40, title: undefined },
)
</script>

<template>
  <svg
    class="ui-brand-mark"
    :width="size"
    :height="size"
    viewBox="0 0 48 48"
    fill="none"
    :role="title ? 'img' : undefined"
    :aria-label="title"
    :aria-hidden="title ? undefined : 'true'"
  >
    <rect x="2.5" y="2.5" width="43" height="43" rx="8" stroke="currentColor" stroke-width="2" />
    <path
      d="M31 14H18a5 5 0 0 0 0 10h12a5 5 0 0 1 0 10H16"
      stroke="currentColor"
      stroke-width="3"
      stroke-linecap="square"
    />
  </svg>
</template>

<style scoped>
.ui-brand-mark {
  flex: none;
  color: var(--color-accent);
}
</style>
