<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import PageHeader from '@/components/console/PageHeader.vue'
import CertificationMark from '@/components/identity/CertificationMark.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import {
  APPLICATION_STATUSES,
  APPLICATION_TYPES,
  type ApplicationStatus,
  type ApplicationType,
  type OrderApplicationView,
} from '@/models'
import { useAuthStore } from '@/stores/auth'

type ApplicationsTab = 'mine' | 'received'

const PAGE_SIZE = 10

const auth = useAuthStore()
const route = useRoute()
const viewer = computed(() => auth.viewer)

const initialTab: ApplicationsTab = route.query.tab === 'received' ? 'received' : 'mine'

const activeTab = ref<ApplicationsTab>(initialTab)
const applications = ref<OrderApplicationView[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)
const refreshing = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const actionError = ref('')
const busyApplicationId = ref<string | null>(null)

const typeFilter = ref<ApplicationType | 'all'>('all')
// 待我审批默认只看待审批的申请。
const statusFilter = ref<ApplicationStatus | 'all'>(initialTab === 'received' ? 'pending' : 'all')

const rejectingId = ref<string | null>(null)
const rejectNote = ref('')
const rejectError = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function toErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof BffError)) return fallback

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return '当前账号没有处理该申请的权限。'
    case 'not-found':
      return '申请不存在或已被移除，请刷新后重试。'
    case 'conflict':
    case 'invalid-input':
      return error.message || '当前操作与申请状态冲突，请刷新后重试。'
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

