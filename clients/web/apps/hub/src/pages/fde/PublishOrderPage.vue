<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { z } from 'zod'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import type { CreateOrderInput } from '@/bff/orders'
import PageHeader from '@/components/console/PageHeader.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import { FDE_INDUSTRIES } from '@/models'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const viewer = computed(() => auth.viewer)

const submitting = ref(false)
const formError = ref('')

const title = ref('')
const industry = ref('')
const deliveryDays = ref('')
const priceYuan = ref('')
const description = ref('')

interface FormFieldErrors {
  title?: string
  industry?: string
  deliveryDays?: string
  priceYuan?: string
  description?: string
}

const FORM_FIELDS = ['title', 'industry', 'deliveryDays', 'priceYuan', 'description'] as const
type FormField = (typeof FORM_FIELDS)[number]

const fieldErrors = reactive<FormFieldErrors>({})

const publishSchema = z.object({
  title: z.string().trim().min(1, '请输入任务标题').max(120, '任务标题长度不能超过 120 个字符'),
  industry: z.string().min(1, '请选择行业'),
  deliveryDays: z
    .string()
    .trim()
    .min(1, '请输入交付周期')
    .refine((value) => /^\d+$/.test(value), '交付周期需为整数天数')
    .transform((value) => Number(value))
    .refine((value) => value >= 1 && value <= 365, '交付周期需在 1–365 天之间'),
  priceYuan: z
    .string()
    .trim()
    .min(1, '请输入预算金额')
    .refine((value) => /^\d+(\.\d{1,2})?$/.test(value), '预算金额最多保留两位小数')
    .transform((value) => Number(value))
    .refine((value) => value > 0, '预算金额必须大于 0')
    .refine((value) => value <= 10_000_000, '预算金额不能超过 10,000,000 元'),
  description: z
    .string()
    .trim()
    .min(1, '请填写需求描述')
    .max(4000, '需求描述长度不能超过 4000 个字符'),
})

