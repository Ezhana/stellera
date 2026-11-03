<script setup lang="ts">
import CertificationMark from '@/components/identity/CertificationMark.vue'
import UiChip from '@/components/ui/UiChip.vue'
import type { FdeOrderView } from '@/models'

interface OrderTableProps {
  orders: readonly FdeOrderView[]
  viewerId: string
  caption: string
  /** Published-orders page shows a dedicated work-log column. */
  showWorkLog?: boolean
  highlightedId?: string | null
}

withDefaults(defineProps<OrderTableProps>(), {
  showWorkLog: false,
  highlightedId: null,
})
</script>

<template>
  <div class="order-table__scroll">
    <table class="order-table">
      <caption class="visually-hidden">
        {{
          caption
        }}
      </caption>
      <thead>
        <tr>
          <th scope="col">任务</th>
          <th scope="col">发布者</th>
          <th scope="col">接单工程师</th>
          <th scope="col">行业</th>
          <th scope="col">交付周期</th>
          <th scope="col">价格</th>
          <th scope="col">状态</th>
          <th v-if="showWorkLog" scope="col">工作日志</th>
          <th scope="col">托管</th>
          <th scope="col">发布时间</th>
          <th v-if="$slots.actions" scope="col">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="order in orders"
          :key="order.id"
          class="order-table__row"
          :class="{ 'is-highlighted': order.id === highlightedId }"
        >
          <td class="order-table__cell order-table__cell--task">
            <p class="order-table__title">{{ order.title }}</p>
            <div class="order-table__meta">
              <span class="order-table__code">{{ order.code }}</span>
              <UiChip v-if="order.publisherId === viewerId" variant="accent">我的发布</UiChip>
            </div>
          </td>
          <td class="order-table__cell">
            <div class="order-table__party">
              <span class="order-table__party-name">{{ order.publisherName }}</span>
              <CertificationMark :certification="order.publisherCertification" />
            </div>
          </td>
          <td class="order-table__cell">
            <div v-if="order.engineerName" class="order-table__party">
              <span class="order-table__party-name">{{ order.engineerName }}</span>
              <CertificationMark :certification="order.engineerCertification" />
            </div>
            <span v-else class="order-table__hint">待接单</span>
          </td>
          <td class="order-table__cell">
            <span class="order-table__industry">{{ order.industry }}</span>
          </td>
          <td class="order-table__cell order-table__cell--nowrap">
            {{ order.deliveryLabel }}
          </td>
          <td class="order-table__cell order-table__price">{{ order.priceLabel }}</td>
          <td class="order-table__cell">
            <div class="order-table__status">
              <UiChip :variant="order.statusTone">{{ order.statusLabel }}</UiChip>
              <span v-if="!showWorkLog && order.workLogCount > 0" class="order-table__hint">
                {{ order.workLogCount }} 条日志
              </span>
            </div>
          </td>
          <td v-if="showWorkLog" class="order-table__cell order-table__cell--nowrap">
            <span class="order-table__logs">
              <span class="order-table__logs-count">{{ order.workLogCount }}</span> 条
            </span>
          </td>
          <td class="order-table__cell">
            <UiChip :variant="order.escrowTone">{{ order.escrowLabel }}</UiChip>
          </td>
          <td class="order-table__cell order-table__cell--nowrap">
            <time class="order-table__time" :datetime="order.createdAt">
              {{ order.publishedAtLabel }}
            </time>
          </td>
          <td v-if="$slots.actions" class="order-table__cell order-table__cell--actions">
            <div class="order-table__actions">
              <slot name="actions" :order="order" />
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.order-table__scroll {
  width: 100%;
  overflow-x: auto;
}

.order-table {
  width: 100%;
  min-width: 64rem;
  border-collapse: collapse;
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  text-align: left;
}

.order-table thead th {
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--obsidian-tertiary-text);
  border-bottom: var(--border-width-default) solid var(--color-border);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
  white-space: nowrap;
}

.order-table__row {
  transition: background-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.order-table__row + .order-table__row .order-table__cell {
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.order-table__row:hover {
  background-color: var(--color-bg-subtle);
}

.order-table__row.is-highlighted {
  background-color: var(--color-accent-subtle);
}

.order-table__row.is-highlighted .order-table__cell {
  border-top-color: var(--color-accent-border);
}

.order-table__cell {
  padding: var(--primitive-space-4);
  color: var(--color-fg);
  vertical-align: top;
}

.order-table__cell--task {
  min-width: 16rem;
  max-width: 26rem;
}

.order-table__cell--nowrap {
  white-space: nowrap;
}

.order-table__cell--actions {
  white-space: nowrap;
}

.order-table__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.order-table__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-table__code {
  color: var(--obsidian-tertiary-text);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-code);
}

.order-table__party {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.order-table__party-name {
  overflow-wrap: anywhere;
}

.order-table__industry {
  color: var(--color-fg-muted);
}

.order-table__price {
  color: var(--obsidian-gold-text);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-body);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.order-table__status {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--primitive-space-1);
}

.order-table__hint {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  white-space: nowrap;
}

.order-table__logs {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-table__logs-count {
  color: var(--color-fg-strong);
  font-variant-numeric: tabular-nums;
  font-weight: var(--font-weight-medium);
}

.order-table__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.order-table__time {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
}
</style>