async function loadApplications(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  errorMessage.value = ''

  const filter = {
    type: typeFilter.value,
    status: statusFilter.value,
    page: page.value,
    pageSize: PAGE_SIZE,
  }

  try {
    const model =
      activeTab.value === 'mine'
        ? await ordersBff.listMyApplications(filter)
        : await ordersBff.listReceivedApplications(filter)
    applications.value = model.applications
    total.value = model.total
    if (model.page > 0) page.value = model.page
  } catch (error) {
    errorMessage.value = toErrorMessage(error, '申请列表加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

async function refresh(): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await loadApplications(false)
  } finally {
    refreshing.value = false
  }
}

function switchTab(tab: ApplicationsTab): void {
  if (activeTab.value === tab) return
  activeTab.value = tab
  // 待我审批默认只看待审批的申请；我发起的默认展示全部状态。
  statusFilter.value = tab === 'received' ? 'pending' : 'all'
  page.value = 1
  rejectingId.value = null
  successMessage.value = ''
  actionError.value = ''
}

function changeFilter(): void {
  page.value = 1
  rejectingId.value = null
  void loadApplications()
}

function changePage(delta: number): void {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  void loadApplications()
}

async function runAction(
  application: OrderApplicationView,
  action: () => Promise<unknown>,
  success: string,
): Promise<void> {
  if (busyApplicationId.value) return
  busyApplicationId.value = application.id
  actionError.value = ''
  successMessage.value = ''

  try {
    await action()
    successMessage.value = success
    await loadApplications(false)
  } catch (error) {
    actionError.value = toErrorMessage(error, '操作失败，请稍后重试。')
  } finally {
    busyApplicationId.value = null
  }
}

function withdraw(application: OrderApplicationView): void {
  void runAction(application, () => ordersBff.withdrawApplication(application.id), '申请已撤回。')
}

function approve(application: OrderApplicationView): void {
  void runAction(
    application,
    () => ordersBff.approveApplication(application.id),
    application.type === 'accept' ? '已通过接单申请。' : '已确认交付并结算托管资金。',
  )
}

function startReject(application: OrderApplicationView): void {
  actionError.value = ''
  successMessage.value = ''
  rejectingId.value = application.id
  rejectNote.value = ''
  rejectError.value = ''
}

function cancelReject(): void {
  rejectingId.value = null
  rejectNote.value = ''
  rejectError.value = ''
}

function submitReject(application: OrderApplicationView): void {
  const note = rejectNote.value.trim()
  if (note.length > 500) {
    rejectError.value = '驳回理由不能超过 500 个字符'
    return
  }
  rejectError.value = ''
  void runAction(
    application,
    () => ordersBff.rejectApplication(application.id, note || null),
    '已驳回申请。',
  ).then(() => {
    if (!actionError.value) cancelReject()
  })
}

watch([activeTab, typeFilter, statusFilter], changeFilter)

onMounted(() => {
  void loadApplications()
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="applications-page">
      <PageHeader
        eyebrow="ORDER APPLICATIONS"
        title="我的申请"
        description="查看我发起的接单/交付申请，或审批我发布的订单收到的申请。"
      >
        <template #actions>
          <UiButton variant="secondary" size="sm" :loading="refreshing" @click="refresh">
            <UiIcon name="refresh" :size="16" />
            刷新
          </UiButton>
        </template>
      </PageHeader>

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

      <section class="applications-panel" :aria-busy="loading ? 'true' : 'false'">
        <div class="applications-toolbar">
          <div class="applications-tabs" role="tablist" aria-label="申请视图">
            <button
              type="button"
              role="tab"
              class="applications-tabs__button"
              :class="{ 'is-active': activeTab === 'mine' }"
              :aria-selected="activeTab === 'mine' ? 'true' : 'false'"
              data-tab="mine"
              @click="switchTab('mine')"
            >
              我发起的
            </button>
            <button
              type="button"
              role="tab"
              class="applications-tabs__button"
              :class="{ 'is-active': activeTab === 'received' }"
              :aria-selected="activeTab === 'received' ? 'true' : 'false'"
              data-tab="received"
              @click="switchTab('received')"
            >
              待我审批
            </button>
          </div>

          <div class="applications-filters">
            <label class="applications-filters__field" for="application-type-filter">
              <span class="applications-filters__label">类型</span>
              <select
                id="application-type-filter"
                v-model="typeFilter"
                class="applications-filters__select"
              >
                <option value="all">全部类型</option>
                <option v-for="type in APPLICATION_TYPES" :key="type.key" :value="type.key">
                  {{ type.label }}
                </option>
              </select>
            </label>

            <label class="applications-filters__field" for="application-status-filter">
              <span class="applications-filters__label">状态</span>
              <select
                id="application-status-filter"
                v-model="statusFilter"
                class="applications-filters__select"
              >
                <option value="all">全部状态</option>
                <option
                  v-for="status in APPLICATION_STATUSES"
                  :key="status.key"
                  :value="status.key"
                >
                  {{ status.label }}
                </option>
              </select>
            </label>
          </div>
        </div>

        <div v-if="loading" class="applications-state" role="status" aria-live="polite">
          <span class="applications-state__spinner" aria-hidden="true" />
          正在加载申请…
        </div>

        <div v-else-if="errorMessage" class="applications-error">
          <UiAlert variant="error" title="申请加载失败">{{ errorMessage }}</UiAlert>
          <UiButton variant="secondary" size="sm" @click="refresh">重试</UiButton>
        </div>

        <p v-else-if="applications.length === 0" class="applications-empty">暂无符合条件的申请。</p>

        <ul v-else class="application-list">
          <li v-for="application in applications" :key="application.id">
            <UiCard padding="md" class="application-card">
              <header class="application-card__head">
                <div class="application-card__order">
                  <p class="application-card__title">{{ application.order.title }}</p>
                  <div class="application-card__meta">
                    <span class="application-card__code">{{ application.order.code }}</span>
                    <UiChip :variant="application.order.statusTone">
                      {{ application.order.statusLabel }}
                    </UiChip>
                    <span class="application-card__time">{{ application.createdAtLabel }}</span>
                  </div>
                </div>
                <div class="application-card__badges">
                  <UiChip :variant="application.typeTone">{{ application.typeLabel }}</UiChip>
                  <UiChip :variant="application.statusTone">{{ application.statusLabel }}</UiChip>
                </div>
              </header>

              <dl class="application-card__facts">
                <div class="application-card__fact">
                  <dt>申请人</dt>
                  <dd>
                    <span>{{ application.applicantName }}</span>
                    <CertificationMark :certifications="application.applicantCertifications" />
                  </dd>
                </div>
                <div v-if="application.reviewerName" class="application-card__fact">
                  <dt>审批人</dt>
                  <dd>
                    <span>{{ application.reviewerName }}</span>
                    <CertificationMark :certifications="application.reviewerCertifications" />
                    <span v-if="application.reviewedAtLabel" class="application-card__time">
                      {{ application.reviewedAtLabel }}
                    </span>
                  </dd>
                </div>
              </dl>

              <p v-if="application.message" class="application-card__message">
                申请说明：{{ application.message }}
              </p>
              <p v-if="application.reviewNote" class="application-card__note">
                {{ application.status === 'rejected' ? '驳回理由' : '审批意见' }}：{{
                  application.reviewNote
                }}
              </p>

              <div v-if="application.status === 'pending'" class="application-card__actions">
                <template v-if="activeTab === 'mine'">
                  <UiButton
                    variant="secondary"
                    size="sm"
                    :loading="busyApplicationId === application.id"
                    @click="withdraw(application)"
                  >
                    撤回申请
                  </UiButton>
                </template>

                <template v-else-if="rejectingId === application.id">
                  <div class="application-card__reject">
                    <label
                      class="application-card__reject-label"
                      :for="`reject-note-${application.id}`"
                    >
                      驳回理由（可选，最多 500 字）
                    </label>
                    <textarea
                      :id="`reject-note-${application.id}`"
                      v-model="rejectNote"
                      class="application-card__reject-input"
                      rows="2"
                      name="reject-note"
                      :maxlength="500"
                      :disabled="busyApplicationId === application.id"
                      placeholder="说明驳回原因，便于申请人调整…"
                    />
                    <p v-if="rejectError" class="application-card__reject-error" role="alert">
                      {{ rejectError }}
                    </p>
                    <div class="application-card__reject-actions">
                      <UiButton
                        variant="destructive"
                        size="sm"
                        :loading="busyApplicationId === application.id"
                        @click="submitReject(application)"
                      >
                        提交驳回
                      </UiButton>
                      <UiButton
                        variant="ghost"
                        size="sm"
                        :disabled="busyApplicationId === application.id"
                        @click="cancelReject"
                      >
                        取消
                      </UiButton>
                    </div>
                  </div>
                </template>

                <template v-else>
                  <UiButton
                    size="sm"
                    :loading="busyApplicationId === application.id"
                    @click="approve(application)"
                  >
                    {{ application.type === 'accept' ? '通过接单' : '确认交付' }}
                  </UiButton>
                  <UiButton
                    variant="secondary"
                    size="sm"
                    :disabled="Boolean(busyApplicationId)"
                    @click="startReject(application)"
                  >
                    驳回
                  </UiButton>
                </template>
              </div>
            </UiCard>
          </li>
        </ul>

        <div class="applications-pagination">
          <span class="applications-pagination__summary">
            共 {{ total }} 条申请 · 第 {{ page }} / {{ totalPages }} 页
          </span>
          <div class="applications-pagination__actions">
            <UiButton variant="secondary" size="sm" :disabled="page <= 1" @click="changePage(-1)">
              上一页
            </UiButton>
            <UiButton
              variant="secondary"
              size="sm"
              :disabled="page >= totalPages"
              @click="changePage(1)"
            >
              下一页
            </UiButton>
          </div>
        </div>
      </section>
    </div>
  </ConsoleLayout>
</template>

<style scoped>
.applications-page {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.applications-panel {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
  padding: var(--primitive-space-5);
  background-color: var(--color-surface);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-surface);
  box-shadow: var(--obsidian-panel-highlight);
}

.applications-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.applications-tabs {
  display: inline-flex;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-1);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.applications-tabs__button {
  min-height: 32px;
  padding: 0 var(--primitive-space-4);
  color: var(--color-fg-muted);
  background: transparent;
  border: var(--border-width-default) solid transparent;
  border-radius: var(--radius-small);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: 1;
  white-space: nowrap;
}

.applications-tabs__button.is-active {
  color: var(--obsidian-gold-text);
  background-color: var(--color-accent-subtle);
  border-color: var(--color-accent-border);
}

.applications-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-3);
}

.applications-filters__field {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
}

.applications-filters__label {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}

.applications-filters__select {
  height: 38px;
  padding: 0 var(--primitive-space-3);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
}

.applications-filters__select option {
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
}

.applications-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.applications-state__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: var(--radius-pill);
  animation: applications-spin 0.9s linear infinite;
}

