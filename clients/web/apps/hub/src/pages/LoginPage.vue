<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { z } from 'zod'

import { BffError } from '@/bff/errors'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import UiInput from '@/components/ui/UiInput.vue'
import { DEMO_ACCOUNTS, type DemoAccount } from '@/config/demoAccounts'
import AuthLayout from '@/layouts/AuthLayout.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const loginSchema = z.object({
  username: z.string().trim().min(1, '请输入用户名').max(64, '用户名长度不能超过 64 个字符'),
  password: z.string().min(1, '请输入密码').max(128, '密码长度不能超过 128 个字符'),
})

const username = ref('')
const password = ref('')
const remember = ref(false)
const showPassword = ref(false)
const submitting = ref(false)
const formError = ref('')
const fieldErrors = reactive<{ username?: string; password?: string }>({})

function validate(): boolean {
  fieldErrors.username = undefined
  fieldErrors.password = undefined

  const result = loginSchema.safeParse({
    username: username.value.trim(),
    password: password.value,
  })
  if (result.success) return true

  for (const issue of result.error.issues) {
    const field = issue.path[0]
    if (field === 'username' && !fieldErrors.username) fieldErrors.username = issue.message
    if (field === 'password' && !fieldErrors.password) fieldErrors.password = issue.message
  }
  return false
}

/** Only single-slash internal paths are valid redirect targets (no `//host` or `\\host`). */
function isSafeInternalPath(path: string): boolean {
  return (
    path.startsWith('/') &&
    !path.startsWith('//') &&
    !path.includes('\\') &&
    !path.startsWith('/login')
  )
}

function resolveRedirect(raw: unknown): string {
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && isSafeInternalPath(value) ? value : '/intro'
}

/** Map the BFF's stable error codes to login-page copy; pages never inspect HTTP statuses. */
function toErrorMessage(error: unknown): string {
  if (!(error instanceof BffError)) return '登录失败，请稍后再试。'

  switch (error.code) {
    case 'invalid-credentials':
      return '用户名或密码不正确，请重新输入。'
    case 'forbidden':
      return '该账号已被停用或没有访问权限，请联系管理员。'
    case 'network':
      return '无法连接到服务，请检查网络后重试。'
    case 'server':
      return '服务暂时不可用，请稍后再试。'
    case 'malformed-response':
      return '服务返回的数据格式异常，请联系管理员。'
    case 'session-expired':
      return '登录状态已过期，请重新登录。'
    default:
      return error.message || '登录失败，请稍后再试。'
  }
}

