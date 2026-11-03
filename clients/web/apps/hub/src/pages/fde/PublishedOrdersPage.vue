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
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import type { FdeOrderStatus, FdeOrderView } from '@/models'
import type { OrderApplicationView } from '@/models'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const viewer = computed(() => auth.viewer)
const viewerId = computed(() => auth.viewer?.id ?? '')

const orders = ref<FdeOrderView[]>([])
const receivedApplications = ref<OrderApplicationView[]>([])
const loading = ref(true)
const refreshing = ref(false)
const errorMessage = ref('')
const actionError = ref('')
const successMessage = ref('')
const statusFilter = ref<FdeOrderStatus | 'all'>('all')
const realtimeState = ref<OrderRealtimeState>('connecting')
const lastEventLabel = ref('')
const announcement = ref('')
const highlightedId = ref<string | null>(null)
const confirmingCancelId = ref<string | null>(null)
const cancellingOrderId = ref<string | null>(null)
const approvingOrderId = ref<string | null>(null)
let connection: OrderRealtimeConnection | null = null
let highlightTimer: ReturnType<typeof setTimeout> | null = null

const stats = computed(() => summarizeOrders(orders.value))
const liveHint = computed(() => lastEventLabel.value || '刚刚已同步')
const filteredOrders = computed(() =>
  statusFilter.value === 'all'
    ? orders.value
    : orders.value.filter((order) => order.status === statusFilter.value),
)

/** Group received pending applications by order so row actions can read them cheaply. */
const pendingApplicationsByOrder = computed(() => {
  const map = new Map<string, OrderApplicationView[]>()
  for (const application of receivedApplications.value) {
    if (application.status !== 'pending') continue
    const list = map.get(application.order.id) ?? []
    list.push(application)
    map.set(application.order.id, list)
  }
  return map
})

function pendingApplications(
  order: FdeOrderView,
  type: 'accept' | 'delivery',
): OrderApplicationView[] {
  return (pendingApplicationsByOrder.value.get(order.id) ?? []).filter(
    (application) => application.type === type,
  )
}

/** Map the BFF's stable error codes to page copy; the page never inspects HTTP statuses. */
function toErrorMessage(error: unknown, scope: 'load' | 'action'): string {
  const fallback = scope === 'load' ? '需求加载失败，请稍后重试。' : '操作失败，请稍后重试。'
  if (!(error instanceof BffError)) return fallback

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return scope === 'load' ? '当前账号没有查看需求的权限。' : '当前账号没有操作该订单的权限。'
    case 'not-found':
      return '订单不存在或已被移除，请刷新后重试。'
    case 'invalid-input':
      return error.message || '提交的内容不符合要求，请检查后重试。'
    case 'conflict':
      return error.message || '当前操作与订单状态冲突，请刷新后重试。'
    case 'network':
      return '无法连接到服务，请检查网络后重试。'
    case 'server':
      return '订单服务暂时不可用，请稍后再试。'
    case 'malformed-response':
      return '服务返回的数据格式异常，请联系管理员。'
    default:
      return error.message || fallback
  }
}

async function loadOrders(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  errorMessage.value = ''

  try {
    const model = await ordersBff.listMyOrders()
    orders.value = model.orders
  } catch (error) {
    errorMessage.value = toErrorMessage(error, 'load')
  } finally {
    loading.value = false
  }
}

/** Load every pending application received on my published orders. */
async function loadReceivedApplications(): Promise<void> {
  try {
    const model = await ordersBff.listReceivedApplications({ status: 'pending', pageSize: 100 })
    receivedApplications.value = model.applications
  } catch {
    receivedApplications.value = []
  }
}

async function refresh(): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await Promise.all([loadOrders(false), loadReceivedApplications()])
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

/** First click arms the confirmation, the second click actually cancels the order. */
function requestCancel(order: FdeOrderView): void {
  if (confirmingCancelId.value === order.id) {
    void cancelOrder(order)
    return
  }
  actionError.value = ''
  confirmingCancelId.value = order.id
}

async function cancelOrder(order: FdeOrderView): Promise<void> {
  if (cancellingOrderId.value) return
  cancellingOrderId.value = order.id
  actionError.value = ''
  successMessage.value = ''

  try {
    const updated = await ordersBff.cancelOrder(order.id)
    orders.value = upsertOrder(orders.value, updated)
    confirmingCancelId.value = null
    successMessage.value = '订单已取消，托管资金已退回。'
    announcement.value = `已取消订单：${order.title}`
  } catch (error) {
    actionError.value = toErrorMessage(error, 'action')
  } finally {
    cancellingOrderId.value = null
  }
}

/** Confirm the latest pending delivery application for one of my in-progress orders. */
async function approveDelivery(order: FdeOrderView): Promise<void> {
  if (approvingOrderId.value) return
  const application = pendingApplications(order, 'delivery')[0]
  if (!application) return

  approvingOrderId.value = order.id
  actionError.value = ''
  successMessage.value = ''

  try {
    await ordersBff.approveApplication(application.id)
    successMessage.value = '已确认交付，托管资金已结算给工程师。'
    announcement.value = `已确认交付：${order.title}`
    await Promise.all([loadOrders(false), loadReceivedApplications()])
  } catch (error) {
    actionError.value = toErrorMessage(error, 'action')
  } finally {
    approvingOrderId.value = null
  }
}

