<script setup lang="ts">
import { computed } from 'vue'

import UiCard from '@/components/ui/UiCard.vue'
import type { OrderStatsView } from '@/models'

interface OrderStatsGridProps {
  stats: OrderStatsView
  totalLabel?: string
}

const props = withDefaults(defineProps<OrderStatsGridProps>(), {
  totalLabel: '订单总数',
})

interface StatCard {
  key: string
  label: string
  value: string
  meta: string
  money?: boolean
}

const cards = computed<StatCard[]>(() => [
  {
    key: 'total',
    label: props.totalLabel,
    value: String(props.stats.total),
    meta: '已加载需求',
  },
  {
    key: 'open',
    label: '待接单',
    value: String(props.stats.openCount),
    meta: '等待工程师接单',
  },
  {
    key: 'progress',
    label: '交付中',
    value: String(props.stats.inProgressCount),
    meta: '工程师交付中',
  },
  {
    key: 'escrow',
    label: '托管金额',
    value: props.stats.escrowHeldLabel,
    meta: '平台资金托管',
    money: true,
  },
])
</script>

<template>
  <div class="order-stats">
    <UiCard v-for="card in cards" :key="card.key" padding="md" class="order-stats__card">
      <p class="order-stats__label">{{ card.label }}</p>
      <p class="order-stats__value" :class="{ 'order-stats__value--money': card.money }">
        {{ card.value }}
      </p>
      <p class="order-stats__meta">{{ card.meta }}</p>
    </UiCard>
  </div>
</template>

<style scoped>
.order-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.order-stats__card {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
}

.order-stats__label {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  letter-spacing: var(--font-letter-spacing-label);
}

.order-stats__value {
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h2);
  font-variant-numeric: tabular-nums;
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.order-stats__value--money {
  color: var(--obsidian-gold-text);
  font-size: var(--font-size-h3);
}

.order-stats__meta {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}

@media (max-width: 1100px) {
  .order-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .order-stats {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