async function handleSubmit(): Promise<void> {
  if (submitting.value) return
  formError.value = ''
  if (!validate()) return

  submitting.value = true
  try {
    await auth.login({ username: username.value.trim(), password: password.value }, remember.value)
    await router.replace(resolveRedirect(route.query.redirect))
  } catch (error) {
    formError.value = toErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

/** 一键填入测试环境演示账号，并清空上一次提交留下的校验错误。 */
function fillDemoAccount(account: DemoAccount): void {
  username.value = account.username
  password.value = account.password
  fieldErrors.username = undefined
  fieldErrors.password = undefined
  formError.value = ''
}
</script>

<template>
  <AuthLayout>
    <UiCard elevated padding="lg" class="login-card">
      <header class="login-card__header">
        <p class="login-card__eyebrow hub-eyebrow">SIGN IN</p>
        <h1 class="login-card__title">登录控制台</h1>
        <p class="login-card__subtitle">使用企业或工程师账号访问 FDE 交付控制台。</p>
      </header>

      <UiAlert
        v-if="formError"
        class="login-card__alert"
        variant="error"
        title="登录失败"
        dismissible
        @close="formError = ''"
      >
        {{ formError }}
      </UiAlert>

      <form class="login-card__form" novalidate @submit.prevent="handleSubmit">
        <UiInput
          v-model="username"
          label="用户名"
          name="username"
          autocomplete="username"
          placeholder="请输入企业账号"
          :maxlength="64"
          :error="fieldErrors.username"
          :disabled="submitting"
        />

        <UiInput
          v-model="password"
          label="密码"
          name="password"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="current-password"
          placeholder="请输入密码"
          :maxlength="128"
          :error="fieldErrors.password"
          :disabled="submitting"
        >
          <template #suffix>
            <button
              class="login-card__password-toggle"
              type="button"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              :aria-pressed="showPassword"
              @click="showPassword = !showPassword"
            >
              <UiIcon :name="showPassword ? 'eye-off' : 'eye'" :size="18" />
            </button>
          </template>
        </UiInput>

        <div class="login-card__options">
          <UiCheckbox v-model="remember">保持登录</UiCheckbox>
          <span class="login-card__options-hint">建议仅在受信任设备上使用</span>
        </div>

        <UiButton class="login-card__submit" block size="lg" type="submit" :loading="submitting">
          {{ submitting ? '正在验证…' : '登录' }}
        </UiButton>
      </form>

      <section class="login-card__demo" aria-labelledby="login-demo-title">
        <div class="login-card__demo-header">
          <h2 id="login-demo-title" class="login-card__demo-title">测试环境演示账号</h2>
          <p class="login-card__demo-hint">点击填入 · 仅测试环境</p>
        </div>
        <ul class="login-card__demo-list">
          <li v-for="account in DEMO_ACCOUNTS" :key="account.username">
            <button
              class="login-card__demo-account"
              type="button"
              :data-demo-account="account.username"
              :aria-label="`填入演示账号：${account.role}（${account.scope}），用户名 ${account.username}，密码 ${account.password}`"
              :title="`${account.role}（${account.scope}）：${account.username} / ${account.password}`"
              :disabled="submitting"
              @click="fillDemoAccount(account)"
            >
              <span class="login-card__demo-role">{{ account.role }}</span>
              <span class="login-card__demo-username">{{ account.username }}</span>
              <span class="login-card__demo-password">{{ account.password }}</span>
            </button>
          </li>
        </ul>
      </section>

      <p class="login-card__footnote">账号由管理员分配；如需开通权限，请联系 IT 管理员。</p>
    </UiCard>
  </AuthLayout>
</template>

<style scoped>
.login-card {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
}

.login-card__header {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
}

.login-card__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.02em;
}

.login-card__subtitle {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.login-card__form {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.login-card__password-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  color: var(--color-fg-muted);
  background: transparent;
  border: 0;
  border-radius: var(--radius-small);
  transition: color var(--motion-duration-normal) var(--motion-easing-standard);
}

.login-card__password-toggle:hover {
  color: var(--color-accent);
}

.login-card__options {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-2);
}

.login-card__options-hint {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.login-card__submit {
  margin-top: var(--primitive-space-1);
}

/* 测试环境演示账号：低频辅助区块，用极细分割线与表单主体区分。 */
.login-card__demo {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  padding-top: var(--primitive-space-4);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.login-card__demo-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--primitive-space-1) var(--primitive-space-2);
}

.login-card__demo-title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
}

.login-card__demo-hint {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.login-card__demo-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: var(--primitive-space-2);
}

.login-card__demo-account {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  padding: var(--primitive-space-2) var(--primitive-space-3);
  text-align: left;
  background: var(--obsidian-surface-glass);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-control);
  transition:
    background-color var(--motion-duration-fast) var(--motion-easing-standard),
    border-color var(--motion-duration-fast) var(--motion-easing-standard);
}

.login-card__demo-account:hover:not(:disabled) {
  background: var(--obsidian-accent-soft-hover);
  border-color: var(--color-accent-border);
}

.login-card__demo-account:disabled {
  opacity: 0.6;
}

.login-card__demo-role {
  color: var(--obsidian-gold-text);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.login-card__demo-username {
  color: var(--color-fg);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-code);
  line-height: 1.2;
}

.login-card__demo-password {
  color: var(--color-fg-muted);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-code);
  line-height: 1.2;
}

.login-card__footnote {
  padding-top: var(--primitive-space-4);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}

/* 移动端：卡片至少两列，用户名/密码保持单行可读。 */
@media (max-width: 480px) {
  .login-card__demo-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
