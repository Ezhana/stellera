<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { z } from 'zod'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import PageHeader from '@/components/console/PageHeader.vue'
import OrderEmptyState from '@/components/orders/OrderEmptyState.vue'
import OrderStatusTabs from '@/components/orders/OrderStatusTabs.vue'
import OrderTable from '@/components/orders/OrderTable.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
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
const workLogContent = ref('')
const workLogHours = ref('')
const workLogError = ref('')
const workLogFieldError = ref('')
const submittingWorkLog = ref(false)

const deliveryOrder = ref<FdeOrderView | null>(null)
const deliveryMessage = ref('')
const deliveryError = ref('')
const submittingDelivery = ref(false)

const logSchema = z.object({
  content: z
    .string()
    .trim()
    .min(1, '请输入工作日志内容')
    .max(4000, '工作日志内容不能超过 4000 个字符'),
  hours: z
    .string()
    .trim()
    .refine((value) => value === '' || /^\d+(\.\d{1,2})?$/.test(value), '工时需为 0–24 之间的数字')
    .transform((value) => (value === '' ? null : Number(value)))
    .refine((value) => value === null || (value >= 0 && value <= 24), '工时需在 0–24 小时之间'),
})

const deliverySchema = z.string().trim().max(500, '交付说明不能超过 500 个字符')

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

function clearActionState(): void {
  successMessage.value = ''
}

function openWorkLog(order: FdeOrderView): void {
  clearActionState()
  deliveryOrder.value = null
  workLogOrder.value = order
  workLogContent.value = ''
  workLogHours.value = ''
  workLogError.value = ''
  workLogFieldError.value = ''
}

function closeWorkLog(): void {
  workLogOrder.value = null
  workLogError.value = ''
  workLogFieldError.value = ''
}

async function submitWorkLog(): Promise<void> {
  if (!workLogOrder.value || submittingWorkLog.value) return

  workLogError.value = ''
  workLogFieldError.value = ''
  const parsed = logSchema.safeParse({ content: workLogContent.value, hours: workLogHours.value })
  if (!parsed.success) {
    const message = parsed.error.issues[0]?.message ?? '请输入工作日志内容'
    if (parsed.error.issues[0]?.path[0] === 'content') workLogFieldError.value = message
    else workLogError.value = message
    return
  }

  submittingWorkLog.value = true
  try {
    const order = workLogOrder.value
    await ordersBff.addWorkLog(order.id, {
      content: parsed.data.content,
      workedHours: parsed.data.hours,
    })
    successMessage.value = '工作日志已提交。'
    announcement.value = `已提交工作日志：${order.title}`
    closeWorkLog()
    await loadOrders(false)
  } catch (error) {
    workLogError.value = toErrorMessage(error, '工作日志提交失败，请稍后重试。')
  } finally {
    submittingWorkLog.value = false
  }
}

function openDelivery(order: FdeOrderView): void {
  clearActionState()
  workLogOrder.value = null
  deliveryOrder.value = order
  deliveryMessage.value = ''
  deliveryError.value = ''
}

function closeDelivery(): void {
  deliveryOrder.value = null
  deliveryError.value = ''
}

