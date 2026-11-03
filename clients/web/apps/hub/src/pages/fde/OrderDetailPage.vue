<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import { profileBff } from '@/bff/profile'
import PageHeader from '@/components/console/PageHeader.vue'
import CertificationMark from '@/components/identity/CertificationMark.vue'
import ApplyOrderModal from '@/components/orders/ApplyOrderModal.vue'
import DeliveryApplicationDrawer from '@/components/orders/DeliveryApplicationDrawer.vue'
import WorkLogDrawer from '@/components/orders/WorkLogDrawer.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import type { FdeOrderDetailView, OrderApplicationView, PublicProfileView } from '@/models'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const viewer = computed(() => auth.viewer)
const viewerId = computed(() => auth.viewer?.id ?? '')

const order = ref<FdeOrderDetailView | null>(null)
const publisherProfile = ref<PublicProfileView | null>(null)
const engineerProfile = ref<PublicProfileView | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const successMessage = ref('')
const actionError = ref('')
const busyAction = ref<string | null>(null)
const confirmingCancel = ref(false)
const announcement = ref('')

const applyOpen = ref(false)
const applyError = ref('')

const workLogOpen = ref(false)
const workLogError = ref('')

const deliveryOpen = ref(false)
const deliveryError = ref('')

const rejectingId = ref<string | null>(null)
const rejectNote = ref('')
const rejectError = ref('')

const createdNoticeVisible = ref(false)

const isPublisher = computed(() =>
  Boolean(order.value && order.value.publisherId === viewerId.value),
)
const isEngineer = computed(() => Boolean(order.value && order.value.engineerId === viewerId.value))
const isOpen = computed(() => order.value?.status === 'open')
const isInProgress = computed(() => order.value?.status === 'in_progress')

const myPendingAcceptApplication = computed(() =>
  order.value?.applications.find(
    (application) =>
      application.type === 'accept' &&
      application.status === 'pending' &&
      application.applicantId === viewerId.value,
  ),
)

const myPendingDeliveryApplication = computed(() =>
  order.value?.applications.find(
    (application) =>
      application.type === 'delivery' &&
      application.status === 'pending' &&
      application.applicantId === viewerId.value,
  ),
)

const canApply = computed(
  () => isOpen.value && !isPublisher.value && !myPendingAcceptApplication.value,
)

const pendingAcceptApplications = computed(
  () =>
    order.value?.applications.filter(
      (item) => item.type === 'accept' && item.status === 'pending',
    ) ?? [],
)
const pendingDeliveryApplications = computed(
  () =>
    order.value?.applications.filter(
      (item) => item.type === 'delivery' && item.status === 'pending',
    ) ?? [],
)

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

async function loadProfiles(model: FdeOrderDetailView): Promise<void> {
  publisherProfile.value = null
  engineerProfile.value = null
  try {
    publisherProfile.value = await profileBff.getPublicProfile(model.publisherId)
  } catch {
    publisherProfile.value = null
  }
  if (model.engineerId) {
    try {
      engineerProfile.value = await profileBff.getPublicProfile(model.engineerId)
    } catch {
      engineerProfile.value = null
    }
  }
}

