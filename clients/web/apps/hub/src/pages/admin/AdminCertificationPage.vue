<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { adminBff } from '@/bff/admin'
import { BffError } from '@/bff/errors'
import PageHeader from '@/components/console/PageHeader.vue'
import CertificationMark from '@/components/identity/CertificationMark.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import {
  CERTIFICATION_APPLICATION_STATUSES,
  CERTIFICATION_APPLICATION_TYPES,
  type AdminCertificationApplicationView,
  type CertificationApplicationStatus,
  type CertificationApplicationType,
} from '@/models'
import { useAuthStore } from '@/stores/auth'

const PAGE_SIZE = 20

const auth = useAuthStore()
const viewer = computed(() => auth.viewer)

const applications = ref<AdminCertificationApplicationView[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)
const errorMessage = ref('')
const successMessage = ref('')
const actionError = ref('')
const busyApplicationId = ref<string | null>(null)
const expandedId = ref<string | null>(null)

const statusFilter = ref<CertificationApplicationStatus | 'all'>('all')
const typeFilter = ref<CertificationApplicationType | 'all'>('all')
const keyword = ref('')

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
      return '当前账号没有认证审核权限。'
    case 'not-found':
      return '认证申请不存在或已被处理，请刷新后重试。'
    case 'conflict':
    case 'invalid-input':
      return error.message || '当前状态不允许该操作，请刷新后重试。'
    case 'network':
      return '无法连接到服务，请检查网络后重试。'
    case 'server':
      return '管理服务暂时不可用，请稍后再试。'
    case 'malformed-response':
      return '服务返回的数据格式异常，请联系管理员。'
    default:
      return error.message || fallback
  }
}