async function submitDelivery(): Promise<void> {
  if (!deliveryOrder.value || submittingDelivery.value) return

  deliveryError.value = ''
  const parsed = deliverySchema.safeParse(deliveryMessage.value)
  if (!parsed.success) {
    deliveryError.value = parsed.error.issues[0]?.message ?? '交付说明不能超过 500 个字符'
    return
  }

  submittingDelivery.value = true
  try {
    const order = deliveryOrder.value
    await ordersBff.applyForOrder(order.id, 'delivery', parsed.data)
    successMessage.value = '交付申请已提交，等待发布者审批。'
    announcement.value = `已申请交付：${order.title}`
    closeDelivery()
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

      <UiCard v-if="workLogOrder" padding="lg" class="assigned-form">
        <header class="assigned-form__header">
          <p class="hub-eyebrow">WORK LOG</p>
          <h2 class="assigned-form__title">提交工作日志 · {{ workLogOrder.title }}</h2>
        </header>

        <UiAlert
          v-if="workLogError"
          variant="error"
          title="提交失败"
          dismissible
          @close="workLogError = ''"
        >
          {{ workLogError }}
        </UiAlert>

        <form class="assigned-form__body" novalidate @submit.prevent="submitWorkLog">
          <div class="assigned-form__field">
            <label class="assigned-form__label" :for="`work-log-${workLogOrder.id}`">
              日志内容
            </label>
            <textarea
              :id="`work-log-${workLogOrder.id}`"
              v-model="workLogContent"
              class="assigned-form__textarea"
              rows="4"
              name="work-log-content"
              :maxlength="4000"
              :disabled="submittingWorkLog"
              placeholder="说明今天完成的交付内容与进展…"
            />
            <p v-if="workLogFieldError" class="assigned-form__error" role="alert">
              {{ workLogFieldError }}
            </p>
            <p v-else class="assigned-form__help">已输入 {{ workLogContent.length }} / 4000 字</p>
          </div>

          <div class="assigned-form__field">
            <label class="assigned-form__label" :for="`work-hours-${workLogOrder.id}`">
              工时 / 小时（可选）
            </label>
            <input
              :id="`work-hours-${workLogOrder.id}`"
              v-model="workLogHours"
              class="assigned-form__input"
              name="work-log-hours"
              inputmode="decimal"
              :disabled="submittingWorkLog"
              placeholder="0–24"
            />
          </div>

          <div class="assigned-form__actions">
            <UiButton type="submit" :loading="submittingWorkLog">提交日志</UiButton>
            <UiButton variant="ghost" :disabled="submittingWorkLog" @click="closeWorkLog">
              取消
            </UiButton>
          </div>
        </form>
      </UiCard>

      <UiCard v-if="deliveryOrder" padding="lg" class="assigned-form">
        <header class="assigned-form__header">
          <p class="hub-eyebrow">APPLY FOR DELIVERY</p>
          <h2 class="assigned-form__title">申请交付 · {{ deliveryOrder.title }}</h2>
          <p class="assigned-form__description">
            提交后由订单发布者确认交付，确认后托管资金将结算给工程师。
          </p>
        </header>

        <UiAlert
          v-if="deliveryError"
          variant="error"
          title="提交失败"
          dismissible
          @close="deliveryError = ''"
        >
          {{ deliveryError }}
        </UiAlert>

        <form class="assigned-form__body" novalidate @submit.prevent="submitDelivery">
          <div class="assigned-form__field">
            <label class="assigned-form__label" :for="`delivery-message-${deliveryOrder.id}`">
              交付说明（可选）
            </label>
            <textarea
              :id="`delivery-message-${deliveryOrder.id}`"
              v-model="deliveryMessage"
              class="assigned-form__textarea"
              rows="4"
              name="delivery-message"
              :maxlength="500"
              :disabled="submittingDelivery"
              placeholder="简要说明交付物与验收方式…"
            />
            <p class="assigned-form__help">已输入 {{ deliveryMessage.length }} / 500 字</p>
          </div>

          <div class="assigned-form__actions">
            <UiButton type="submit" :loading="submittingDelivery">提交交付申请</UiButton>
            <UiButton variant="ghost" :disabled="submittingDelivery" @click="closeDelivery">
              取消
            </UiButton>
          </div>
        </form>
      </UiCard>

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

.assigned-form {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.assigned-form__header {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
}

.assigned-form__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
}

.assigned-form__description {
  max-width: 62ch;
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.assigned-form__body {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.assigned-form__field {
  display: flex;
  flex-direction: column;
}

.assigned-form__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.assigned-form__input,
.assigned-form__textarea {
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.assigned-form__input {
  height: 44px;
  padding-top: 0;
  padding-bottom: 0;
}

.assigned-form__textarea {
  min-height: 110px;
  resize: vertical;
}

.assigned-form__input:focus-visible,
.assigned-form__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.assigned-form__error {
  margin-top: var(--primitive-space-1);
  color: var(--color-danger);
  font-size: var(--font-size-caption);
}

.assigned-form__help {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.assigned-form__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-3);
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
