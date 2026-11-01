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

.login-card__footnote {
  padding-top: var(--primitive-space-4);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}
</style>