/** Map the BFF's stable error codes to page copy; the page never inspects HTTP statuses. */
function toErrorMessage(error: unknown): string {
  const fallback = '发布失败，请稍后重试。'
  if (!(error instanceof BffError)) return fallback

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return '当前账号没有发布需求的权限，请联系管理员。'
    case 'not-found':
      return '订单不存在或已被移除，请刷新后重试。'
    case 'invalid-input':
      return error.message || '提交的内容不符合要求，请检查后重试。'
    case 'conflict':
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

function clearFieldErrors(): void {
  for (const field of FORM_FIELDS) fieldErrors[field] = undefined
}

/** Validate the form and convert yuan into integer cents for the BFF. */
function parseForm(): CreateOrderInput | null {
  clearFieldErrors()

  const result = publishSchema.safeParse({
    title: title.value,
    industry: industry.value,
    deliveryDays: deliveryDays.value,
    priceYuan: priceYuan.value,
    description: description.value,
  })

  if (!result.success) {
    for (const issue of result.error.issues) {
      const field = issue.path[0]
      if (typeof field !== 'string' || !(FORM_FIELDS as readonly string[]).includes(field)) continue
      if (!fieldErrors[field as FormField]) fieldErrors[field as FormField] = issue.message
    }
    return null
  }

  return {
    title: result.data.title,
    industry: result.data.industry,
    description: result.data.description,
    deliveryDays: result.data.deliveryDays,
    priceCents: Math.round(result.data.priceYuan * 100),
  }
}

async function handlePublish(): Promise<void> {
  if (submitting.value) return

  formError.value = ''
  const input = parseForm()
  if (!input) return

  submitting.value = true
  try {
    const order = await ordersBff.createOrder(input)
    await router.push({
      name: 'fde-order-detail',
      params: { id: order.id },
      query: { created: '1' },
    })
  } catch (error) {
    formError.value = toErrorMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="publish-page">
      <PageHeader
        eyebrow="PUBLISH ORDER"
        title="发布需求"
        description="需求发布后立即进入订单大厅，预算会进入平台托管，交付完成后结算给工程师。"
      >
        <template #actions>
          <RouterLink class="publish-page__link" :to="{ name: 'fde-published' }">
            <UiIcon name="arrow-left" :size="16" />
            返回我发布的
          </RouterLink>
          <RouterLink class="publish-page__link" :to="{ name: 'fde-hall' }">
            订单大厅
            <UiIcon name="arrow-right" :size="16" />
          </RouterLink>
        </template>
      </PageHeader>

      <UiAlert
        v-if="formError"
        variant="error"
        title="发布失败"
        dismissible
        @close="formError = ''"
      >
        {{ formError }}
      </UiAlert>

      <UiCard elevated padding="lg" class="publish-form">
        <header class="publish-form__header">
          <p class="hub-eyebrow">NEW DEMAND</p>
          <h2 class="publish-form__title">发布新需求</h2>
          <p class="publish-form__description">
            填写需求信息与预算，发布后工程师将在订单大厅申请接单。请尽量写清交付物与验收标准。
          </p>
        </header>

        <form class="publish-form__grid" novalidate @submit.prevent="handlePublish">
          <UiInput
            v-model="title"
            label="任务标题"
            name="title"
            :maxlength="120"
            placeholder="例如：医疗影像数据标注与质检"
            :error="fieldErrors.title"
            :disabled="submitting"
          />

          <div class="publish-form__field">
            <label class="publish-form__label" for="publish-industry">行业</label>
            <select
              id="publish-industry"
              v-model="industry"
              class="publish-form__select"
              :disabled="submitting"
            >
              <option value="" disabled>请选择行业</option>
              <option v-for="item in FDE_INDUSTRIES" :key="item" :value="item">{{ item }}</option>
            </select>
            <p v-if="fieldErrors.industry" class="publish-form__error" role="alert">
              {{ fieldErrors.industry }}
            </p>
          </div>

          <UiInput
            v-model="deliveryDays"
            label="交付周期 / 天"
            name="deliveryDays"
            inputmode="numeric"
            placeholder="7"
            :error="fieldErrors.deliveryDays"
            :disabled="submitting"
          />

          <UiInput
            v-model="priceYuan"
            label="预算 / 元"
            name="priceYuan"
            inputmode="decimal"
            placeholder="86000"
            :error="fieldErrors.priceYuan"
            :disabled="submitting"
          />

          <div class="publish-form__field publish-form__field--wide">
            <label class="publish-form__label" for="publish-description">需求描述</label>
            <textarea
              id="publish-description"
              v-model="description"
              class="publish-form__textarea"
              rows="6"
              :maxlength="4000"
              :disabled="submitting"
              placeholder="说明目标、交付物与验收标准…"
            />
            <p v-if="fieldErrors.description" class="publish-form__error" role="alert">
              {{ fieldErrors.description }}
            </p>
            <p v-else class="publish-form__help">已输入 {{ description.length }} / 4000 字</p>
          </div>

          <div class="publish-form__actions publish-form__field--wide">
            <UiButton type="submit" :loading="submitting">发布需求</UiButton>
            <RouterLink class="publish-form__cancel" :to="{ name: 'fde-published' }">
              取消
            </RouterLink>
          </div>
        </form>
      </UiCard>
    </div>
  </ConsoleLayout>
</template>

<style scoped>
.publish-page {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.publish-page__link {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
  min-height: 44px;
  padding: 0 var(--primitive-space-5);
  color: var(--color-fg);
  background: var(--obsidian-surface-glass);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
  transition: border-color var(--motion-duration-fast) var(--motion-easing-standard);
}

.publish-page__link:hover {
  border-color: var(--color-accent);
  text-decoration: none;
}

.publish-form {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-5);
}

.publish-form__header {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
}

.publish-form__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-medium);
}

.publish-form__description {
  max-width: 62ch;
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.publish-form__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.publish-form__field {
  display: flex;
  flex-direction: column;
}

.publish-form__field--wide {
  grid-column: 1 / -1;
}

.publish-form__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.publish-form__select {
  height: 44px;
  padding: 0 var(--primitive-space-4);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  transition: border-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.publish-form__select:hover:not(:disabled) {
  border-color: var(--color-accent-border);
}

.publish-form__select:focus-visible {
  border-color: var(--color-accent);
}

.publish-form__select option {
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
}

.publish-form__textarea {
  min-height: 148px;
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  line-height: 1.6;
  resize: vertical;
  transition: border-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.publish-form__textarea::placeholder {
  color: var(--color-fg-muted);
}

.publish-form__textarea:hover:not(:disabled) {
  border-color: var(--color-accent-border);
}

.publish-form__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.publish-form__textarea:disabled {
  color: var(--color-fg-muted);
  background-color: var(--color-bg);
  cursor: not-allowed;
}

.publish-form__error {
  margin-top: var(--primitive-space-1);
  color: var(--color-danger);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}

.publish-form__help {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}

.publish-form__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-4);
}

.publish-form__cancel {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.publish-form__cancel:hover {
  color: var(--color-fg);
}

@media (max-width: 760px) {
  .publish-form__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
