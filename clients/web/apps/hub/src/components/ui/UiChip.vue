<script setup lang="ts">
import { computed } from 'vue'

import type { BadgeTone } from '@/models'

const props = withDefaults(defineProps<{ variant?: BadgeTone }>(), {
  variant: 'default',
})

const classes = computed(() => ['ui-chip', `ui-chip--${props.variant}`])
</script>

<template>
  <span :class="classes"><slot /></span>
</template>

<style scoped>
/* Obsidian badge: a pill badge, never a clickable filter chip. */
.ui-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-1) var(--primitive-space-3);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--obsidian-surface-glass);
  color: var(--color-fg-muted);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
  white-space: nowrap;
}

/* Gold badge = tinted surface, not a second primary action. */
.ui-chip--accent {
  background: var(--color-accent-subtle);
  border-color: var(--color-accent-border);
  color: var(--obsidian-gold-text);
}

.ui-chip--info {
  background: var(--color-info-subtle);
  border-color: transparent;
  color: var(--color-info);
}

.ui-chip--success {
  background: var(--color-success-subtle);
  border-color: transparent;
  color: var(--color-success);
}

.ui-chip--warning {
  background: var(--color-warning-subtle);
  border-color: transparent;
  color: var(--color-warning);
}

.ui-chip--error {
  background: var(--color-danger-subtle);
  border-color: transparent;
  color: var(--color-danger);
}
</style>
