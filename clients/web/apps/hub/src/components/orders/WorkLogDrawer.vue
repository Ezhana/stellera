<script setup lang="ts">
import { ref, watch } from 'vue'
import { z } from 'zod'

import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiDrawer from '@/components/ui/UiDrawer.vue'
import UiInput from '@/components/ui/UiInput.vue'
import type { FdeOrderView } from '@/models'

interface WorkLogDrawerProps {
  order: FdeOrderView | null
  submitting?: boolean
  error?: string
}

const props = withDefaults(defineProps<WorkLogDrawerProps>(), {
  submitting: false,
  error: '',
})

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ submit: [input: { content: string; workedHours: number | null }] }>()

const content = ref('')
const hours = ref('')
const contentError = ref('')
const hoursError = ref('')

const logSchema = z.object({
  content: z
    .string()
    .trim()
    .min(1, '请输入工作日志内容')
    .max(4000, '工作日志内容不能超过 4000 个字符'),
  hours: z
    .string()
    .trim()
    .refine((value) => value === '' || /^\d+(\.\d{1,2})?$/.test(value), '工时需为 0–24 之间的数字')
    .transform((value) => (value === '' ? null : Number(value)))
    .refine((value) => value === null || (value >= 0 && value <= 24), '工时需在 0–24 小时之间'),
})

function reset(): void {
  content.value = ''
  hours.value = ''
  contentError.value = ''
  hoursError.value = ''
}

watch(open, (isOpen) => {
  if (isOpen) reset()
})

function submit(): void {
  if (props.submitting) return
  contentError.value = ''
  hoursError.value = ''

  const parsed = logSchema.safeParse({ content: content.value, hours: hours.value })
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      const field = issue.path[0]
      if (field === 'content' && !contentError.value) contentError.value = issue.message
      if (field === 'hours' && !hoursError.value) hoursError.value = issue.message
    }
    return
  }

  emit('submit', { content: parsed.data.content, workedHours: parsed.data.hours })
}
</script>

<template>
  <UiDrawer
    v-model="open"
    title="提交工作日志"
    :description="order ? `${order.code} · ${order.title}` : undefined"
    size="md"
  >
    <UiAlert v-if="error" variant="error" title="提交失败">{{ error }}</UiAlert>

    <div class="work-log-drawer__field">
      <label class="work-log-drawer__label" for="work-log-content">日志内容</label>
      <textarea
        id="work-log-content"
        v-model="content"
        class="work-log-drawer__textarea"
        name="work-log-content"
        rows="5"
        :maxlength="4000"
        :disabled="submitting"
        placeholder="说明今天完成的交付内容与进展…"
      />
      <p v-if="contentError" class="work-log-drawer__error" role="alert">{{ contentError }}</p>
      <p v-else class="work-log-drawer__help">已输入 {{ content.length }} / 4000 字</p>
    </div>

    <UiInput
      v-model="hours"
      label="工时 / 小时（可选）"
      name="work-log-hours"
      inputmode="decimal"
      placeholder="0–24"
      :error="hoursError"
      :disabled="submitting"
    />

    <template #footer>
      <UiButton variant="secondary" :disabled="submitting" @click="open = false">取消</UiButton>
      <UiButton :loading="submitting" @click="submit">提交日志</UiButton>
    </template>
  </UiDrawer>
</template>

<style scoped>
.work-log-drawer__field {
  display: flex;
  flex-direction: column;
}

.work-log-drawer__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.work-log-drawer__textarea {
  min-height: 128px;
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

.work-log-drawer__textarea::placeholder {
  color: var(--color-fg-muted);
}

.work-log-drawer__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.work-log-drawer__textarea:disabled {
  color: var(--color-fg-muted);
  background-color: var(--color-bg);
  cursor: not-allowed;
}

.work-log-drawer__error {
  margin-top: var(--primitive-space-1);
  color: var(--color-danger);
  font-size: var(--font-size-caption);
}

.work-log-drawer__help {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}
</style>