async function loadOrder(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  errorMessage.value = ''

  try {
    const id = String(route.params.id ?? '')
    const model = await ordersBff.getOrder(id)
    order.value = model
    await loadProfiles(model)
  } catch (error) {
    order.value = null
    errorMessage.value = toErrorMessage(error, '订单详情加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

function resetActionState(): void {
  successMessage.value = ''
  actionError.value = ''
}

async function runAction(
  busyKey: string,
  action: () => Promise<unknown>,
  success: string,
): Promise<boolean> {
  if (busyAction.value) return false
  busyAction.value = busyKey
  resetActionState()
  try {
    await action()
    successMessage.value = success
    announcement.value = success
    await loadOrder(false)
    return true
  } catch (error) {
    actionError.value = toErrorMessage(error, '操作失败，请稍后重试。')
    return false
  } finally {
    busyAction.value = null
  }
}

function openApply(): void {
  resetActionState()
  applyError.value = ''
  applyOpen.value = true
}

async function submitAcceptApplication(message: string): Promise<void> {
  if (!order.value || busyAction.value) return
  busyAction.value = 'apply'
  applyError.value = ''
  try {
    await ordersBff.applyForOrder(order.value.id, 'accept', message)
    applyOpen.value = false
    successMessage.value = '接单申请已提交，等待发布者审批。'
    announcement.value = successMessage.value
    await loadOrder(false)
  } catch (error) {
    applyError.value = toErrorMessage(error, '申请接单失败，请稍后重试。')
  } finally {
    busyAction.value = null
  }
}

async function cancelOrder(): Promise<void> {
  if (!order.value) return
  if (!confirmingCancel.value) {
    confirmingCancel.value = true
    return
  }
  await runAction(
    'cancel',
    () => ordersBff.cancelOrder(order.value!.id),
    '订单已取消，托管资金已退回。',
  )
  confirmingCancel.value = false
}

async function approveApplication(application: OrderApplicationView): Promise<void> {
  const success =
    application.type === 'accept' ? '已通过接单申请。' : '已确认交付，托管资金已结算给工程师。'
  await runAction(
    `approve-${application.id}`,
    () => ordersBff.approveApplication(application.id),
    success,
  )
}

function startReject(application: OrderApplicationView): void {
  resetActionState()
  rejectingId.value = application.id
  rejectNote.value = ''
  rejectError.value = ''
}

function cancelReject(): void {
  rejectingId.value = null
  rejectNote.value = ''
  rejectError.value = ''
}

async function submitReject(application: OrderApplicationView): Promise<void> {
  const note = rejectNote.value.trim()
  if (note.length > 500) {
    rejectError.value = '驳回理由不能超过 500 个字符'
    return
  }
  const applied = await runAction(
    `reject-${application.id}`,
    () => ordersBff.rejectApplication(application.id, note || null),
    '已驳回申请。',
  )
  if (applied) cancelReject()
}

function openWorkLog(): void {
  resetActionState()
  workLogError.value = ''
  workLogOpen.value = true
}

async function submitWorkLog(input: {
  content: string
  workedHours: number | null
}): Promise<void> {
  if (!order.value || busyAction.value) return
  busyAction.value = 'work-log'
  workLogError.value = ''
  try {
    await ordersBff.addWorkLog(order.value.id, input)
    workLogOpen.value = false
    successMessage.value = '工作日志已提交。'
    announcement.value = successMessage.value
    await loadOrder(false)
  } catch (error) {
    workLogError.value = toErrorMessage(error, '工作日志提交失败，请稍后重试。')
  } finally {
    busyAction.value = null
  }
}

function openDelivery(): void {
  resetActionState()
  deliveryError.value = ''
  deliveryOpen.value = true
}

async function submitDelivery(message: string): Promise<void> {
  if (!order.value || busyAction.value) return
  busyAction.value = 'delivery'
  deliveryError.value = ''
  try {
    await ordersBff.applyForOrder(order.value.id, 'delivery', message)
    deliveryOpen.value = false
    successMessage.value = '交付申请已提交，等待发布者审批。'
    announcement.value = successMessage.value
    await loadOrder(false)
  } catch (error) {
    deliveryError.value = toErrorMessage(error, '交付申请提交失败，请稍后重试。')
  } finally {
    busyAction.value = null
  }
}

onMounted(async () => {
  if (route.query.created === '1') {
    createdNoticeVisible.value = true
    announcement.value = '需求已发布，预算已进入托管。'
    const query = { ...route.query }
    delete query.created
    void router.replace({ query })
  }
  await loadOrder()
})

watch(
  () => route.params.id,
  () => {
    if (route.name === 'fde-order-detail') void loadOrder()
  },
)
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="order-detail">
      <PageHeader
        eyebrow="FDE ORDER DETAIL"
        :title="order?.title ?? '订单详情'"
        :description="order ? `订单编号 ${order.code}` : undefined"
      >
        <template #actions>
          <RouterLink class="order-detail__link-button" :to="{ name: 'fde-hall' }">
            <UiIcon name="arrow-left" :size="16" />
            返回订单大厅
          </RouterLink>
          <UiButton variant="secondary" size="sm" :loading="loading" @click="loadOrder(false)">
            <UiIcon name="refresh" :size="16" />
            刷新
          </UiButton>
        </template>
      </PageHeader>

      <p class="visually-hidden" role="status" aria-live="polite">{{ announcement }}</p>

      <UiAlert
        v-if="createdNoticeVisible"
        variant="success"
        title="发布成功"
        dismissible
        @close="createdNoticeVisible = false"
      >
        需求已发布，预算已进入托管。
      </UiAlert>

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

      <div v-if="loading" class="order-detail__state" role="status" aria-live="polite">
        正在加载订单详情…
      </div>

      <div v-else-if="errorMessage" class="order-detail__state order-detail__state--error">
        <UiAlert variant="error" title="订单详情加载失败">{{ errorMessage }}</UiAlert>
        <UiButton variant="secondary" size="sm" @click="loadOrder()">重试</UiButton>
      </div>

      <template v-else-if="order">
        <div class="order-detail__toolbar">
          <div class="order-detail__badges">
            <UiChip :variant="order.statusTone">{{ order.statusLabel }}</UiChip>
            <UiChip :variant="order.escrowTone">{{ order.escrowLabel }}</UiChip>
            <UiChip>{{ order.industry }}</UiChip>
          </div>
          <div class="order-detail__actions">
            <UiButton
              v-if="canApply"
              size="sm"
              :loading="busyAction === 'apply'"
              @click="openApply"
            >
              申请接单
            </UiButton>
            <UiButton v-else-if="isOpen && myPendingAcceptApplication" size="sm" disabled>
              接单申请待审批
            </UiButton>
            <UiButton
              v-if="isPublisher && isOpen"
              variant="secondary"
              size="sm"
              :loading="busyAction === 'cancel'"
              @click="cancelOrder"
            >
              {{ confirmingCancel ? '确认取消订单' : '取消订单' }}
            </UiButton>
            <template v-if="isEngineer && isInProgress">
              <UiButton variant="secondary" size="sm" @click="openWorkLog">提交工作日志</UiButton>
              <UiButton v-if="myPendingDeliveryApplication" size="sm" variant="secondary" disabled>
                交付申请待审批
              </UiButton>
              <UiButton v-else size="sm" @click="openDelivery">申请交付</UiButton>
            </template>
          </div>
        </div>

        <UiCard padding="lg" class="order-detail__section">
          <header class="order-detail__section-head">
            <h2 class="order-detail__section-title">订单信息</h2>
          </header>
          <dl class="order-detail__facts">
            <div class="order-detail__fact">
              <dt>订单编号</dt>
              <dd class="order-detail__mono">{{ order.code }}</dd>
            </div>
            <div class="order-detail__fact">
              <dt>状态</dt>
              <dd>
                <UiChip :variant="order.statusTone">{{ order.statusLabel }}</UiChip>
              </dd>
            </div>
            <div class="order-detail__fact">
              <dt>资金托管</dt>
              <dd>
                <UiChip :variant="order.escrowTone">{{ order.escrowLabel }}</UiChip>
              </dd>
            </div>
            <div class="order-detail__fact">
              <dt>行业</dt>
              <dd>{{ order.industry || '—' }}</dd>
            </div>
            <div class="order-detail__fact">
              <dt>交付周期</dt>
              <dd>{{ order.deliveryLabel }}</dd>
            </div>
            <div class="order-detail__fact">
              <dt>订单金额</dt>
              <dd class="order-detail__price">{{ order.priceLabel }}</dd>
            </div>
            <div class="order-detail__fact">
              <dt>创建时间</dt>
              <dd>{{ order.publishedAtLabel }}</dd>
            </div>
            <div class="order-detail__fact">
              <dt>接单时间</dt>
              <dd>{{ order.claimedAtLabel ?? '—' }}</dd>
            </div>
            <div class="order-detail__fact">
              <dt>完成时间</dt>
              <dd>{{ order.completedAtLabel ?? '—' }}</dd>
            </div>
          </dl>
          <div class="order-detail__description">
            <p class="order-detail__description-title">需求描述</p>
            <p class="order-detail__description-body">
              {{ order.description || '暂无需求描述。' }}
            </p>
          </div>
        </UiCard>

        <section class="order-detail__parties" aria-label="订单双方">
          <UiCard padding="lg" class="order-detail__party">
            <p class="order-detail__party-role">发布方</p>
            <div class="order-detail__party-head">
              <h2 class="order-detail__party-name">{{ order.publisherName }}</h2>
              <CertificationMark :certifications="order.publisherCertifications" />
            </div>
            <p v-if="publisherProfile?.bio" class="order-detail__party-bio">
              {{ publisherProfile.bio }}
            </p>
            <p v-if="publisherProfile?.city" class="order-detail__party-meta">
              {{ publisherProfile.city }}
            </p>
            <RouterLink
              class="order-detail__party-link"
              :to="{ name: 'public-profile', params: { id: order.publisherId } }"
            >
              查看发布方公开主页
              <UiIcon name="arrow-right" :size="14" />
            </RouterLink>
          </UiCard>

          <UiCard padding="lg" class="order-detail__party">
            <p class="order-detail__party-role">接单工程师</p>
            <template v-if="order.engineerId">
              <div class="order-detail__party-head">
                <h2 class="order-detail__party-name">{{ order.engineerName }}</h2>
                <CertificationMark :certifications="order.engineerCertifications" />
              </div>
              <p v-if="engineerProfile?.bio" class="order-detail__party-bio">
                {{ engineerProfile.bio }}
              </p>
              <p v-if="engineerProfile?.city" class="order-detail__party-meta">
                {{ engineerProfile.city }}
              </p>
              <RouterLink
                class="order-detail__party-link"
                :to="{ name: 'public-profile', params: { id: order.engineerId } }"
              >
                查看工程师公开主页
                <UiIcon name="arrow-right" :size="14" />
              </RouterLink>
            </template>
            <p v-else class="order-detail__party-empty">尚未有工程师接单。</p>
          </UiCard>
        </section>

        <UiCard padding="lg" class="order-detail__section">
          <header class="order-detail__section-head">
            <h2 class="order-detail__section-title">工作日志</h2>
            <p class="order-detail__section-hint">共 {{ order.logs.length }} 条</p>
          </header>
          <p v-if="order.logs.length === 0" class="order-detail__empty">暂无工作日志。</p>
          <ol v-else class="order-detail__timeline">
            <li v-for="log in order.logs" :key="log.id" class="order-detail__log">
              <div class="order-detail__log-head">
                <span class="order-detail__log-author">{{ log.authorName }}</span>
                <span class="order-detail__log-time">{{ log.createdAtLabel }}</span>
                <span v-if="log.workedHours !== null" class="order-detail__log-hours">
                  {{ log.workedHours }} 小时
                </span>
              </div>
              <p class="order-detail__log-content">{{ log.content }}</p>
            </li>
          </ol>
        </UiCard>

        <UiCard padding="lg" class="order-detail__section">
          <header class="order-detail__section-head">
            <h2 class="order-detail__section-title">申请记录</h2>
            <p class="order-detail__section-hint">该订单的全部接单 / 交付申请与历史审批记录。</p>
          </header>

          <p v-if="order.applications.length === 0" class="order-detail__empty">暂无申请记录。</p>
          <ul v-else class="order-detail__applications">
            <li v-for="application in order.applications" :key="application.id">
              <div class="order-detail__application">
                <div class="order-detail__application-head">
                  <div class="order-detail__application-badges">
                    <UiChip :variant="application.typeTone">{{ application.typeLabel }}</UiChip>
                    <UiChip :variant="application.statusTone">{{ application.statusLabel }}</UiChip>
                    <span class="order-detail__application-time">
                      提交于 {{ application.createdAtLabel }}
                    </span>
                  </div>
                  <div
                    v-if="
                      isPublisher &&
                      application.status === 'pending' &&
                      ((application.type === 'accept' && isOpen) ||
                        (application.type === 'delivery' && isInProgress))
                    "
                    class="order-detail__application-actions"
                  >
                    <UiButton
                      size="sm"
                      :loading="busyAction === `approve-${application.id}`"
                      @click="approveApplication(application)"
                    >
                      {{ application.type === 'accept' ? '通过接单' : '确认交付' }}
                    </UiButton>
                    <UiButton
                      variant="secondary"
                      size="sm"
                      :disabled="Boolean(busyAction)"
                      @click="startReject(application)"
                    >
                      驳回
                    </UiButton>
                  </div>
                </div>

                <dl class="order-detail__facts order-detail__facts--compact">
                  <div class="order-detail__fact">
                    <dt>申请人</dt>
                    <dd>
                      <RouterLink
                        class="order-detail__inline-link"
                        :to="{ name: 'public-profile', params: { id: application.applicantId } }"
                      >
                        {{ application.applicantName }}
                      </RouterLink>
                      <CertificationMark :certifications="application.applicantCertifications" />
                    </dd>
                  </div>
                  <div v-if="application.reviewerName" class="order-detail__fact">
                    <dt>审批人</dt>
                    <dd>
                      <span>{{ application.reviewerName }}</span>
                      <CertificationMark :certifications="application.reviewerCertifications" />
                      <span
                        v-if="application.reviewedAtLabel"
                        class="order-detail__application-time"
                      >
                        · {{ application.reviewedAtLabel }}
                      </span>
                    </dd>
                  </div>
                </dl>

                <p v-if="application.message" class="order-detail__application-message">
                  申请说明：{{ application.message }}
                </p>
                <p
                  v-if="application.reviewNote"
                  class="order-detail__application-message order-detail__application-message--note"
                >
                  {{ application.status === 'rejected' ? '驳回理由' : '审批意见' }}：{{
                    application.reviewNote
                  }}
                </p>

                <div v-if="rejectingId === application.id" class="order-detail__reject">
                  <label class="order-detail__label" :for="`detail-reject-${application.id}`">
                    驳回理由（可选，最多 500 字）
                  </label>
                  <textarea
                    :id="`detail-reject-${application.id}`"
                    v-model="rejectNote"
                    class="order-detail__textarea"
                    rows="2"
                    name="detail-reject-note"
                    :maxlength="500"
                    :disabled="busyAction === `reject-${application.id}`"
                    placeholder="说明驳回原因，便于申请人调整…"
                  />
                  <p v-if="rejectError" class="order-detail__error" role="alert">
                    {{ rejectError }}
                  </p>
                  <div class="order-detail__form-actions">
                    <UiButton
                      variant="destructive"
                      size="sm"
                      :loading="busyAction === `reject-${application.id}`"
                      @click="submitReject(application)"
                    >
                      提交驳回
                    </UiButton>
                    <UiButton variant="ghost" size="sm" @click="cancelReject">取消</UiButton>
                  </div>
                </div>
              </div>
            </li>
          </ul>

          <div
            v-if="pendingAcceptApplications.length && isPublisher && isOpen"
            class="order-detail__hint"
          >
            待审批接单申请 {{ pendingAcceptApplications.length }} 条。
          </div>
          <div
            v-if="pendingDeliveryApplications.length && isPublisher && isInProgress"
            class="order-detail__hint"
          >
            待审批交付申请 {{ pendingDeliveryApplications.length }} 条。
          </div>
        </UiCard>
      </template>

      <ApplyOrderModal
        v-model:open="applyOpen"
        :order="order"
        :submitting="busyAction === 'apply'"
        :error="applyError"
        @confirm="submitAcceptApplication"
      />

      <WorkLogDrawer
        v-model:open="workLogOpen"
        :order="order"
        :submitting="busyAction === 'work-log'"
        :error="workLogError"
        @submit="submitWorkLog"
      />

      <DeliveryApplicationDrawer
        v-model:open="deliveryOpen"
        :order="order"
        :submitting="busyAction === 'delivery'"
        :error="deliveryError"
        @submit="submitDelivery"
      />
    </div>
  </ConsoleLayout>
</template>

<style scoped>
.order-detail {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.order-detail__link-button {
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
}

.order-detail__link-button:hover {
  border-color: var(--color-accent);
  text-decoration: none;
}

.order-detail__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.order-detail__badges,
.order-detail__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.order-detail__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.order-detail__state--error {
  flex-direction: column;
  align-items: flex-start;
}

.order-detail__section {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.order-detail__section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--primitive-space-1) var(--primitive-space-3);
}

.order-detail__section-title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
}

.order-detail__section-hint {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-detail__facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: var(--primitive-space-4);
}

.order-detail__facts--compact {
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: var(--primitive-space-2) var(--primitive-space-5);
}

.order-detail__fact {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.order-detail__fact dt {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-detail__fact dd {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-1);
  color: var(--color-fg);
  font-size: var(--font-size-small);
  overflow-wrap: anywhere;
}

.order-detail__mono {
  font-family: var(--font-family-mono);
  font-size: var(--font-size-code);
}

.order-detail__price {
  color: var(--obsidian-gold-text);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-body-lg);
  font-variant-numeric: tabular-nums;
}

.order-detail__description {
  padding: var(--primitive-space-4);
  background-color: var(--color-bg-subtle);
  border-left: 2px solid var(--color-accent-border);
  border-radius: var(--radius-small);
}

.order-detail__description-title {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
}

.order-detail__description-body {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg);
  font-size: var(--font-size-small);
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.order-detail__parties {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.order-detail__party {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
}

.order-detail__party-role {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
}

.order-detail__party-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.order-detail__party-name {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-medium);
}

.order-detail__party-bio {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.order-detail__party-meta {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-detail__party-link {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-1);
  margin-top: auto;
  padding-top: var(--primitive-space-2);
  color: var(--color-accent-hover);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
}

.order-detail__party-link:hover {
  color: var(--color-accent);
  text-decoration: none;
}

.order-detail__party-empty {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.order-detail__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.order-detail__textarea {
  min-height: 96px;
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  line-height: 1.6;
  resize: vertical;
}

.order-detail__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.order-detail__error {
  margin-top: var(--primitive-space-1);
  color: var(--color-danger);
  font-size: var(--font-size-caption);
}

.order-detail__help {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-detail__form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-3);
}

.order-detail__timeline {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  margin: 0;
  padding: 0;
  list-style: none;
  border-left: var(--border-width-default) solid var(--color-border);
}

.order-detail__log {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
  padding-left: var(--primitive-space-5);
}

.order-detail__log::before {
  position: absolute;
  top: 6px;
  left: -4px;
  width: 7px;
  height: 7px;
  background-color: var(--color-accent);
  border-radius: var(--radius-pill);
  content: '';
}

.order-detail__log-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--primitive-space-2);
}

.order-detail__log-author {
  color: var(--color-fg-strong);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
}

.order-detail__log-time,
.order-detail__log-hours {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-detail__log-content {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.order-detail__applications {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
}

.order-detail__application {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
  padding: var(--primitive-space-4);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.order-detail__application-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--primitive-space-2);
}

.order-detail__application-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.order-detail__application-time {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-detail__application-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2);
}

.order-detail__application-message {
  padding: var(--primitive-space-2) var(--primitive-space-3);
  color: var(--color-fg-muted);
  background-color: var(--color-surface);
  border-left: 2px solid var(--color-border);
  border-radius: var(--radius-small);
  font-size: var(--font-size-small);
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.order-detail__application-message--note {
  color: var(--color-danger);
  border-left-color: var(--color-danger);
}

.order-detail__reject {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
}

.order-detail__inline-link {
  color: var(--color-accent-hover);
  font-weight: var(--font-weight-medium);
}

.order-detail__inline-link:hover {
  color: var(--color-accent);
}

.order-detail__hint {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.order-detail__empty {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

@media (max-width: 900px) {
  .order-detail__parties {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
