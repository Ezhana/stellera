<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { z } from 'zod'

import { BffError } from '@/bff/errors'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import UiInput from '@/components/ui/UiInput.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const registerSchema = z
  .object({
    username: z
      .string()
      .trim()
      .min(3, '用户名至少 3 个字符')
      .max(64, '用户名长度不能超过 64 个字符')
      .regex(/^[A-Za-z0-9_.-]+$/, '用户名只能包含字母、数字、下划线、点或短横线'),
    fullName: z.string().trim().min(1, '请输入姓名').max(128, '姓名长度不能超过 128 个字符'),
    email: z
      .string()
      .trim()
      .min(1, '请输入邮箱')
      .max(128, '邮箱长度不能超过 128 个字符')
      .email('请输入有效的邮箱地址'),
    password: z.string().min(8, '密码至少 8 个字符').max(128, '密码长度不能超过 128 个字符'),
    confirmPassword: z.string().min(1, '请再次输入密码'),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: '两次输入的密码不一致',
    path: ['confirmPassword'],
  })

type RegisterField = 'username' | 'fullName' | 'email' | 'password' | 'confirmPassword'
const FIELDS: readonly RegisterField[] = [
  'username',
  'fullName',
  'email',
  'password',
  'confirmPassword',
]

const username = ref('')
const fullName = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const formError = ref('')
const fieldErrors = reactive<Partial<Record<RegisterField, string>>>({})

function clearFieldErrors(): void {
  for (const field of FIELDS) fieldErrors[field] = undefined
}

function validate(): boolean {
  clearFieldErrors()
  const result = registerSchema.safeParse({
    username: username.value.trim(),
    fullName: fullName.value.trim(),
    email: email.value.trim(),
    password: password.value,
    confirmPassword: confirmPassword.value,
  })
  if (result.success) return true

  for (const issue of result.error.issues) {
    const field = issue.path[0]
    if (typeof field !== 'string' || !FIELDS.includes(field as RegisterField)) continue
    if (!fieldErrors[field as RegisterField]) fieldErrors[field as RegisterField] = issue.message
  }
  return false
}

/** Map the BFF's stable error codes to register-page copy; pages never inspect HTTP statuses. */
function toErrorMessage(error: unknown): string {
  if (!(error instanceof BffError)) return '注册失败，请稍后再试。'

  switch (error.code) {
    case 'conflict':
      return '用户名或邮箱已被占用，请更换后重试。'
    case 'invalid-input':
      return error.message || '提交的内容不符合要求，请检查后重试。'
    case 'forbidden':
      return '当前环境不允许自助注册，请联系管理员。'
    case 'network':
      return '无法连接到服务，请检查网络后重试。'
    case 'server':
      return '服务暂时不可用，请稍后再试。'
    case 'malformed-response':
      return '服务返回的数据格式异常，请联系管理员。'
    default:
      return error.message || '注册失败，请稍后再试。'
  }
}

async function handleSubmit(): Promise<void> {
  if (submitting.value) return
  formError.value = ''
  if (!validate()) return

  submitting.value = true
  try {
    await auth.register(
      {
        username: username.value.trim(),
        email: email.value.trim(),
        fullName: fullName.value.trim(),
        password: password.value,
      },
      false,
    )
    await router.replace({ name: 'intro' })
  } catch (error) {
    formError.value = toErrorMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <UiCard elevated padding="lg" class="register-card">
      <header class="register-card__header">
        <p class="register-card__eyebrow hub-eyebrow">CREATE ACCOUNT</p>
        <h1 class="register-card__title">注册控制台账号</h1>
        <p class="register-card__subtitle">注册后可发布需求、申请接单并管理交付订单。</p>
      </header>

      <UiAlert
        v-if="formError"
        class="register-card__alert"
        variant="error"
        title="注册失败"
        dismissible
        @close="formError = ''"
      >
        {{ formError }}
      </UiAlert>

      <form class="register-card__form" novalidate @submit.prevent="handleSubmit">
        <UiInput
          v-model="username"
          label="用户名"
          name="username"
          autocomplete="username"
          placeholder="3–64 位字母、数字、_ . -"
          :maxlength="64"
          :error="fieldErrors.username"
          :disabled="submitting"
        />

        <UiInput
          v-model="fullName"
          label="姓名"
          name="fullName"
          autocomplete="name"
          placeholder="用于订单与申请展示"
          :maxlength="128"
          :error="fieldErrors.fullName"
          :disabled="submitting"
        />

        <UiInput
          v-model="email"
          label="邮箱"
          name="email"
          type="email"
          autocomplete="email"
          placeholder="you@example.com"
          :maxlength="128"
          :error="fieldErrors.email"
          :disabled="submitting"
        />

        <UiInput
          v-model="password"
          label="密码"
          name="password"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          placeholder="至少 8 个字符"
          :maxlength="128"
          :error="fieldErrors.password"
          :disabled="submitting"
        >
          <template #suffix>
            <button
              class="register-card__password-toggle"
              type="button"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              :aria-pressed="showPassword"
              @click="showPassword = !showPassword"
            >
              <UiIcon :name="showPassword ? 'eye-off' : 'eye'" :size="18" />
            </button>
          </template>
        </UiInput>

        <UiInput
          v-model="confirmPassword"
          label="确认密码"
          name="confirmPassword"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          placeholder="再次输入密码"
          :maxlength="128"
          :error="fieldErrors.confirmPassword"
          :disabled="submitting"
        />

        <UiButton class="register-card__submit" block size="lg" type="submit" :loading="submitting">
          {{ submitting ? '正在注册…' : '注册并进入控制台' }}
        </UiButton>
      </form>

      <p class="register-card__footnote">
        已有账号？
        <RouterLink class="register-card__link" :to="{ name: 'login' }">返回登录</RouterLink>
      </p>
    </UiCard>
  </AuthLayout>
</template>

<style scoped>
.register-card {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
}

.register-card__header {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
}

.register-card__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.02em;
}

.register-card__subtitle {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.register-card__form {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.register-card__password-toggle {
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

.register-card__password-toggle:hover {
  color: var(--color-accent);
}

.register-card__submit {
  margin-top: var(--primitive-space-1);
}

.register-card__footnote {
  padding-top: var(--primitive-space-4);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.register-card__link {
  color: var(--color-accent-hover);
  font-weight: var(--font-weight-medium);
}

.register-card__link:hover {
  color: var(--color-accent);
}
</style>
