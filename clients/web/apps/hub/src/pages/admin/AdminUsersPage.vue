<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { z } from 'zod'

import { adminBff } from '@/bff/admin'
import { BffError } from '@/bff/errors'
import PageHeader from '@/components/console/PageHeader.vue'
import CertificationMark from '@/components/identity/CertificationMark.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiDrawer from '@/components/ui/UiDrawer.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import type { AdminRoleOption, AdminUserView } from '@/models'
import { useAuthStore } from '@/stores/auth'

const PAGE_SIZE = 20

const auth = useAuthStore()
const viewer = computed(() => auth.viewer)

const users = ref<AdminUserView[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)
const errorMessage = ref('')
const successMessage = ref('')
const actionError = ref('')

const keyword = ref('')
const roleFilter = ref('')
const roleOptions = ref<AdminRoleOption[]>([])

const editingUserId = ref<string | null>(null)
const pendingUserId = ref<string | null>(null)

const nickname = ref('')
const email = ref('')
const profileErrors = reactive<{ nickname?: string; email?: string }>({})
const profileSubmitError = ref('')
const savingProfile = ref(false)

const walletDirection = ref<'credit' | 'debit'>('credit')
const walletAmountYuan = ref('')
const walletNote = ref('')
const walletErrors = reactive<{ amount?: string; note?: string; submit?: string }>({})
const adjustingWallet = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const editingUser = computed(
  () => users.value.find((user) => user.id === editingUserId.value) ?? null,
)
const editorOpen = computed({
  get: () => editingUserId.value !== null,
  set: (value: boolean) => {
    if (!value) closeEditor()
  },
})
const editorTitle = computed(() =>
  editingUser.value ? `编辑用户 · ${editingUser.value.displayName}` : '编辑用户',
)

const profileSchema = z.object({
  nickname: z.string().trim().min(1, '请输入昵称').max(64, '昵称长度不能超过 64 个字符'),
  email: z
    .string()
    .trim()
    .min(1, '请输入邮箱')
    .max(320, '邮箱长度不能超过 320 个字符')
    .email('请输入有效的邮箱地址'),
})

