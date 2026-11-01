<script setup lang="ts">
import { computed } from 'vue'

type UiCardPadding = 'none' | 'md' | 'lg'

interface UiCardProps {
  /** Floating card layer: elevated surface, strong hairline and a real shadow. */
  elevated?: boolean
  padding?: UiCardPadding
}

const props = withDefaults(defineProps<UiCardProps>(), {
  elevated: false,
  padding: 'md',
})

const classes = computed(() => [
  'ui-card',
  `ui-card--padding-${props.padding}`,
  { 'ui-card--elevated': props.elevated },
])
</script>

<template>
  <section :class="classes">
    <slot />
  </section>
</template>

<style scoped>
.ui-card {
  background-color: var(--color-surface);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-surface);
  box-shadow: var(--obsidian-panel-highlight);
}

.ui-card--padding-none {
  padding: 0;
}

.ui-card--padding-md {
  padding: var(--primitive-space-6);
}

.ui-card--padding-lg {
  padding: var(--primitive-space-8);
}

/* A floating card uses the elevated surface and a real shadow; it never glows. */
.ui-card--elevated {
  background-color: var(--color-surface-elevated);
  border-color: var(--obsidian-border-strong);
  box-shadow: var(--obsidian-panel-highlight), var(--shadow-lg);
}
</style>
