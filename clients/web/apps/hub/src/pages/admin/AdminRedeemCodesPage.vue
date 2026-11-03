<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { z } from 'zod'

import { adminBff } from '@/bff/admin'
import { BffError } from '@/bff/errors'
import PageHeader from '@/components/console/PageHeader.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import {
  ADMIN_REDEEM_CODE_STATUSES,
  type AdminRedeemCodeStatus,
  type AdminRedeemCodeView,
} from '@/models'
import { useAuthStore } from '@/stores/auth'

const PAGE_SIZE = 20

const auth = useAuthStore()
const viewer = computed(() => auth.viewer)

const codes = ref<AdminRedeemCodeView[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)
const errorMessage = ref('')
const successMessage = ref('')

const statusFilter = ref<AdminRedeemCodeStatus | 'all'>('all')
const keyword = ref('')

const amountYuan = ref('')
const quantity = ref('1')
const expiresInDays = ref('')
const note = ref('')
const creating = ref(false)
const formError = ref('')

interface FormFieldErrors {
  amountYuan?: string
  quantity?: string
  expiresInDays?: string
  note?: string
}

const FORM_FIELDS = ['amountYuan', 'quantity', 'expiresInDays', 'note'] as const
type FormField = (typeof FORM_FIELDS)[number]
const fieldErrors = reactive<FormFieldErrors>({})

const pendingId = ref<string | null>(null)

const STATUS_FILTERS: readonly { key: AdminRedeemCodeStatus | 'all'; label: string }[] = [
  { key: 'all', label: '全部' },
  ...ADMIN_REDEEM_CODE_STATUSES.map((meta) => ({ key: meta.key, label: meta.label })),
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const createSchema = z.object({
  amountYuan: z
    .string()
    .trim()
    .min(1, '请输入面额')
    .refine((value) => /^\d+(\.\d{1,2})?$/.test(value), '面额最多保留两位小数')
    .transform((value) => Number(value))
    .refine((value) => value >= 1, '面额不能低于 1 元')
    .refine((value) => value <= 1_000_000, '面额不能超过 1,000,000 元'),
  quantity: z
    .string()
    .trim()
    .min(1, '请输入生成数量')
    .refine((value) => /^\d+$/.test(value), '生成数量需为整数')
    .transform((value) => Number(value))
    .refine((value) => value >= 1 && value <= 100, '生成数量需在 1–100 之间'),
  expiresInDays: z
    .string()
    .trim()
    .refine((value) => value === '' || /^\d+$/.test(value), '有效期需为整数天数')
    .transform((value) => (value === '' ? null : Number(value)))
    .refine((value) => value === null || (value >= 1 && value <= 3650), '有效期需在 1–3650 天之间'),
  note: z.string().trim().max(120, '备注长度不能超过 120 个字符'),
})

/** Map the BFF's stable error codes to admin copy; the page never inspects HTTP statuses. */
function toErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof BffError)) return fallback

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return '当前账号没有管理员权限，请联系超级管理员。'
    case 'not-found':
      return '兑换码不存在或已被移除，请刷新后重试。'
    case 'conflict':
    case 'invalid-input':
      return error.message || fallback
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