function connectRealtime(): void {
  try {
    connection = ordersBff.connectRealtime({
      onStateChange(state) {
        realtimeState.value = state
      },
      onEvent(event) {
        if (event.type === 'connected') return

        const tracked = orders.value.some((order) => order.id === event.order.id)
        const mine = event.order.publisherId === viewerId.value
        // The published list only cares about my own orders changing state.
        if (!tracked && !mine) return

        orders.value = upsertOrder(orders.value, event.order)

        const label = `${tracked ? '订单更新' : '新订单'} · ${event.order.title}`
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
  await Promise.all([loadOrders(), loadReceivedApplications()])
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
        eyebrow="MY PUBLISHED ORDERS"
        title="我发布的"
        description="查看当前发布的需求、托管状态与交付进度。"
      >
        <template #actions>
          <RouterLink class="order-page__link-button" :to="{ name: 'fde-hall' }">
            <UiIcon name="arrow-left" :size="16" />
            返回订单大厅
          </RouterLink>
          <RouterLink class="order-page__link-button" :to="{ name: 'fde-publish' }">
            <UiIcon name="plus" :size="16" />
            发布需求
          </RouterLink>
          <LiveStatus :state="realtimeState" :last-event-label="lastEventLabel || undefined" />
        </template>
      </PageHeader>

      <p class="visually-hidden" role="status" aria-live="polite">{{ announcement }}</p>

      <UiAlert
        v-if="successMessage"
        variant="success"
        title="操作成功"
        dismissible
        @close="successMessage = ''"
      >
        {{ successMessage }}
      </UiAlert>

      <UiAlert
        v-if="actionError"
        variant="error"
        title="操作失败"
        dismissible
        @close="actionError = ''"
      >
        {{ actionError }}
      </UiAlert>

      <OrderStatsGrid :stats="stats" total-label="我的订单" />

      <section class="order-page__panel" :aria-busy="loading ? 'true' : 'false'">
        <div class="order-page__toolbar">
          <OrderStatusTabs v-model="statusFilter" />

          <div class="order-page__toolbar-actions">
            <span class="order-page__result">
              共 {{ orders.length }} 条 · 当前显示 {{ filteredOrders.length }} 条
            </span>
            <UiButton variant="secondary" size="sm" :loading="refreshing" @click="refresh">
              <UiIcon name="refresh" :size="16" />
              刷新
            </UiButton>
          </div>
        </div>

        <div v-if="loading" class="order-page__state" role="status" aria-live="polite">
          <span class="order-page__spinner" aria-hidden="true" />
          正在加载需求…
        </div>

        <div v-else-if="errorMessage" class="order-page__error">
          <UiAlert variant="error" title="需求加载失败">{{ errorMessage }}</UiAlert>
          <UiButton variant="secondary" size="sm" @click="refresh">重试</UiButton>
        </div>

        <OrderEmptyState
          v-else-if="filteredOrders.length === 0"
          :title="orders.length === 0 ? '还没有发布过需求' : '没有符合筛选条件的需求'"
          :description="
            orders.length === 0
              ? '发布第一条需求，工程师将在订单大厅接单并交付。'
              : '试试切换状态筛选查看其他需求。'
          "
        >
          <template #action>
            <RouterLink class="order-page__link-button" :to="{ name: 'fde-publish' }">
              发布第一条需求
            </RouterLink>
          </template>
        </OrderEmptyState>

        <OrderTable
          v-else
          :orders="filteredOrders"
          :viewer-id="viewerId"
          caption="我发布的订单列表"
          show-work-log
          :highlighted-id="highlightedId"
        >
          <template #actions="{ order }">
            <template v-if="order.status === 'open'">
              <RouterLink
                v-if="pendingApplications(order, 'accept').length"
                class="order-page__link-button order-page__link-button--inline"
                :to="{ name: 'fde-applications', query: { tab: 'received' } }"
              >
                {{ pendingApplications(order, 'accept').length }} 条接单申请
              </RouterLink>
              <UiButton
                variant="ghost"
                size="sm"
                :loading="cancellingOrderId === order.id"
                @click="requestCancel(order)"
              >
                {{ confirmingCancelId === order.id ? '确认取消' : '取消订单' }}
              </UiButton>
            </template>
            <template v-else-if="order.status === 'in_progress'">
              <UiButton
                v-if="pendingApplications(order, 'delivery').length"
                size="sm"
                :loading="approvingOrderId === order.id"
                @click="approveDelivery(order)"
              >
                确认交付
              </UiButton>
              <span v-else class="order-page__action-hint">等待交付申请</span>
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

.order-page__toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-3);
}

.order-page__result {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-page__link-button--inline {
  min-height: 36px;
  padding: 0 var(--primitive-space-3);
  font-size: var(--font-size-caption);
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
</style>
