<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminBff } from '@/bff/admin'
import { BffError } from '@/bff/errors'
import PageHeader from '@/components/console/PageHeader.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import type { AdminSettingView } from '@/models'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const viewer = computed(() => auth.viewer)

const settings = ref<AdminSettingView[]>([])
const values = ref<Record<string, string>>({})
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const saveError = ref('')
const successMessage = ref('')

function setValue(key: string, value: string): void {
  values.value = { ...values.value, [key]: value }
}

function handleTextareaInput(key: string, event: Event): void {
  const target = event.target as HTMLTextAreaElement | null
  setValue(key, target?.value ?? '')
}

function settingValue(key: string): string {
  return values.value[key] ?? ''
}

/** Map the BFF's stable error codes to admin copy; the page never inspects HTTP statuses. */
function toErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof BffError)) return fallback

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return '当前账号没有管理员权限，请联系超级管理员。'
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

function applyModel(model: { settings: AdminSettingView[] }): void {
  settings.value = model.settings
  const next: Record<string, string> = {}
  for (const setting of model.settings) next[setting.key] = setting.value
  values.value = next
}

async function loadSettings(): Promise<void> {
  loading.value = true
  errorMessage.value = ''

  try {
    applyModel(await adminBff.getSettings())
  } catch (error) {
    errorMessage.value = toErrorMessage(error, '系统设置加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

async function handleSave(): Promise<void> {
  if (saving.value) return

  saveError.value = ''
  successMessage.value = ''
  saving.value = true

  try {
    applyModel(await adminBff.updateSettings({ ...values.value }))
    successMessage.value = '系统设置已保存，钱包页与导航文案会同步更新。'
  } catch (error) {
    saveError.value = toErrorMessage(error, '系统设置保存失败，请稍后重试。')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadSettings()
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="admin-page">
      <PageHeader
        eyebrow="ADMIN · SETTINGS"
        title="系统设置"
        description="维护平台名称、客服联系方式与钱包充值说明，保存后立即对全站生效。"
      >
        <template #actions>
          <UiButton variant="secondary" size="sm" :loading="loading" @click="loadSettings">
            刷新
          </UiButton>
        </template>
      </PageHeader>

      <UiAlert
        v-if="successMessage"
        variant="success"
        title="保存成功"
        dismissible
        @close="successMessage = ''"
      >
        {{ successMessage }}
      </UiAlert>

      <div v-if="loading" class="admin-state" role="status" aria-live="polite">
        正在加载系统设置…
      </div>

      <div v-else-if="errorMessage" class="admin-error">
        <UiAlert variant="error" title="系统设置加载失败">{{ errorMessage }}</UiAlert>
        <UiButton variant="secondary" size="sm" @click="loadSettings">重试</UiButton>
      </div>

      <template v-else>
        <section class="admin-panel">
          <header class="admin-section-head">
            <h2 class="admin-section-title">可编辑配置</h2>
            <p class="admin-section-hint">仅维护三个白名单配置项。</p>
          </header>

          <UiAlert
            v-if="saveError"
            variant="error"
            title="保存失败"
            dismissible
            @close="saveError = ''"
          >
            {{ saveError }}
          </UiAlert>

          <form class="settings-form" novalidate @submit.prevent="handleSave">
            <div v-for="setting in settings" :key="setting.key" class="settings-field">
              <UiInput
                v-if="!setting.multiline"
                :label="setting.label"
                :name="`setting-${setting.key}`"
                :help="setting.description"
                :model-value="settingValue(setting.key)"
                :disabled="saving"
                @update:model-value="(value) => setValue(setting.key, value)"
              />

              <template v-else>
                <label class="settings-field__label" :for="`setting-${setting.key}`">
                  {{ setting.label }}
                </label>
                <textarea
                  :id="`setting-${setting.key}`"
                  class="settings-field__textarea"
                  rows="4"
                  :value="settingValue(setting.key)"
                  :disabled="saving"
                  @input="handleTextareaInput(setting.key, $event)"
                />
                <p class="settings-field__help">{{ setting.description }}</p>
              </template>

              <p v-if="setting.updatedAtLabel" class="settings-field__updated">
                最后更新：{{ setting.updatedAtLabel }}
              </p>
            </div>

            <div class="settings-form__actions">
              <UiButton type="submit" :loading="saving">保存设置</UiButton>
            </div>
          </form>
        </section>

        <UiCard padding="md" class="settings-info">
          <p class="hub-eyebrow">RUNTIME STATUS</p>
          <h2 class="settings-info__title">运行信息</h2>
          <dl class="settings-info__list">
            <div class="settings-info__item">
              <dt class="settings-info__term">在线充值</dt>
              <dd class="settings-info__value">未开放（接入支付渠道后开启）</dd>
            </div>
            <div class="settings-info__item">
              <dt class="settings-info__term">平台名称</dt>
              <dd class="settings-info__value">{{ settingValue('platform_name') || '—' }}</dd>
            </div>
            <div class="settings-info__item">
              <dt class="settings-info__term">客服联系方式</dt>
              <dd class="settings-info__value">{{ settingValue('support_contact') || '—' }}</dd>
            </div>
          </dl>
        </UiCard>
      </template>
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

.settings-form {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-5);
  max-width: 44rem;
}

.settings-field {
  display: flex;
  flex-direction: column;
}

.settings-field__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.settings-field__textarea {
  min-height: 112px;
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

.settings-field__textarea:hover:not(:disabled) {
  border-color: var(--color-accent-border);
}

.settings-field__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.settings-field__help {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}

.settings-field__updated {
  margin-top: var(--primitive-space-1);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
}

.settings-form__actions {
  display: flex;
  gap: var(--primitive-space-3);
}

.settings-info {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  max-width: 44rem;
}

.settings-info__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
}

.settings-info__list {
  display: flex;
  flex-direction: column;
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.settings-info__item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--primitive-space-2);
  padding: var(--primitive-space-3) 0;
  border-bottom: var(--border-width-default) solid var(--color-border-subtle);
}

.settings-info__term {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.settings-info__value {
  color: var(--color-fg-strong);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  text-align: right;
}
</style>
