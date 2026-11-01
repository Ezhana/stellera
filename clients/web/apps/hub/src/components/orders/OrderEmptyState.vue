<script setup lang="ts">
import UiIcon from '@/components/ui/UiIcon.vue'
import type { IconName } from '@/models'

interface OrderEmptyStateProps {
  title: string
  description: string
  icon?: IconName
}

withDefaults(defineProps<OrderEmptyStateProps>(), {
  icon: 'orders',
})
</script>

<template>
  <div class="order-empty">
    <span class="order-empty__icon" aria-hidden="true">
      <UiIcon :name="icon" :size="26" />
    </span>
    <p class="order-empty__title">{{ title }}</p>
    <p class="order-empty__description">{{ description }}</p>
    <div v-if="$slots.action" class="order-empty__action">
      <slot name="action" />
    </div>
  </div>
</template>

<style scoped>
.order-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--primitive-space-2);
  padding: var(--primitive-space-10) var(--primitive-space-6);
  text-align: center;
}

.order-empty__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  margin-bottom: var(--primitive-space-2);
  color: var(--color-fg-muted);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-pill);
}

.order-empty__title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
}

.order-empty__description {
  max-width: 46ch;
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.order-empty__action {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--primitive-space-2);
  margin-top: var(--primitive-space-2);
}
</style>
