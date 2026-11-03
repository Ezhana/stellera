<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { BffError } from '@/bff/errors'
import { ordersBff, summarizeOrders, upsertOrder } from '@/bff/orders'
import type { OrderRealtimeConnection, OrderRealtimeState } from '@/bff/orders'
import PageHeader from '@/components/console/PageHeader.vue'
import LiveStatus from '@/components/orders/LiveStatus.vue'
import OrderEmptyState from '@/components/orders/OrderEmptyState.vue'
import OrderStatsGrid from '@/components/orders/OrderStatsGrid.vue'
import OrderStatusTabs from '@/components/orders/OrderStatusTabs.vue'
import OrderTable from '@/components/orders/OrderTable.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import { FDE_INDUSTRIES, type FdeOrderStatus, type FdeOrderView } from '@/models'
import type { OrderApplicationView } from '@/models'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const viewer = computed(() => auth.viewer)
const viewerId = computed(() => auth.viewer?.id ?? '')

const orders = ref<FdeOrderView[]>([])
const myPendingApplications = ref<OrderApplicationView[]>([])
const loading = ref(true)
const refreshing = ref(false)
const applyingOrderId = ref<string | null>(null)
const errorMessage = ref('')
const successMessage = ref('')
const statusFilter = ref<FdeOrderStatus | 'all'>('all')
const industryFilter = ref('')
const keyword = ref('')
const realtimeState = ref<OrderRealtimeState>('connecting')
const lastEventLabel = ref('')
const announcement = ref('')
const highlightedId = ref<string | null>(null)

let connection: OrderRealtimeConnection | null = null
let highlightTimer: ReturnType<typeof setTimeout> | null = null

const stats = computed(() => summarizeOrders(orders.value))
const liveHint = computed(() => lastEventLabel.value || '刚刚已同步')

/** Orders already carrying one of my pending accept applications; their button is disabled. */
const pendingAcceptOrderIds = computed(
  () => new Set(myPendingApplications.value.map((application) => application.order.id)),
)

/** The hall loads one page of orders and filters client-side, so realtime upserts stay visible. */
const filteredOrders = computed(() => {
  const needle = keyword.value.trim().toLowerCase()

  return orders.value.filter((order) => {
    if (statusFilter.value !== 'all' && order.status !== statusFilter.value) return false
    if (industryFilter.value && order.industry !== industryFilter.value) return false
    if (needle) {
      const haystack =
        `${order.title} ${order.code} ${order.publisherName} ${order.industry} ${order.description}`.toLowerCase()
      if (!haystack.includes(needle)) return false
    }
    return true
  })
})

/** Map the BFF's stable error codes to hall copy; the page never inspects HTTP statuses. */
function toErrorMessage(error: unknown): string {
  if (!(error instanceof BffError)) return '订单加载失败，请稍后重试。'

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return '当前账号没有查看订单的权限。'
    case 'network':
      return '无法连接到服务，请检查网络后重试。'
    case 'server':
      return '订单服务暂时不可用，请稍后再试。'
    case 'malformed-response':
      return '服务返回的数据格式异常，请联系管理员。'
    case 'conflict':
    case 'invalid-input':
      return error.message || '当前操作与订单状态冲突，请刷新后重试。'
    case 'not-found':
      return '订单不存在或已被移除，请刷新后重试。'
    default:
      return error.message || '订单加载失败，请稍后重试。'
  }
}

async function loadOrders(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  errorMessage.value = ''

  try {
    const model = await ordersBff.listOrders()
    orders.value = model.orders
  } catch (error) {
    errorMessage.value = toErrorMessage(error)
  } finally {
    loading.value = false
  }
}

/** Load my pending accept applications so the hall can mark already-applied orders. */
async function loadMyPendingApplications(): Promise<void> {
  try {
    const model = await ordersBff.listMyApplications({
      type: 'accept',
      status: 'pending',
      pageSize: 100,
    })
    myPendingApplications.value = model.applications
  } catch {
    // Applications are an enhancement: a failed lookup must never break the hall list.
    myPendingApplications.value = []
  }
}

