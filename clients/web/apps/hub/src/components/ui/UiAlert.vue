<script setup lang="ts">
import { computed } from 'vue'

type UiAlertVariant = 'error' | 'success' | 'warning' | 'info'

interface UiAlertProps {
  variant?: UiAlertVariant
  title?: string
  dismissible?: boolean
}

const props = withDefaults(defineProps<UiAlertProps>(), {
  variant: 'error',
  title: undefined,
  dismissible: false,
})

defineEmits<{ close: [] }>()

const marks: Record<UiAlertVariant, string> = {
  error: '!',
  success: '✓',
  warning: '!',
  info: 'i',
}

const classes = computed(() => ['ui-alert', `ui-alert--${props.variant}`])
const mark = computed(() => marks[props.variant])
</script>

<template>
  <div
    :class="classes"
    :role="variant === 'error' ? 'alert' : 'status'"
    :aria-live="variant === 'error' ? 'assertive' : 'polite'"
  >
    <span class="ui-alert__mark" aria-hidden="true">{{ mark }}</span>
    <div class="ui-alert__body">
      <p v-if="title" class="ui-alert__title">{{ title }}</p>
      <div class="ui-alert__message"><slot /></div>
    </div>
    <button
      v-if="dismissible"
      class="ui-alert__close"
      type="button"
      aria-label="关闭提示"
      @click="$emit('close')"
    >
      ×
    </button>
  </div>
</template>

<style scoped>
.ui-alert {
  display: flex;
  align-items: flex-start;
  gap: var(--primitive-space-3);
  padding: 12px 16px;
  border: var(--border-width-default) solid transparent;
  border-left-width: var(--border-width-default);
  border-radius: var(--radius-control);
  box-shadow: var(--shadow-sm);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  line-height: var(--font-line-height-small);
}

.ui-alert--error {
  background-color: var(--color-danger-subtle);
  border-left-color: var(--color-danger);
}

.ui-alert--success {
  background-color: var(--color-success-subtle);
  border-left-color: var(--color-success);
}

.ui-alert--warning {
  background-color: var(--color-warning-subtle);
  border-left-color: var(--color-warning);
}

.ui-alert--info {
  background-color: var(--color-info-subtle);
  border-left-color: var(--color-info);
}

.ui-alert__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex: none;
  border: var(--border-width-default) solid currentColor;
  border-radius: var(--radius-small);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-bold);
  line-height: 1;
}

.ui-alert--error .ui-alert__mark {
  color: var(--color-danger);
}

.ui-alert--success .ui-alert__mark {
  color: var(--color-success);
}

.ui-alert--warning .ui-alert__mark {
  color: var(--color-warning);
}

.ui-alert--info .ui-alert__mark {
  color: var(--color-info);
}

.ui-alert__body {
  flex: 1;
  min-width: 0;
}

.ui-alert__title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-strong);
}

.ui-alert__message {
  color: var(--color-fg);
}

.ui-alert__title + .ui-alert__message {
  margin-top: var(--primitive-space-1);
}

.ui-alert__close {
  padding: 0 2px;
  margin-left: auto;
  background: transparent;
  border: 0;
  color: var(--color-fg-muted);
  font-size: var(--font-size-body-lg);
  line-height: 1;
}

.ui-alert__close:hover {
  color: var(--color-fg);
}
</style>