const walletSchema = z.object({
  amountYuan: z
    .string()
    .trim()
    .min(1, '请输入调整金额')
    .refine((value) => /^\d+(\.\d{1,2})?$/.test(value), '调整金额最多保留两位小数')
    .transform((value) => Number(value))
    .refine((value) => value > 0, '调整金额必须大于 0')
    .refine((value) => Math.round(value * 100) <= 100_000_000, '单次调整金额不能超过 1,000,000 元'),
  note: z.string().trim().min(1, '请填写调整备注').max(120, '备注长度不能超过 120 个字符'),
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
      return '用户不存在或已被移除，请刷新后重试。'
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

async function loadRoles(): Promise<void> {
  try {
    roleOptions.value = await adminBff.listRoles()
  } catch (error) {
    actionError.value = toErrorMessage(error, '角色列表加载失败，请稍后重试。')
  }
}

async function loadUsers(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  errorMessage.value = ''

  try {
    const model = await adminBff.listUsers({
      q: keyword.value.trim() || undefined,
      role: roleFilter.value || undefined,
      page: page.value,
      pageSize: PAGE_SIZE,
    })
    users.value = model.users
    total.value = model.total
    if (model.page > 0) page.value = model.page
  } catch (error) {
    errorMessage.value = toErrorMessage(error, '用户列表加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  page.value = 1
  void loadUsers()
}

function handleRoleFilterChange(): void {
  page.value = 1
  void loadUsers()
}

function changePage(delta: number): void {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  void loadUsers()
}

function resetWalletForm(): void {
  walletDirection.value = 'credit'
  walletAmountYuan.value = ''
  walletNote.value = ''
  walletErrors.amount = undefined
  walletErrors.note = undefined
  walletErrors.submit = undefined
}

function closeEditor(): void {
  editingUserId.value = null
  profileErrors.nickname = undefined
  profileErrors.email = undefined
  profileSubmitError.value = ''
  resetWalletForm()
}

function openEditor(user: AdminUserView): void {
  successMessage.value = ''
  actionError.value = ''
  editingUserId.value = user.id
  nickname.value = user.nickname
  email.value = user.email ?? ''
  profileErrors.nickname = undefined
  profileErrors.email = undefined
  profileSubmitError.value = ''
  resetWalletForm()
}

async function saveProfile(): Promise<void> {
  const user = editingUser.value
  if (!user || savingProfile.value) return
  profileErrors.nickname = undefined
  profileErrors.email = undefined
  profileSubmitError.value = ''

  const parsed = profileSchema.safeParse({
    nickname: nickname.value,
    email: email.value,
  })
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      const field = issue.path[0]
      if (field === 'nickname' && !profileErrors.nickname) profileErrors.nickname = issue.message
      if (field === 'email' && !profileErrors.email) profileErrors.email = issue.message
    }
    return
  }

  savingProfile.value = true
  successMessage.value = ''
  actionError.value = ''
  try {
    await adminBff.updateUser(user.id, {
      nickname: parsed.data.nickname,
      email: parsed.data.email,
    })
    successMessage.value = `已保存 ${parsed.data.nickname} 的资料。`
    closeEditor()
    await loadUsers(false)
  } catch (error) {
    profileSubmitError.value = toErrorMessage(error, '用户资料保存失败，请稍后重试。')
  } finally {
    savingProfile.value = false
  }
}

async function adjustWallet(): Promise<void> {
  const user = editingUser.value
  if (!user || adjustingWallet.value) return
  walletErrors.amount = undefined
  walletErrors.note = undefined
  walletErrors.submit = undefined

  const parsed = walletSchema.safeParse({
    amountYuan: walletAmountYuan.value,
    note: walletNote.value,
  })
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      const field = issue.path[0]
      if (field === 'amountYuan' && !walletErrors.amount) walletErrors.amount = issue.message
      if (field === 'note' && !walletErrors.note) walletErrors.note = issue.message
    }
    return
  }

  adjustingWallet.value = true
  successMessage.value = ''
  actionError.value = ''
  try {
    const updated = await adminBff.walletAdjustment(user.id, {
      direction: walletDirection.value,
      amountCents: Math.round(parsed.data.amountYuan * 100),
      note: parsed.data.note,
    })
    const verb = walletDirection.value === 'credit' ? '增加' : '扣减'
    successMessage.value = `已为 ${user.displayName} ${verb}余额，当前余额 ${updated.balanceLabel}。`
    closeEditor()
    await loadUsers(false)
  } catch (error) {
    walletErrors.submit = toErrorMessage(error, '余额调整失败，请稍后重试。')
  } finally {
    adjustingWallet.value = false
  }
}

async function toggleUserActive(user: AdminUserView): Promise<void> {
  if (pendingUserId.value) return
  const activating = !user.isActive
  pendingUserId.value = user.id
  actionError.value = ''
  successMessage.value = ''

  try {
    await adminBff.updateUser(user.id, { isActive: activating })
    successMessage.value = `已${activating ? '启用' : '停用'} ${user.displayName}。`
    await loadUsers(false)
  } catch (error) {
    actionError.value = toErrorMessage(error, '用户状态更新失败，请稍后重试。')
  } finally {
    pendingUserId.value = null
  }
}