.applications-error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--primitive-space-3);
}

.applications-empty {
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  text-align: center;
}

.application-list {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
}

.application-card {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
}

.application-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.application-card__order {
  min-width: 0;
}

.application-card__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
  overflow-wrap: anywhere;
}

.application-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
  margin-top: var(--primitive-space-1);
}

.application-card__code {
  color: var(--obsidian-tertiary-text);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-code);
}

.application-card__time {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
}

.application-card__badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2);
}

.application-card__facts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-3) var(--primitive-space-6);
}

.application-card__fact {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
}

.application-card__fact dt {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.application-card__fact dd {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
  color: var(--color-fg);
  font-size: var(--font-size-small);
}

.application-card__message,
.application-card__note {
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--color-fg-muted);
  background-color: var(--color-bg-subtle);
  border-left: 2px solid var(--color-border);
  border-radius: var(--radius-small);
  font-size: var(--font-size-small);
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.application-card__note {
  border-left-color: var(--color-accent-border);
}

.application-card__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
  padding-top: var(--primitive-space-2);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.application-card__reject {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
  width: 100%;
}

.application-card__reject-label {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
}

.application-card__reject-input {
  min-height: 64px;
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

.application-card__reject-input:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.application-card__reject-error {
  color: var(--color-danger);
  font-size: var(--font-size-caption);
}

.application-card__reject-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2);
}

.applications-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
  padding-top: var(--primitive-space-2);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.applications-pagination__summary {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.applications-pagination__actions {
  display: flex;
  gap: var(--primitive-space-2);
}

@keyframes applications-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