async function applyForOrder(order: FdeOrderView): Promise<void> {
  if (applyingOrderId.value) return
  applyingOrderId.value = order.id
  successMessage.value = ''
  errorMessage.value = ''

  try {
    await ordersBff.applyForOrder(order.id, 'accept')
    successMessage.value = '申请已提交，等待发布者审批。'
    announcement.value = `已申请接单：${order.title}`
    await Promise.all([loadOrders(false), loadMyPendingApplications()])
  } catch (error) {
    errorMessage.value = toErrorMessage(error)
  } finally {
    applyingOrderId.value = null
  }
}

function canApply(order: FdeOrderView): boolean {
  return (
    order.status === 'open' &&
    order.publisherId !== viewerId.value &&
    !pendingAcceptOrderIds.value.has(order.id)
  )
}

async function refresh(): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await Promise.all([loadOrders(false), loadMyPendingApplications()])
  } finally {
    refreshing.value = false
  }
}

function highlightRow(orderId: string): void {
  highlightedId.value = orderId
  if (highlightTimer) clearTimeout(highlightTimer)
  highlightTimer = setTimeout(() => {
    highlightedId.value = null
    highlightTimer = null
  }, 2_000)
}

function connectRealtime(): void {
  try {
    connection = ordersBff.connectRealtime({
      onStateChange(state) {
        realtimeState.value = state
      },
      onEvent(event) {
        if (event.type === 'connected') return

        const existed = orders.value.some((order) => order.id === event.order.id)
        orders.value = upsertOrder(orders.value, event.order)

        const label = `${existed ? '订单更新' : '新订单'} · ${event.order.title}`
        lastEventLabel.value = label
        announcement.value = label
        highlightRow(event.order.id)
      },
    })
  } catch {
    // Realtime is an enhancement: a failed feed must never break the list.
    realtimeState.value = 'offline'
  }
}

onMounted(async () => {
  await Promise.all([loadOrders(), loadMyPendingApplications()])
  connectRealtime()
})

