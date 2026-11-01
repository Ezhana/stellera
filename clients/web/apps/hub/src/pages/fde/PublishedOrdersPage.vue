<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { z } from 'zod'

import { BffError } from '@/bff/errors'
import { ordersBff, summarizeOrders, upsertOrder } from '@/bff/orders'
import type { CreateOrderInput, OrderRealtimeConnection, OrderRealtimeState } from '@/bff/orders'
import PageHeader from '@/components/console/PageHeader.vue'
import LiveStatus from '@/components/orders/LiveStatus.vue'
import OrderEmptyState from '@/components/orders/OrderEmptyState.vue'
import OrderStatsGrid from '@/components/orders/OrderStatsGrid.vue'
import OrderStatusTabs from '@/components/orders/OrderStatusTabs.vue'
import OrderTable from '@/components/orders/OrderTable.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import { FDE_INDUSTRIES, type FdeOrderStatus, type FdeOrderView } from '@/models'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const viewer = computed(() => auth.viewer)
const viewerId = computed(() => auth.viewer?.id ?? '')
const canPublish = computed(() => auth.viewer?.capabilities.publishOrder ?? false)

const orders = ref<FdeOrderView[]>([])
const loading = ref(true)
const refreshing = ref(false)
const errorMessage = ref('')
const statusFilter = ref<FdeOrderStatus | 'all'>('all')
const realtimeState = ref<OrderRealtimeState>('connecting')
const lastEventLabel = ref('')
const announcement = ref('')
const highlightedId = ref<string | null>(null)

const formOpen = ref(false)
const submitting = ref(false)
const successMessage = ref('')
const formError = ref('')

const title = ref('')
const industry = ref('')
const deliveryDays = ref('')
const priceYuan = ref('')
const description = ref('')

interface FormFieldErrors {
  title?: string
  industry?: string
  deliveryDays?: string
  priceYuan?: string
  description?: string
}

const FORM_FIELDS = ['title', 'industry', 'deliveryDays', 'priceYuan', 'description'] as const
type FormField = (typeof FORM_FIELDS)[number]

const fieldErrors = reactive<FormFieldErrors>({})

let connection: OrderRealtimeConnection | null = null
let highlightTimer: ReturnType<typeof setTimeout> | null = null

const publishSchema = z.object({
  title: z.string().trim().min(1, '请输入任务标题').max(120, '任务标题长度不能超过 120 个字符'),
  industry: z.string().min(1, '请选择行业'),
  deliveryDays: z
    .string()
    .trim()
    .min(1, '请输入交付周期')
    .refine((value) => /^\d+$/.test(value), '交付周期需为整数天数')
    .transform((value) => Number(value))
    .refine((value) => value >= 1 && value <= 365, '交付周期需在 1–365 天之间'),
  priceYuan: z
    .string()
    .trim()
    .min(1, '请输入预算金额')
    .refine((value) => /^\d+(\.\d{1,2})?$/.test(value), '预算金额最多保留两位小数')
    .transform((value) => Number(value))
    .refine((value) => value > 0, '预算金额必须大于 0')
    .refine((value) => value <= 10_000_000, '预算金额不能超过 10,000,000 元'),
  description: z
    .string()
    .trim()
    .min(1, '请填写需求描述')
    .max(4000, '需求描述长度不能超过 4000 个字符'),
})

const stats = computed(() => summarizeOrders(orders.value))
const liveHint = computed(() => lastEventLabel.value || '刚刚已同步')
const filteredOrders = computed(() =>
  statusFilter.value === 'all'
    ? orders.value
    : orders.value.filter((order) => order.status === statusFilter.value),
)

/** Map the BFF's stable error codes to page copy; the page never inspects HTTP statuses. */
function toErrorMessage(error: unknown, scope: 'load' | 'publish'): string {
  const fallback = scope === 'load' ? '需求加载失败，请稍后重试。' : '发布失败，请稍后重试。'
  if (!(error instanceof BffError)) return fallback

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return scope === 'load'
        ? '当前账号没有查看需求的权限。'
        : '当前账号没有发布需求的权限，请联系管理员。'
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

async function refresh(): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await loadOrders(false)
  } finally {
    refreshing.value = false
  }
}

function clearFieldErrors(): void {
  for (const field of FORM_FIELDS) fieldErrors[field] = undefined
}

/** Validate the inline form and convert yuan into integer cents for the BFF. */
function parseForm(): CreateOrderInput | null {
  clearFieldErrors()

  const result = publishSchema.safeParse({
    title: title.value,
    industry: industry.value,
    deliveryDays: deliveryDays.value,
    priceYuan: priceYuan.value,
    description: description.value,
  })

  if (!result.success) {
    for (const issue of result.error.issues) {
      const field = issue.path[0]
      if (typeof field !== 'string' || !(FORM_FIELDS as readonly string[]).includes(field)) continue
      if (!fieldErrors[field as FormField]) fieldErrors[field as FormField] = issue.message
    }
    return null
  }

  return {
    title: result.data.title,
    industry: result.data.industry,
    description: result.data.description,
    deliveryDays: result.data.deliveryDays,
    priceCents: Math.round(result.data.priceYuan * 100),
  }
}

function resetForm(): void {
  title.value = ''
  industry.value = ''
  deliveryDays.value = ''
  priceYuan.value = ''
  description.value = ''
  clearFieldErrors()
}

function openForm(): void {
  successMessage.value = ''
  formError.value = ''
  formOpen.value = true
}

function closeForm(): void {
  formOpen.value = false
  formError.value = ''
  resetForm()
}

function toggleForm(): void {
  if (formOpen.value) closeForm()
  else openForm()
}

