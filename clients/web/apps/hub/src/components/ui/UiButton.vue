<script setup lang="ts">
import { computed } from 'vue'

type UiButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive'
type UiButtonSize = 'sm' | 'md' | 'lg'

interface UiButtonProps {
  variant?: UiButtonVariant
  size?: UiButtonSize
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  loading?: boolean
  block?: boolean
}

const props = withDefaults(defineProps<UiButtonProps>(), {
  variant: 'primary',
  size: 'md',
  type: 'button',
  disabled: false,
  loading: false,
  block: false,
})

const classes = computed(() => [
  'ui-button',
  `ui-button--${props.variant}`,
  `ui-button--${props.size}`,
  { 'ui-button--block': props.block, 'ui-button--loading': props.loading },
])
</script>

<template>
  <button
    :class="classes"
    :type="type"
    :disabled="disabled || loading"
    :aria-busy="loading ? 'true' : undefined"
  >
    <span v-if="loading" class="ui-button__spinner" aria-hidden="true" />
    <span class="ui-button__label"><slot /></span>
  </button>
</template>

<style scoped>
.ui-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-2);
  min-height: 44px;
  padding: 0 20px;
  border: var(--border-width-default) solid transparent;
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.01em;
  line-height: 1;
  text-align: center;
  transition:
    background-color var(--motion-duration-fast) var(--motion-easing-standard),
    border-color var(--motion-duration-fast) var(--motion-easing-standard),
    color var(--motion-duration-fast) var(--motion-easing-standard),
    filter var(--motion-duration-fast) var(--motion-easing-standard);
}

.ui-button:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.ui-button--block {
  width: 100%;
}

/* Sizes — Obsidian source §10.1. */
.ui-button--sm {
  min-height: 36px;
  padding: 0 var(--primitive-space-4);
  font-size: var(--font-size-small);
}

.ui-button--md {
  min-height: 44px;
  padding: 0 var(--primitive-space-5);
  font-size: var(--font-size-small);
}

.ui-button--lg {
  min-height: 52px;
  padding: 0 1.75rem;
  font-size: var(--font-size-body);
}

/* Primary — the screen's one gold focal point: gradient fill, ink text, gold glow. */
.ui-button--primary {
  color: var(--color-on-accent);
  background: var(--obsidian-gold-gradient);
  border-color: transparent;
  box-shadow: var(--shadow-glow);
  font-weight: var(--font-weight-strong);
}

.ui-button--primary:hover:not(:disabled) {
  filter: brightness(1.05);
}

.ui-button--primary:active:not(:disabled) {
  filter: brightness(0.95);
}

/* Secondary — glass fill, strong hairline, gold on hover. */
.ui-button--secondary {
  color: var(--color-fg);
  background: var(--obsidian-surface-glass);
  border-color: var(--obsidian-border-strong);
}

.ui-button--secondary:hover:not(:disabled) {
  border-color: var(--color-accent);
}

/* Ghost — no fill, muted text that strengthens. */
.ui-button--ghost {
  color: var(--color-fg-muted);
  background: transparent;
  border-color: transparent;
}

.ui-button--ghost:hover:not(:disabled) {
  color: var(--color-fg);
}

/* Destructive — derived claret fill, ivory text. */
.ui-button--destructive {
  color: var(--color-on-danger);
  background-color: var(--color-danger-solid);
  border-color: var(--color-danger);
  font-weight: var(--font-weight-strong);
}

.ui-button--destructive:hover:not(:disabled) {
  filter: brightness(1.08);
}

.ui-button:disabled {
  opacity: 0.45;
  pointer-events: none;
  box-shadow: none;
}

.ui-button--loading {
  cursor: progress;
}

.ui-button__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: var(--radius-pill);
  animation: ui-button-spin 0.8s linear infinite;
}

@keyframes ui-button-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