onMounted(async () => {
  await Promise.all([loadRoles(), loadUsers()])
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="admin-page">
      <PageHeader
        eyebrow="ADMIN · USERS"
        title="用户管理"
        description="编辑用户昵称与启用状态，并为用户调整钱包余额；认证由认证审核流程授予。"
      >
        <template #actions>
          <UiButton variant="secondary" size="sm" :loading="loading" @click="loadUsers()">
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

      <section class="admin-panel">
        <form class="admin-toolbar" novalidate @submit.prevent="handleSearch">
          <UiInput
            v-model="keyword"
            class="admin-toolbar__search"
            type="search"
            name="user-search"
            placeholder="搜索用户名、邮箱或姓名"
            aria-label="搜索用户"
          />

          <label class="admin-toolbar__field" for="user-role-filter">
            <span class="admin-toolbar__label">角色</span>
            <select
              id="user-role-filter"
              v-model="roleFilter"
              class="admin-select"
              @change="handleRoleFilterChange"
            >
              <option value="">全部角色</option>
              <option v-for="role in roleOptions" :key="role.key" :value="role.key">
                {{ role.label }}
              </option>
            </select>
          </label>

          <UiButton type="submit" variant="secondary">搜索</UiButton>
        </form>

        <div v-if="loading" class="admin-state" role="status" aria-live="polite">正在加载用户…</div>

        <div v-else-if="errorMessage" class="admin-error">
          <UiAlert variant="error" title="用户加载失败">{{ errorMessage }}</UiAlert>
          <UiButton variant="secondary" size="sm" @click="loadUsers()">重试</UiButton>
        </div>

        <template v-else>
          <div v-if="users.length" class="admin-table__scroll">
            <table class="admin-table">
              <caption class="visually-hidden">
                用户列表
              </caption>
              <thead>
                <tr>
                  <th scope="col">用户</th>
                  <th scope="col">实名</th>
                  <th scope="col">邮箱</th>
                  <th scope="col">认证</th>
                  <th scope="col">角色</th>
                  <th scope="col">余额</th>
                  <th scope="col">状态</th>
                  <th scope="col">创建时间</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="user in users" :key="user.id">
                  <tr class="admin-table__row">
                    <td class="admin-table__cell">
                      <div class="admin-user">
                        <span class="admin-user__avatar" aria-hidden="true">
                          {{ user.initials }}
                        </span>
                        <div class="admin-user__copy">
                          <p class="admin-user__name">{{ user.displayName }}</p>
                          <p class="admin-user__username">@{{ user.username }}</p>
                        </div>
                      </div>
                    </td>
                    <td class="admin-table__cell admin-table__cell--muted">
                      {{ user.fullName ?? '—' }}
                    </td>
                    <td class="admin-table__cell admin-table__cell--muted">
                      {{ user.email ?? '未登记邮箱' }}
                    </td>
                    <td class="admin-table__cell">
                      <CertificationMark
                        v-if="user.certifications.length"
                        :certifications="user.certifications"
                      />
                      <span v-else class="admin-table__cell--muted">未认证</span>
                    </td>
                    <td class="admin-table__cell">
                      <div v-if="user.roles.length" class="admin-user__roles">
                        <UiChip v-for="role in user.roles" :key="role.key" :variant="role.tone">
                          {{ role.label }}
                        </UiChip>
                      </div>
                      <span v-else class="admin-table__cell--muted">未分配角色</span>
                    </td>
                    <td class="admin-table__cell admin-table__cell--money">
                      {{ user.balanceLabel }}
                    </td>
                    <td class="admin-table__cell">
                      <UiChip :variant="user.isActive ? 'success' : 'default'">
                        {{ user.statusLabel }}
                      </UiChip>
                    </td>
                    <td class="admin-table__cell admin-table__cell--nowrap">
                      {{ user.createdAtLabel }}
                    </td>
                    <td class="admin-table__cell">
                      <div class="admin-actions">
                        <UiButton
                          variant="ghost"
                          size="sm"
                          :loading="pendingUserId === user.id"
                          @click="toggleUserActive(user)"
                        >
                          {{ user.isActive ? '停用' : '启用' }}
                        </UiButton>
                        <UiButton variant="ghost" size="sm" @click="openEditor(user)">
                          编辑
                        </UiButton>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <p v-else class="admin-empty">没有符合条件的用户。</p>

          <div class="admin-pagination">
            <span class="admin-pagination__summary">
              共 {{ total }} 位用户 · 第 {{ page }} / {{ totalPages }} 页
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

      <UiDrawer v-model="editorOpen" :title="editorTitle" size="md">
        <template v-if="editingUser">
          <section class="admin-editor__section" aria-label="用户资料">
            <p class="admin-editor__title">用户资料</p>

            <UiAlert
              v-if="profileSubmitError"
              variant="error"
              title="保存失败"
              dismissible
              @close="profileSubmitError = ''"
            >
              {{ profileSubmitError }}
            </UiAlert>

            <div class="admin-editor__grid">
              <UiInput
                v-model="nickname"
                label="昵称"
                name="edit-nickname"
                :maxlength="64"
                :error="profileErrors.nickname"
                :disabled="savingProfile"
              />
              <UiInput
                v-model="email"
                label="邮箱"
                name="edit-email"
                type="email"
                :maxlength="320"
                :error="profileErrors.email"
                :disabled="savingProfile"
              />
            </div>
            <p class="admin-editor__help">
              昵称会展示在订单与申请中；实名、企业、工程师认证由认证审核授予。
            </p>
            <div class="admin-editor__actions">
              <UiButton :loading="savingProfile" @click="saveProfile">保存资料</UiButton>
              <UiButton variant="ghost" :disabled="savingProfile" @click="closeEditor">
                取消
              </UiButton>
            </div>
          </section>

          <section class="admin-editor__section" aria-label="余额调整">
            <p class="admin-editor__title">余额调整</p>
            <p class="admin-editor__help">
              当前余额 {{ editingUser.balanceLabel }}；扣减金额不能超过可用余额。
            </p>

            <UiAlert
              v-if="walletErrors.submit"
              variant="error"
              title="调整失败"
              dismissible
              @close="walletErrors.submit = undefined"
            >
              {{ walletErrors.submit }}
            </UiAlert>

            <form class="admin-editor__grid" novalidate @submit.prevent="adjustWallet">
              <div class="admin-editor__field">
                <label class="admin-editor__label" for="wallet-direction">方向</label>
                <select
                  id="wallet-direction"
                  v-model="walletDirection"
                  class="admin-select"
                  :disabled="adjustingWallet"
                >
                  <option value="credit">增加余额</option>
                  <option value="debit">扣减余额</option>
                </select>
              </div>
              <UiInput
                v-model="walletAmountYuan"
                label="金额 / 元"
                name="wallet-amount"
                inputmode="decimal"
                placeholder="100.00"
                :error="walletErrors.amount"
                :disabled="adjustingWallet"
              />
              <UiInput
                v-model="walletNote"
                label="备注"
                name="wallet-note"
                placeholder="例如：活动奖励 / 退款补偿"
                :maxlength="120"
                :error="walletErrors.note"
                :disabled="adjustingWallet"
              />
              <div class="admin-editor__actions">
                <UiButton type="submit" :loading="adjustingWallet">提交调整</UiButton>
              </div>
            </form>
          </section>
        </template>

        <template #footer>
          <UiButton variant="secondary" @click="closeEditor">关闭</UiButton>
        </template>
      </UiDrawer>
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

.admin-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--primitive-space-3);
}