async function handlePublish(): Promise<void> {
  if (submitting.value) return

  formError.value = ''
  successMessage.value = ''
  const input = parseForm()
  if (!input) return

  submitting.value = true
  try {
    const order = await ordersBff.createOrder(input)
    orders.value = upsertOrder(orders.value, order)
    resetForm()
    formOpen.value = false
    successMessage.value = '需求已发布并进入订单大厅，资金已进入平台托管。'
    announcement.value = `已发布需求：${order.title}`
    highlightRow(order.id)
  } catch (error) {
    formError.value = toErrorMessage(error, 'publish')
  } finally {
    submitting.value = false
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
  await loadOrders()
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
          <UiButton v-if="canPublish" variant="secondary" @click="toggleForm">
            {{ formOpen ? '收起表单' : '发布需求' }}
          </UiButton>
          <LiveStatus :state="realtimeState" :last-event-label="lastEventLabel || undefined" />
        </template>
      </PageHeader>

      <p class="visually-hidden" role="status" aria-live="polite">{{ announcement }}</p>

      <UiAlert
        v-if="successMessage"
        variant="success"
        title="发布成功"
        dismissible
        @close="successMessage = ''"
      >
        {{ successMessage }}
      </UiAlert>

      <UiAlert v-if="!canPublish" variant="info" title="无发布权限">
        当前账号可以浏览已发布需求；发布需求需要企业或管理员账号，请联系管理员开通权限。
      </UiAlert>

      <UiCard v-if="formOpen && canPublish" elevated padding="lg" class="publish-form">
        <header class="publish-form__header">
          <p class="hub-eyebrow">PUBLISH ORDER</p>
          <h2 class="publish-form__title">发布新需求</h2>
          <p class="publish-form__description">
            需求发布后立即进入订单大厅，预算会进入平台托管，交付完成后结算。
          </p>
        </header>

        <UiAlert
          v-if="formError"
          variant="error"
          title="发布失败"
          dismissible
          @close="formError = ''"
        >
          {{ formError }}
        </UiAlert>

        <form class="publish-form__grid" novalidate @submit.prevent="handlePublish">
          <UiInput
            v-model="title"
            label="任务标题"
            name="title"
            :maxlength="120"
            placeholder="例如：医疗影像数据标注与质检"
            :error="fieldErrors.title"
            :disabled="submitting"
          />

          <div class="publish-form__field">
            <label class="publish-form__label" for="publish-industry">行业</label>
            <select
              id="publish-industry"
              v-model="industry"
              class="publish-form__select"
              :disabled="submitting"
            >
              <option value="" disabled>请选择行业</option>
              <option v-for="item in FDE_INDUSTRIES" :key="item" :value="item">{{ item }}</option>
            </select>
            <p v-if="fieldErrors.industry" class="publish-form__error" role="alert">
              {{ fieldErrors.industry }}
            </p>
          </div>

          <UiInput
            v-model="deliveryDays"
            label="交付周期 / 天"
            name="deliveryDays"
            inputmode="numeric"
            placeholder="7"
            :error="fieldErrors.deliveryDays"
            :disabled="submitting"
          />

          <UiInput
            v-model="priceYuan"
            label="预算 / 元"
            name="priceYuan"
            inputmode="decimal"
            placeholder="86000"
            :error="fieldErrors.priceYuan"
            :disabled="submitting"
          />

          <div class="publish-form__field publish-form__field--wide">
            <label class="publish-form__label" for="publish-description">需求描述</label>
            <textarea
              id="publish-description"
              v-model="description"
              class="publish-form__textarea"
              rows="5"
              :maxlength="4000"
              :disabled="submitting"
              placeholder="说明目标、交付物与验收标准…"
            />
            <p v-if="fieldErrors.description" class="publish-form__error" role="alert">
              {{ fieldErrors.description }}
            </p>
            <p v-else class="publish-form__help">已输入 {{ description.length }} / 4000 字</p>
          </div>

          <div class="publish-form__actions publish-form__field--wide">
            <UiButton type="submit" :loading="submitting">发布需求</UiButton>
            <UiButton variant="ghost" :disabled="submitting" @click="closeForm">取消</UiButton>
          </div>
        </form>
      </UiCard>

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
            <UiButton v-if="canPublish" variant="secondary" @click="openForm">
              发布第一条需求
            </UiButton>
          </template>
        </OrderEmptyState>

        <OrderTable
          v-else
          :orders="filteredOrders"
          :viewer-id="viewerId"
          caption="我发布的订单列表"
          show-work-log
          :highlighted-id="highlightedId"
        />
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

.publish-form {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-5);
}

.publish-form__header {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
}

.publish-form__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-medium);
}

.publish-form__description {
  max-width: 60ch;
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.publish-form__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.publish-form__field {
  display: flex;
  flex-direction: column;
}

.publish-form__field--wide {
  grid-column: 1 / -1;
}

.publish-form__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.publish-form__select {
  height: 44px;
  padding: 0 var(--primitive-space-4);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  transition: border-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.publish-form__select:hover:not(:disabled) {
  border-color: var(--color-accent-border);
}

.publish-form__select:focus-visible {
  border-color: var(--color-accent);
}

.publish-form__select option {
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
}

.publish-form__textarea {
  min-height: 128px;
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  line-height: 1.6;
  resize: vertical;
  transition: border-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.publish-form__textarea::placeholder {
  color: var(--color-fg-muted);
}

.publish-form__textarea:hover:not(:disabled) {
  border-color: var(--color-accent-border);
}

.publish-form__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.publish-form__textarea:disabled {
  color: var(--color-fg-muted);
  background-color: var(--color-bg);
  cursor: not-allowed;
}

.publish-form__error {
  margin-top: var(--primitive-space-1);
  color: var(--color-danger);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}

.publish-form__help {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}

.publish-form__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-3);
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

@media (max-width: 760px) {
  .publish-form__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
