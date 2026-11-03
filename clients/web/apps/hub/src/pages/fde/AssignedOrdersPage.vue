<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import PageHeader from '@/components/console/PageHeader.vue'
import DeliveryApplicationDrawer from '@/components/orders/DeliveryApplicationDrawer.vue'
import OrderEmptyState from '@/components/orders/OrderEmptyState.vue'
import OrderStatusTabs from '@/components/orders/OrderStatusTabs.vue'
import OrderTable from '@/components/orders/OrderTable.vue'
import WorkLogDrawer from '@/components/orders/WorkLogDrawer.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import { type FdeOrderStatus, type FdeOrderView, type OrderApplicationView } from '@/models'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const viewer = computed(() => auth.viewer)
const viewerId = computed(() => auth.viewer?.id ?? '')

const orders = ref<FdeOrderView[]>([])
const pendingDeliveryApplications = ref<OrderApplicationView[]>([])
const loading = ref(true)
const refreshing = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const announcement = ref('')
const statusFilter = ref<FdeOrderStatus | 'all'>('all')

const workLogOrder = ref<FdeOrderView | null>(null)
const workLogOpen = ref(false)
const workLogError = ref('')
const submittingWorkLog = ref(false)

const deliveryOrder = ref<FdeOrderView | null>(null)
const deliveryOpen = ref(false)
const deliveryError = ref('')
const submittingDelivery = ref(false)

const pendingDeliveryOrderIds = computed(
  () => new Set(pendingDeliveryApplications.value.map((application) => application.order.id)),
)

/** Map the BFF's stable error codes to page copy; the page never inspects HTTP statuses. */
function toErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof BffError)) return fallback

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return '当前账号没有操作该订单的权限。'
    case 'not-found':
      return '订单不存在或已被移除，请刷新后重试。'
    case 'conflict':
    case 'invalid-input':
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
    const filter = statusFilter.value === 'all' ? undefined : { status: statusFilter.value }
    const model = await ordersBff.listAssignedOrders(filter)
    orders.value = model.orders
  } catch (error) {
    errorMessage.value = toErrorMessage(error, '接单列表加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

/** My own pending delivery applications; orders with one already show a disabled action. */
async function loadPendingDeliveryApplications(): Promise<void> {
  try {
    const model = await ordersBff.listMyApplications({
      type: 'delivery',
      status: 'pending',
      pageSize: 100,
    })
    pendingDeliveryApplications.value = model.applications
  } catch {
    pendingDeliveryApplications.value = []
  }
}

async function refresh(): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await Promise.all([loadOrders(false), loadPendingDeliveryApplications()])
  } finally {
    refreshing.value = false
  }
}

function openWorkLog(order: FdeOrderView): void {
  successMessage.value = ''
  workLogError.value = ''
  workLogOrder.value = order
  workLogOpen.value = true
}

async function submitWorkLog(input: {
  content: string
  workedHours: number | null
}): Promise<void> {
  const order = workLogOrder.value
  if (!order || submittingWorkLog.value) return

  submittingWorkLog.value = true
  workLogError.value = ''
  try {
    await ordersBff.addWorkLog(order.id, input)
    successMessage.value = '工作日志已提交。'
    announcement.value = `已提交工作日志：${order.title}`
    workLogOpen.value = false
    workLogOrder.value = null
    await loadOrders(false)
  } catch (error) {
    workLogError.value = toErrorMessage(error, '工作日志提交失败，请稍后重试。')
  } finally {
    submittingWorkLog.value = false
  }
}

function openDelivery(order: FdeOrderView): void {
  successMessage.value = ''
  deliveryError.value = ''
  deliveryOrder.value = order
  deliveryOpen.value = true
}

async function submitDelivery(message: string): Promise<void> {
  const order = deliveryOrder.value
  if (!order || submittingDelivery.value) return

  submittingDelivery.value = true
  deliveryError.value = ''
  try {
    await ordersBff.applyForOrder(order.id, 'delivery', message)
    successMessage.value = '交付申请已提交，等待发布者审批。'
    announcement.value = `已申请交付：${order.title}`
    deliveryOpen.value = false
    deliveryOrder.value = null
    await Promise.all([loadOrders(false), loadPendingDeliveryApplications()])
  } catch (error) {
    deliveryError.value = toErrorMessage(error, '交付申请提交失败，请稍后重试。')
  } finally {
    submittingDelivery.value = false
  }
}

watch(statusFilter, () => {
  void loadOrders(false)
})

onMounted(async () => {
  await Promise.all([loadOrders(), loadPendingDeliveryApplications()])
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="assigned-page">
      <PageHeader
        eyebrow="ASSIGNED ORDERS"
        title="我接到的"
        description="查看审批通过后由我交付的订单，提交工作日志并申请交付。"
      >
        <template #actions>
          <UiButton variant="secondary" size="sm" :loading="refreshing" @click="refresh">
            <UiIcon name="refresh" :size="16" />
            刷新
          </UiButton>
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

      <WorkLogDrawer
        v-model:open="workLogOpen"
        :order="workLogOrder"
        :submitting="submittingWorkLog"
        :error="workLogError"
        @submit="submitWorkLog"
      />

      <DeliveryApplicationDrawer
        v-model:open="deliveryOpen"
        :order="deliveryOrder"
        :submitting="submittingDelivery"
        :error="deliveryError"
        @submit="submitDelivery"
      />

      <section class="assigned-panel" :aria-busy="loading ? 'true' : 'false'">
        <div class="assigned-panel__toolbar">
          <OrderStatusTabs v-model="statusFilter" />
          <span class="assigned-panel__result">共 {{ orders.length }} 条订单</span>
        </div>

        <div v-if="loading" class="assigned-panel__state" role="status" aria-live="polite">
          <span class="assigned-panel__spinner" aria-hidden="true" />
          正在加载接单…
        </div>

        <div v-else-if="errorMessage" class="assigned-panel__error">
          <UiAlert variant="error" title="接单加载失败">{{ errorMessage }}</UiAlert>
          <UiButton variant="secondary" size="sm" @click="refresh">重试</UiButton>
        </div>

        <OrderEmptyState
          v-else-if="orders.length === 0"
          title="暂时没有接到的订单"
          description="发布者对您的接单申请审批通过后，订单会出现在这里。"
          icon="wrench"
        />

        <OrderTable v-else :orders="orders" :viewer-id="viewerId" caption="我接到的订单列表">
          <template #actions="{ order }">
            <template v-if="order.status === 'in_progress'">
              <UiButton size="sm" variant="secondary" @click="openWorkLog(order)">
                提交工作日志
              </UiButton>
              <UiButton
                v-if="pendingDeliveryOrderIds.has(order.id)"
                size="sm"
                variant="secondary"
                disabled
              >
                交付申请待审批
              </UiButton>
              <UiButton v-else size="sm" @click="openDelivery(order)">申请交付</UiButton>
            </template>
            <span v-else class="assigned-panel__action-hint">—</span>
          </template>
        </OrderTable>
      </section>
    </div>
  </ConsoleLayout>
</template>

<style scoped>
.assigned-page {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.assigned-panel {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
  padding: var(--primitive-space-5);
  background-color: var(--color-surface);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-surface);
  box-shadow: var(--obsidian-panel-highlight);
}

.assigned-panel__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.assigned-panel__result {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.assigned-panel__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.assigned-panel__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: var(--radius-pill);
  animation: assigned-panel-spin 0.9s linear infinite;
}

.assigned-panel__error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--primitive-space-3);
}

.assigned-panel__action-hint {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);

  white-space: nowrap;
}

@keyframes assigned-panel-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
