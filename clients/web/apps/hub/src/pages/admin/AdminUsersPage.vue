<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminBff } from '@/bff/admin'
import { BffError } from '@/bff/errors'
import PageHeader from '@/components/console/PageHeader.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiChip from '@/components/ui/UiChip.vue'
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

const keyword = ref('')
const roleFilter = ref('')
const roleOptions = ref<AdminRoleOption[]>([])

const expandedUserId = ref<string | null>(null)
const selectedRoles = ref<string[]>([])
const roleError = ref('')
const savingRoles = ref(false)
const pendingUserId = ref<string | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

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
    errorMessage.value = toErrorMessage(error, '角色列表加载失败，请稍后重试。')
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

function closeRoleEditor(): void {
  expandedUserId.value = null
  selectedRoles.value = []
  roleError.value = ''
}

function openRoleEditor(user: AdminUserView): void {
  successMessage.value = ''
  roleError.value = ''
  if (expandedUserId.value === user.id) {
    closeRoleEditor()
    return
  }
  expandedUserId.value = user.id
  selectedRoles.value = [...user.roleKeys]
}

function setRole(roleKey: string, checked: boolean): void {
  if (checked) {
    if (!selectedRoles.value.includes(roleKey))
      selectedRoles.value = [...selectedRoles.value, roleKey]
    return
  }
  selectedRoles.value = selectedRoles.value.filter((key) => key !== roleKey)
}

async function saveRoles(user: AdminUserView): Promise<void> {
  if (savingRoles.value) return
  if (selectedRoles.value.length === 0) {
    roleError.value = '至少保留一个角色'
    return
  }

  roleError.value = ''
  successMessage.value = ''
  savingRoles.value = true
  try {
    await adminBff.updateUser(user.id, { roles: selectedRoles.value })
    successMessage.value = `已更新 ${user.displayName} 的角色。`
    closeRoleEditor()
    await loadUsers(false)
  } catch (error) {
    roleError.value = toErrorMessage(error, '角色更新失败，请稍后重试。')
  } finally {
    savingRoles.value = false
  }
}

async function toggleUserActive(user: AdminUserView): Promise<void> {
  if (pendingUserId.value) return
  const activating = !user.isActive
  pendingUserId.value = user.id
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await adminBff.updateUser(user.id, { isActive: activating })
    successMessage.value = `已${activating ? '启用' : '停用'} ${user.displayName}。`
    await loadUsers(false)
  } catch (error) {
    errorMessage.value = toErrorMessage(error, '用户状态更新失败，请稍后重试。')
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
        description="搜索用户、调整角色与启用状态，变更立即生效。"
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
                  <th scope="col">邮箱</th>
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
                      {{ user.email ?? '未登记邮箱' }}
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
                        <UiButton variant="ghost" size="sm" @click="openRoleEditor(user)">
                          {{ expandedUserId === user.id ? '收起角色' : '调整角色' }}
                        </UiButton>
                      </div>
                    </td>
                  </tr>

                  <tr v-if="expandedUserId === user.id" class="admin-table__row--editor">
                    <td class="admin-table__cell" colspan="7">
                      <div class="admin-role-editor">
                        <p class="admin-role-editor__title">调整「{{ user.displayName }}」的角色</p>
                        <div class="admin-role-editor__options">
                          <UiCheckbox
                            v-for="role in roleOptions"
                            :key="role.key"
                            :model-value="selectedRoles.includes(role.key)"
                            :label="role.label"
                            :disabled="savingRoles"
                            @update:model-value="(checked) => setRole(role.key, Boolean(checked))"
                          />
                        </div>
                        <p v-if="roleError" class="admin-role-editor__error" role="alert">
                          {{ roleError }}
                        </p>
                        <div class="admin-role-editor__actions">
                          <UiButton size="sm" :loading="savingRoles" @click="saveRoles(user)">
                            保存角色
                          </UiButton>
                          <UiButton
                            variant="ghost"
                            size="sm"
                            :disabled="savingRoles"
                            @click="closeRoleEditor"
                          >
                            取消
                          </UiButton>
                        </div>
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

.admin-table__row--editor {
  background-color: var(--color-bg-subtle);
}

.admin-role-editor {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-3) var(--primitive-space-2);
}

.admin-role-editor__title {
  color: var(--color-fg-strong);
  font-weight: var(--font-weight-medium);
}

.admin-role-editor__options {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-4);
}

.admin-role-editor__error {
  color: var(--color-danger);
  font-size: var(--font-size-caption);
}

.admin-role-editor__actions {
  display: flex;
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
