<script setup lang="ts">
import type { FdeOrderStatus } from '@/models'
import { FDE_ORDER_STATUSES } from '@/models'

type StatusTab = FdeOrderStatus | 'all'

const model = defineModel<StatusTab>({ default: 'all' })

const tabs: readonly { key: StatusTab; label: string }[] = [
  { key: 'all', label: '全部' },
  ...FDE_ORDER_STATUSES.map((status) => ({ key: status.key, label: status.label })),
]
</script>

<template>
  <div class="status-tabs" role="group" aria-label="按订单状态筛选">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      class="status-tabs__button"
      :class="{ 'is-active': model === tab.key }"
      type="button"
      :aria-pressed="model === tab.key ? 'true' : 'false'"
      @click="model = tab.key"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<style scoped>
.status-tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-1);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.status-tabs__button {
  min-height: 32px;
  padding: 0 var(--primitive-space-3);
  color: var(--color-fg-muted);
  background: transparent;
  border: var(--border-width-default) solid transparent;
  border-radius: var(--radius-small);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: 1;
  white-space: nowrap;
  transition:
    color var(--motion-duration-fast) var(--motion-easing-standard),
    background-color var(--motion-duration-fast) var(--motion-easing-standard),
    border-color var(--motion-duration-fast) var(--motion-easing-standard);
}

.status-tabs__button:hover {
  color: var(--color-fg);
}

.status-tabs__button.is-active {
  color: var(--obsidian-gold-text);
  background-color: var(--color-accent-subtle);
  border-color: var(--color-accent-border);
}
</style>