.admin-toolbar__search {
  flex: 1 1 18rem;
}

.admin-toolbar__field {
  display: flex;
  flex-direction: column;
}

.admin-toolbar__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.admin-select {
  height: 44px;
  min-width: 10rem;
  padding: 0 var(--primitive-space-4);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
}

.admin-select option {
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
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
  min-width: 72rem;
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

.admin-table__row {
  transition: background-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.admin-table__row:hover {
  background-color: var(--color-bg-subtle);
}

.admin-table__cell {
  padding: var(--primitive-space-4);
  color: var(--color-fg);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
  vertical-align: middle;
}

.admin-table__cell--nowrap {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.admin-table__cell--muted {
  color: var(--color-fg-muted);
}

.admin-table__cell--money {
  color: var(--obsidian-gold-text);
  font-family: var(--font-family-heading);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.admin-user {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-3);
}

.admin-user__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex: none;
  color: var(--color-accent);
  background-color: var(--color-accent-subtle);
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-pill);
  font-size: var(--font-size-caption);
}

.admin-user__copy {
  min-width: 0;
}

.admin-user__name {
  color: var(--color-fg-strong);
  font-weight: var(--font-weight-medium);
}

.admin-user__username {
  color: var(--obsidian-tertiary-text);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-caption);
}

.admin-user__roles {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
}

.admin-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
}

.admin-editor__section {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  min-width: 0;
}

.admin-editor__title {
  color: var(--color-fg-strong);
  font-weight: var(--font-weight-medium);
}

.admin-editor__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--primitive-space-3);
}

.admin-editor__field {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.admin-editor__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.admin-editor__help {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  line-height: 1.5;
}

.admin-editor__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
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
</style>