onBeforeUnmount(() => {
  connection?.close()
  connection = null
  if (highlightTimer) {
    clearTimeout(highlightTimer)
    highlightTimer = null
  }
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="order-page">
      <PageHeader
        eyebrow="FDE ORDER HALL"
        title="订单大厅"
        description="企业发布需求、工程师接单交付，平台托管资金并保障履约。"
      >
        <template #actions>
          <LiveStatus :state="realtimeState" :last-event-label="lastEventLabel || undefined" />
          <RouterLink class="order-page__link-button" :to="{ name: 'fde-published' }">
            我发布的
            <UiIcon name="arrow-right" :size="16" />
          </RouterLink>
        </template>
      </PageHeader>

      <p class="visually-hidden" role="status" aria-live="polite">{{ announcement }}</p>

      <UiAlert
        v-if="successMessage"
        variant="success"
        title="申请已提交"
        dismissible
        @close="successMessage = ''"
      >
        {{ successMessage }}
      </UiAlert>

      <OrderStatsGrid :stats="stats" total-label="订单总数" />

      <section class="order-page__panel" :aria-busy="loading ? 'true' : 'false'">
        <div class="order-page__toolbar">
          <OrderStatusTabs v-model="statusFilter" />

          <div class="order-page__filters">
            <label class="order-page__select-field" for="hall-industry">
              <span class="order-page__select-label">行业</span>
              <select id="hall-industry" v-model="industryFilter" class="order-page__select">
                <option value="">全部行业</option>
                <option v-for="industry in FDE_INDUSTRIES" :key="industry" :value="industry">
                  {{ industry }}
                </option>
              </select>
            </label>

            <UiInput
              v-model="keyword"
              class="order-page__search"
              type="search"
              placeholder="搜索任务、编号或发布方"
              aria-label="搜索订单"
            />

            <UiButton variant="secondary" size="sm" :loading="refreshing" @click="refresh">
              <UiIcon name="refresh" :size="16" />
              刷新
            </UiButton>
          </div>
        </div>

        <p class="order-page__result">
          <span>共 {{ orders.length }} 条订单</span>
          <span v-if="filteredOrders.length !== orders.length">
            · 当前筛选 {{ filteredOrders.length }} 条
          </span>
          <span v-if="realtimeState === 'live'" class="order-page__result-live">
            实时更新 · {{ liveHint }}
          </span>
        </p>

        <div v-if="loading" class="order-page__state" role="status" aria-live="polite">
          <span class="order-page__spinner" aria-hidden="true" />
          正在加载订单…
        </div>

        <div v-else-if="errorMessage" class="order-page__error">
          <UiAlert variant="error" title="订单加载失败">{{ errorMessage }}</UiAlert>
          <UiButton variant="secondary" size="sm" @click="refresh">重试</UiButton>
        </div>

        <OrderEmptyState
          v-else-if="filteredOrders.length === 0"
          :title="orders.length === 0 ? '暂无可接订单' : '没有符合筛选条件的订单'"
          :description="
            orders.length === 0
              ? '订单大厅还没有开放需求。发布第一条需求，工程师会在这里接单。'
              : '试试调整状态、行业或搜索关键词。'
          "
        >
          <template #action>
            <RouterLink class="order-page__link-button" :to="{ name: 'fde-published' }">
              前往我发布的
            </RouterLink>
          </template>
        </OrderEmptyState>

        <OrderTable
          v-else
          :orders="filteredOrders"
          :viewer-id="viewerId"
          caption="订单大厅实时订单列表"
          :highlighted-id="highlightedId"
        >
          <template #actions="{ order }">
            <template v-if="order.publisherId === viewerId">
              <span class="order-page__action-hint">我发布的</span>
            </template>
            <template v-else-if="order.status === 'open'">
              <UiButton
                v-if="canApply(order)"
                size="sm"
                :loading="applyingOrderId === order.id"
                @click="applyForOrder(order)"
              >
                申请接单
              </UiButton>
              <UiButton v-else size="sm" variant="secondary" disabled>已申请</UiButton>
            </template>
            <span v-else class="order-page__action-hint">—</span>
          </template>
        </OrderTable>
      </section>
    </div>
  </ConsoleLayout>
</template>

<style scoped>
.order-page {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.order-page__link-button {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
  min-height: 44px;
  padding: 0 var(--primitive-space-5);
  color: var(--color-fg);
  background: var(--obsidian-surface-glass);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
  transition: border-color var(--motion-duration-fast) var(--motion-easing-standard);
}

.order-page__link-button:hover {
  border-color: var(--color-accent);
  text-decoration: none;
}

.order-page__panel {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
  padding: var(--primitive-space-5);
  background-color: var(--color-surface);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-surface);
  box-shadow: var(--obsidian-panel-highlight);
}

.order-page__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.order-page__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-3);
}

.order-page__select-field {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
}

.order-page__select-label {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}

.order-page__select {
  height: 40px;
  padding: 0 var(--primitive-space-3);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
}

.order-page__select:focus-visible {
  border-color: var(--color-accent);
}

.order-page__select option {
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
}

.order-page__search {
  width: 17rem;
  max-width: 100%;
}

.order-page__result {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-page__result-live {
  color: var(--obsidian-tertiary-text);
}

.order-page__result-live::before {
  content: '·';
  margin-right: var(--primitive-space-2);
}

.order-page__action-hint {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  white-space: nowrap;
}

.order-page__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.order-page__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: var(--radius-pill);
  animation: order-page-spin 0.9s linear infinite;
}

.order-page__error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--primitive-space-3);
}

@keyframes order-page-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 900px) {
  .order-page__search {
    width: 100%;
  }

  .order-page__toolbar,
  .order-page__filters {
    align-items: stretch;
  }
}
</style>