async function loadApplications(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  errorMessage.value = ''

  try {
    const model = await adminBff.listCertificationApplications({
      status: statusFilter.value,
      type: typeFilter.value,
      q: keyword.value.trim() || undefined,
      page: page.value,
      pageSize: PAGE_SIZE,
    })
    applications.value = model.applications
    total.value = model.total
    if (model.page > 0) page.value = model.page
  } catch (error) {
    errorMessage.value = toErrorMessage(error, '认证申请加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  page.value = 1
  expandedId.value = null
  void loadApplications()
}

function changePage(delta: number): void {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  expandedId.value = null
  void loadApplications()
}

function toggleExpanded(application: AdminCertificationApplicationView): void {
  expandedId.value = expandedId.value === application.id ? null : application.id
}

function applicationSummary(application: AdminCertificationApplicationView): string {
  if (application.type === 'enterprise') return application.companyName || '—'
  if (application.type === 'engineer') return application.skills || '—'
  return application.realName || '—'
}

async function approve(application: AdminCertificationApplicationView): Promise<void> {
  if (busyApplicationId.value) return
  busyApplicationId.value = application.id
  actionError.value = ''
  successMessage.value = ''

  try {
    await adminBff.approveCertificationApplication(application.id)
    successMessage.value = `已通过${application.typeLabel}申请，认证已授予该用户。`
    await loadApplications(false)
  } catch (error) {
    actionError.value = toErrorMessage(error, '认证申请审批失败，请稍后重试。')
  } finally {
    busyApplicationId.value = null
  }
}

function startReject(application: AdminCertificationApplicationView): void {
  actionError.value = ''
  successMessage.value = ''
  expandedId.value = application.id
  rejectingId.value = application.id
  rejectNote.value = ''
  rejectError.value = ''
}

function cancelReject(): void {
  rejectingId.value = null
  rejectNote.value = ''
  rejectError.value = ''
}

async function submitReject(application: AdminCertificationApplicationView): Promise<void> {
  if (busyApplicationId.value) return
  const note = rejectNote.value.trim()
  if (note.length > 500) {
    rejectError.value = '驳回理由不能超过 500 个字符'
    return
  }

  busyApplicationId.value = application.id
  actionError.value = ''
  successMessage.value = ''
  try {
    await adminBff.rejectCertificationApplication(application.id, note || null)
    successMessage.value = `已驳回${application.typeLabel}申请。`
    cancelReject()
    await loadApplications(false)
  } catch (error) {
    rejectError.value = toErrorMessage(error, '认证申请驳回失败，请稍后重试。')
  } finally {
    busyApplicationId.value = null
  }
}

watch([statusFilter, typeFilter], handleSearch)

onMounted(() => {
  void loadApplications()
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="cert-admin">
      <PageHeader
        eyebrow="ADMIN · CERTIFICATIONS"
        title="认证审核"
        description="审核实名 / 企业 / 工程师认证申请；通过后认证与角色自动授予申请人。"
      >
        <template #actions>
          <UiButton variant="secondary" size="sm" :loading="loading" @click="loadApplications()">
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

      <section class="cert-admin__panel" :aria-busy="loading ? 'true' : 'false'">
        <form class="cert-admin__toolbar" novalidate @submit.prevent="handleSearch">
          <label class="cert-admin__field" for="cert-status-filter">
            <span class="cert-admin__label">状态</span>
            <select id="cert-status-filter" v-model="statusFilter" class="cert-admin__select">
              <option value="all">全部状态</option>
              <option
                v-for="status in CERTIFICATION_APPLICATION_STATUSES"
                :key="status.key"
                :value="status.key"
              >
                {{ status.label }}
              </option>
            </select>
          </label>

          <label class="cert-admin__field" for="cert-type-filter">
            <span class="cert-admin__label">类型</span>
            <select id="cert-type-filter" v-model="typeFilter" class="cert-admin__select">
              <option value="all">全部类型</option>
              <option
                v-for="type in CERTIFICATION_APPLICATION_TYPES"
                :key="type.key"
                :value="type.key"
              >
                {{ type.label }}
              </option>
            </select>
          </label>

          <UiInput
            v-model="keyword"
            class="cert-admin__search"
            type="search"
            name="cert-search"
            placeholder="搜索申请人昵称、用户名或公司"
            aria-label="搜索认证申请"
          />

          <UiButton type="submit" variant="secondary">搜索</UiButton>
        </form>

        <div v-if="loading" class="cert-admin__state" role="status" aria-live="polite">
          正在加载认证申请…
        </div>

        <div v-else-if="errorMessage" class="cert-admin__error">
          <UiAlert variant="error" title="认证申请加载失败">{{ errorMessage }}</UiAlert>
          <UiButton variant="secondary" size="sm" @click="loadApplications()">重试</UiButton>
        </div>

        <template v-else>
          <div v-if="applications.length" class="cert-admin__table-scroll">
            <table class="cert-admin__table">
              <caption class="visually-hidden">
                认证申请列表
              </caption>
              <thead>
                <tr>
                  <th scope="col">申请人</th>
                  <th scope="col">类型</th>
                  <th scope="col">状态</th>
                  <th scope="col">提交时间</th>
                  <th scope="col">摘要</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="application in applications" :key="application.id">
                  <tr class="cert-admin__row">
                    <td class="cert-admin__cell">
                      <div v-if="application.applicant" class="cert-admin__applicant">
                        <span class="cert-admin__avatar" aria-hidden="true">
                          {{ application.applicant.initials }}
                        </span>
                        <div class="cert-admin__applicant-copy">
                          <p class="cert-admin__applicant-name">
                            {{ application.applicant.displayName }}
                          </p>
                          <p class="cert-admin__applicant-meta">
                            @{{ application.applicant.username }}
                          </p>
                          <CertificationMark
                            :certifications="application.applicant.certifications"
                          />
                        </div>
                      </div>
                      <span v-else class="cert-admin__muted">—</span>
                    </td>
                    <td class="cert-admin__cell">
                      <UiChip :variant="application.typeTone">{{ application.typeLabel }}</UiChip>
                    </td>
                    <td class="cert-admin__cell">
                      <UiChip :variant="application.statusTone">
                        {{ application.statusLabel }}
                      </UiChip>
                    </td>
                    <td class="cert-admin__cell cert-admin__cell--nowrap">
                      {{ application.createdAtLabel }}
                    </td>
                    <td class="cert-admin__cell cert-admin__cell--muted">
                      {{ applicationSummary(application) }}
                    </td>
                    <td class="cert-admin__cell">
                      <div class="cert-admin__actions">
                        <UiButton
                          variant="ghost"
                          size="sm"
                          :aria-expanded="expandedId === application.id ? 'true' : 'false'"
                          @click="toggleExpanded(application)"
                        >
                          {{ expandedId === application.id ? '收起' : '详情' }}
                        </UiButton>
                        <template v-if="application.status === 'pending'">
                          <UiButton
                            size="sm"
                            :loading="busyApplicationId === application.id"
                            @click="approve(application)"
                          >
                            通过
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
                    </td>
                  </tr>

                  <tr v-if="expandedId === application.id" class="cert-admin__row--detail">
                    <td class="cert-admin__cell" colspan="6">
                      <div class="cert-admin__detail">
                        <dl class="cert-admin__detail-grid">
                          <div v-if="application.realName" class="cert-admin__detail-item">
                            <dt>真实姓名</dt>
                            <dd>{{ application.realName }}</dd>
                          </div>
                          <div v-if="application.idNumber" class="cert-admin__detail-item">
                            <dt>身份证号</dt>
                            <dd>{{ application.idNumber }}</dd>
                          </div>
                          <div v-if="application.companyName" class="cert-admin__detail-item">
                            <dt>公司名称</dt>
                            <dd>{{ application.companyName }}</dd>
                          </div>
                          <div v-if="application.creditCode" class="cert-admin__detail-item">
                            <dt>统一社会信用代码</dt>
                            <dd>{{ application.creditCode }}</dd>
                          </div>
                          <div v-if="application.contactName" class="cert-admin__detail-item">
                            <dt>联系人</dt>
                            <dd>{{ application.contactName }}</dd>
                          </div>
                          <div v-if="application.contactPhone" class="cert-admin__detail-item">
                            <dt>联系电话</dt>
                            <dd>{{ application.contactPhone }}</dd>
                          </div>
                          <div v-if="application.skills" class="cert-admin__detail-item">
                            <dt>技能</dt>
                            <dd>{{ application.skills }}</dd>
                          </div>
                          <div
                            v-if="application.workYears !== null"
                            class="cert-admin__detail-item"
                          >
                            <dt>工作年限</dt>
                            <dd>{{ application.workYears }} 年</dd>
                          </div>
                          <div class="cert-admin__detail-item">
                            <dt>当前认证</dt>
                            <dd>
                              <CertificationMark
                                :certifications="application.applicant?.certifications ?? []"
                              />
                              <span
                                v-if="!application.applicant?.certifications.length"
                                class="cert-admin__muted"
                              >
                                无
                              </span>
                            </dd>
                          </div>
                          <div v-if="application.reviewer" class="cert-admin__detail-item">
                            <dt>审批人</dt>
                            <dd>{{ application.reviewer.displayName }}</dd>
                          </div>
                          <div v-if="application.reviewedAtLabel" class="cert-admin__detail-item">
                            <dt>审批时间</dt>
                            <dd>{{ application.reviewedAtLabel }}</dd>
                          </div>
                        </dl>

                        <div v-if="application.projectExperience" class="cert-admin__text-block">
                          <p class="cert-admin__text-title">项目经历</p>
                          <p class="cert-admin__text">{{ application.projectExperience }}</p>
                        </div>
                        <div v-if="application.description" class="cert-admin__text-block">
                          <p class="cert-admin__text-title">说明</p>
                          <p class="cert-admin__text">{{ application.description }}</p>
                        </div>
                        <div v-if="application.reviewNote" class="cert-admin__text-block">
                          <p class="cert-admin__text-title">审核意见</p>
                          <p class="cert-admin__text cert-admin__text--note">
                            {{ application.reviewNote }}
                          </p>
                        </div>

                        <div v-if="rejectingId === application.id" class="cert-admin__reject">
                          <label class="cert-admin__label" :for="`reject-note-${application.id}`">
                            驳回理由（可选，最多 500 字）
                          </label>
                          <textarea
                            :id="`reject-note-${application.id}`"
                            v-model="rejectNote"
                            class="cert-admin__textarea"
                            rows="2"
                            name="cert-reject-note"
                            :maxlength="500"
                            :disabled="busyApplicationId === application.id"
                            placeholder="说明驳回原因，便于申请人补充材料…"
                          />
                          <p v-if="rejectError" class="cert-admin__error-text" role="alert">
                            {{ rejectError }}
                          </p>
                          <div class="cert-admin__actions">
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
                              :disabled="Boolean(busyApplicationId)"
                              @click="cancelReject"
                            >
                              取消
                            </UiButton>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <p v-else class="cert-admin__empty">没有符合条件的认证申请。</p>

          <div class="cert-admin__pagination">
            <span class="cert-admin__pagination-summary">
              共 {{ total }} 条申请 · 第 {{ page }} / {{ totalPages }} 页
            </span>
            <div class="cert-admin__pagination-actions">
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
        </template>
      </section>
    </div>
  </ConsoleLayout>
</template>

<style scoped>
.cert-admin {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.cert-admin__panel {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
  padding: var(--primitive-space-5);
  background-color: var(--color-surface);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-surface);
  box-shadow: var(--obsidian-panel-highlight);
}

.cert-admin__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--primitive-space-3);
}

.cert-admin__field {
  display: flex;
  flex-direction: column;
}

.cert-admin__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.cert-admin__select {
  height: 44px;
  min-width: 9rem;
  padding: 0 var(--primitive-space-4);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
}

.cert-admin__select option {
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
}

.cert-admin__search {
  flex: 1 1 16rem;
}

.cert-admin__state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.cert-admin__error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--primitive-space-3);
}