async function loadCodes(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  errorMessage.value = ''

  try {
    const model = await adminBff.listRedeemCodes({
      status: statusFilter.value,
      q: keyword.value.trim() || undefined,
      page: page.value,
      pageSize: PAGE_SIZE,
    })
    codes.value = model.codes
    total.value = model.total
    if (model.page > 0) page.value = model.page
  } catch (error) {
    errorMessage.value = toErrorMessage(error, '兑换码列表加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

function clearFieldErrors(): void {
  for (const field of FORM_FIELDS) fieldErrors[field] = undefined
}

async function handleCreate(): Promise<void> {
  if (creating.value) return

  clearFieldErrors()
  formError.value = ''
  successMessage.value = ''

  const result = createSchema.safeParse({
    amountYuan: amountYuan.value,
    quantity: quantity.value,
    expiresInDays: expiresInDays.value,
    note: note.value,
  })

  if (!result.success) {
    for (const issue of result.error.issues) {
      const field = issue.path[0]
      if (typeof field !== 'string' || !(FORM_FIELDS as readonly string[]).includes(field)) continue
      if (!fieldErrors[field as FormField]) fieldErrors[field as FormField] = issue.message
    }
    return
  }

  creating.value = true
  try {
    const batch = await adminBff.createRedeemCodes({
      amountCents: Math.round(result.data.amountYuan * 100),
      quantity: result.data.quantity,
      expiresInDays: result.data.expiresInDays,
      note: result.data.note || null,
    })
    successMessage.value = `已生成 ${batch.codes.length} 个兑换码，批次号 ${batch.batchNo}。`
    amountYuan.value = ''
    quantity.value = '1'
    expiresInDays.value = ''
    note.value = ''
    page.value = 1
    await loadCodes(false)
  } catch (error) {
    formError.value = toErrorMessage(error, '生成兑换码失败，请稍后重试。')
  } finally {
    creating.value = false
  }
}

function handleSearch(): void {
  page.value = 1
  void loadCodes()
}

async function toggleStatus(code: AdminRedeemCodeView): Promise<void> {
  if (code.status === 'used' || pendingId.value) return
  const next: 'active' | 'disabled' = code.status === 'active' ? 'disabled' : 'active'
  if (next === 'active' && code.isExpired) return

  pendingId.value = code.id
  errorMessage.value = ''
  successMessage.value = ''
  try {
    await adminBff.updateRedeemCodeStatus(code.id, next)
    successMessage.value = `已${next === 'active' ? '启用' : '停用'}兑换码 ${code.code}。`
    await loadCodes(false)
  } catch (error) {
    errorMessage.value = toErrorMessage(error, '兑换码状态更新失败，请稍后重试。')
  } finally {
    pendingId.value = null
  }
}

function changePage(delta: number): void {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  void loadCodes()
}

onMounted(() => {
  void loadCodes()
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="admin-page">
      <PageHeader
        eyebrow="ADMIN · REDEEM CODES"
        title="兑换码管理"
        description="按批次生成兑换码，追踪使用与过期状态，并随时停用未使用的码。"
      >
        <template #actions>
          <UiButton variant="secondary" size="sm" :loading="loading" @click="loadCodes()">
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

      <section class="admin-panel">
        <header class="admin-section-head">
          <h2 class="admin-section-title">生成兑换码</h2>
          <p class="admin-section-hint">单批最多 100 个，面额与有效期仅对新生成的码生效。</p>
        </header>

        <UiAlert
          v-if="formError"
          variant="error"
          title="生成失败"
          dismissible
          @close="formError = ''"
        >
          {{ formError }}
        </UiAlert>

        <form class="redeem-form" novalidate @submit.prevent="handleCreate">
          <UiInput
            v-model="amountYuan"
            name="redeem-amount"
            label="面额 / 元"
            inputmode="decimal"
            placeholder="100"
            :error="fieldErrors.amountYuan"
            :disabled="creating"
          />
          <UiInput
            v-model="quantity"
            name="redeem-quantity"
            label="生成数量"
            inputmode="numeric"
            placeholder="1"
            :error="fieldErrors.quantity"
            :disabled="creating"
          />
          <UiInput
            v-model="expiresInDays"
            name="redeem-expires"
            label="有效期 / 天（可空）"
            inputmode="numeric"
            placeholder="留空表示永久有效"
            :error="fieldErrors.expiresInDays"
            :disabled="creating"
          />
          <UiInput
            v-model="note"
            name="redeem-note"
            label="备注（可空）"
            placeholder="例如：双十一活动"
            :maxlength="120"
            :error="fieldErrors.note"
            :disabled="creating"
          />
          <div class="redeem-form__actions">
            <UiButton type="submit" :loading="creating">生成兑换码</UiButton>
          </div>
        </form>
      </section>

      <section class="admin-panel">
        <div class="admin-toolbar">
          <div class="admin-filters" role="group" aria-label="按兑换码状态筛选">
            <button
              v-for="filter in STATUS_FILTERS"
              :key="filter.key"
              class="admin-filters__button"
              :class="{ 'is-active': statusFilter === filter.key }"
              type="button"
              :aria-pressed="statusFilter === filter.key ? 'true' : 'false'"
              @click="
                () => {
                  statusFilter = filter.key
                  handleSearch()
                }
              "
            >
              {{ filter.label }}
            </button>
          </div>

          <form class="admin-toolbar__form" novalidate @submit.prevent="handleSearch">
            <UiInput
              v-model="keyword"
              class="admin-toolbar__search"
              type="search"
              name="redeem-search"
              placeholder="搜索兑换码或批次号"
              aria-label="搜索兑换码"
            />
            <UiButton type="submit" variant="secondary">搜索</UiButton>
          </form>
        </div>

        <div v-if="loading" class="admin-state" role="status" aria-live="polite">
          正在加载兑换码…
        </div>

        <div v-else-if="errorMessage" class="admin-error">
          <UiAlert variant="error" title="兑换码加载失败">{{ errorMessage }}</UiAlert>
          <UiButton variant="secondary" size="sm" @click="loadCodes()">重试</UiButton>
        </div>

        <template v-else>
          <div v-if="codes.length" class="admin-table__scroll">
            <table class="admin-table">
              <caption class="visually-hidden">
                兑换码列表
              </caption>
              <thead>
                <tr>
                  <th scope="col">兑换码</th>
                  <th scope="col">面额</th>
                  <th scope="col">状态</th>
                  <th scope="col">批次</th>
                  <th scope="col">创建时间</th>
                  <th scope="col">过期时间</th>
                  <th scope="col">使用人</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="code in codes" :key="code.id" class="admin-table__row">
                  <td class="admin-table__cell admin-table__code">{{ code.code }}</td>
                  <td class="admin-table__cell admin-table__cell--money">{{ code.amountLabel }}</td>
                  <td class="admin-table__cell">
                    <UiChip :variant="code.statusTone">{{ code.statusLabel }}</UiChip>
                  </td>
                  <td class="admin-table__cell admin-table__cell--muted">{{ code.batchNo }}</td>
                  <td class="admin-table__cell admin-table__cell--nowrap">
                    {{ code.createdAtLabel }}
                  </td>
                  <td class="admin-table__cell admin-table__cell--nowrap">
                    {{ code.expiresAtLabel ?? '永久有效' }}
                  </td>
                  <td class="admin-table__cell admin-table__cell--muted">
                    <template v-if="code.usedByName">
                      {{ code.usedByName }}
                      <span v-if="code.usedAtLabel" class="admin-table__sub">
                        · {{ code.usedAtLabel }}
                      </span>
                    </template>
                    <span v-else>—</span>
                  </td>
                  <td class="admin-table__cell">
                    <UiButton
                      v-if="code.status !== 'used'"
                      variant="ghost"
                      size="sm"
                      :loading="pendingId === code.id"
                      :disabled="code.status === 'disabled' && code.isExpired"
                      @click="toggleStatus(code)"
                    >
                      {{ code.status === 'active' ? '停用' : '启用' }}
                    </UiButton>
                    <span v-else class="admin-table__cell--muted">已使用</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="admin-empty">没有符合条件的兑换码。</p>

          <div class="admin-pagination">
            <span class="admin-pagination__summary">
              共 {{ total }} 个兑换码 · 第 {{ page }} / {{ totalPages }} 页
            </span>
            <div class="admin-pagination__actions">
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
.admin-page {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.admin-panel {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
  padding: var(--primitive-space-5);
  background-color: var(--color-surface);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-surface);
  box-shadow: var(--obsidian-panel-highlight);
}

.admin-section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--primitive-space-2);
}

.admin-section-title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
}

.admin-section-hint {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.redeem-form {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-items: start;
  gap: var(--primitive-space-4);
}

.redeem-form__actions {
  grid-column: 1 / -1;
  display: flex;
  gap: var(--primitive-space-3);
}

.admin-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.admin-toolbar__form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.admin-toolbar__search {
  min-width: 16rem;
}

.admin-filters {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-1);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.admin-filters__button {
  min-height: 30px;
  padding: 0 var(--primitive-space-3);
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

.admin-filters__button:hover {
  color: var(--color-fg);
}

.admin-filters__button.is-active {
  color: var(--obsidian-gold-text);
  background-color: var(--color-accent-subtle);
  border-color: var(--color-accent-border);
}

.admin-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.admin-error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--primitive-space-3);
}

.admin-table__scroll {
  width: 100%;
  overflow-x: auto;
}

.admin-table {
  width: 100%;
  min-width: 64rem;
  border-collapse: collapse;
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  text-align: left;
}

.admin-table thead th {
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--obsidian-tertiary-text);
  border-bottom: var(--border-width-default) solid var(--color-border);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
  white-space: nowrap;
}

.admin-table__row:hover {
  background-color: var(--color-bg-subtle);
}

.admin-table__cell {
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--color-fg);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
  vertical-align: middle;
}

.admin-table__code {
  color: var(--color-fg-strong);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-code);
  white-space: nowrap;
}

.admin-table__cell--muted {
  color: var(--color-fg-muted);
}

.admin-table__cell--nowrap {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.admin-table__cell--money {
  color: var(--obsidian-gold-text);
  font-family: var(--font-family-heading);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.admin-table__sub {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
}

.admin-empty {
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  text-align: center;
}

.admin-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
  padding-top: var(--primitive-space-2);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.admin-pagination__summary {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.admin-pagination__actions {
  display: flex;
  gap: var(--primitive-space-2);
}

@media (max-width: 1100px) {
  .redeem-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .redeem-form {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
