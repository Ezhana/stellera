<script setup lang="ts">
import { computed } from 'vue'

import type { OrderRealtimeState } from '@/bff/orders'

interface LiveStatusProps {
  state: OrderRealtimeState
  lastEventLabel?: string
}

const props = withDefaults(defineProps<LiveStatusProps>(), {
  lastEventLabel: undefined,
})

const STATE_META: Record<
  OrderRealtimeState,
  { label: string; tone: 'default' | 'warning' | 'success' }
> = {
  connecting: { label: '连接中', tone: 'warning' },
  live: { label: '实时同步', tone: 'success' },
  reconnecting: { label: '重连中', tone: 'warning' },
  offline: { label: '已断开', tone: 'default' },
}

const meta = computed(() => STATE_META[props.state])
</script>

<template>
  <span class="live-status" :class="`live-status--${meta.tone}`" role="status" aria-live="polite">
    <span class="live-status__dot" aria-hidden="true" />
    <span class="live-status__label">{{ meta.label }}</span>
    <span v-if="lastEventLabel" class="live-status__event">{{ lastEventLabel }}</span>
  </span>
</template>

<style scoped>
.live-status {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
  max-width: 100%;
  padding: var(--primitive-space-1) var(--primitive-space-3);
  background: var(--obsidian-surface-glass);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-pill);
  color: var(--color-fg-muted);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: 1.4;
  white-space: nowrap;
}

.live-status__dot {
  width: 7px;
  height: 7px;
  flex: none;
  background-color: var(--color-fg-muted);
  border-radius: var(--radius-pill);
}

.live-status__label {
  flex: none;
}

.live-status__event {
  max-width: 15rem;
  overflow: hidden;
  color: var(--obsidian-tertiary-text);
  text-overflow: ellipsis;
}

.live-status--success .live-status__label {
  color: var(--color-success);
}

.live-status--success .live-status__dot {
  background-color: var(--color-success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-success) 18%, transparent);
}

.live-status--warning .live-status__label {
  color: var(--color-warning);
}

.live-status--warning .live-status__dot {
  background-color: var(--color-warning);
  animation: live-status-pulse 1.6s var(--motion-easing-standard) infinite;
}

@keyframes live-status-pulse {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.4;
  }
}
</style>