.cert-admin__table-scroll {
  width: 100%;
  overflow-x: auto;
}

.cert-admin__table {
  width: 100%;
  min-width: 60rem;
  border-collapse: collapse;
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  text-align: left;
}

.cert-admin__table thead th {
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--obsidian-tertiary-text);
  border-bottom: var(--border-width-default) solid var(--color-border);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
  white-space: nowrap;
}

.cert-admin__row:hover {
  background-color: var(--color-bg-subtle);
}

.cert-admin__cell {
  padding: var(--primitive-space-4);
  color: var(--color-fg);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
  vertical-align: top;
}

.cert-admin__cell--nowrap {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.cert-admin__cell--muted,
.cert-admin__muted {
  color: var(--color-fg-muted);
}

.cert-admin__applicant {
  display: flex;
  align-items: flex-start;
  gap: var(--primitive-space-3);
}

.cert-admin__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex: none;
  color: var(--color-accent);
  background-color: var(--color-accent-subtle);
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-pill);
  font-size: var(--font-size-caption);
}

.cert-admin__applicant-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.cert-admin__applicant-name {
  color: var(--color-fg-strong);
  font-weight: var(--font-weight-medium);
}

.cert-admin__applicant-meta {
  color: var(--obsidian-tertiary-text);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-caption);
}

.cert-admin__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
}

.cert-admin__row--detail {
  background-color: var(--color-bg-subtle);
}

.cert-admin__detail {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-2);
}

.cert-admin__detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: var(--primitive-space-3);
}

.cert-admin__detail-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cert-admin__detail-item dt {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.cert-admin__detail-item dd {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-1);
  color: var(--color-fg);
  font-size: var(--font-size-small);
  overflow-wrap: anywhere;
}

.cert-admin__text-block {
  padding: var(--primitive-space-3) var(--primitive-space-4);
  background-color: var(--color-surface);
  border-left: 2px solid var(--color-border);
  border-radius: var(--radius-small);
}

.cert-admin__text-title {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
}

.cert-admin__text {
  margin-top: 2px;
  color: var(--color-fg);
  font-size: var(--font-size-small);
  line-height: 1.6;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.cert-admin__text--note {
  color: var(--color-danger);
}

.cert-admin__reject {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
}

.cert-admin__textarea {
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

.cert-admin__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.cert-admin__error-text {
  color: var(--color-danger);
  font-size: var(--font-size-caption);
}

.cert-admin__empty {
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  text-align: center;
}

.cert-admin__pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
  padding-top: var(--primitive-space-2);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.cert-admin__pagination-summary {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.cert-admin__pagination-actions {
  display: flex;
  gap: var(--primitive-space-2);
}
</style>
