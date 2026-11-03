<script setup lang="ts">
import { ref, watch } from 'vue'
import { z } from 'zod'

import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiDrawer from '@/components/ui/UiDrawer.vue'
import type { FdeOrderView } from '@/models'

interface DeliveryApplicationDrawerProps {
  order: FdeOrderView | null
  submitting?: boolean
  error?: string
}

const props = withDefaults(defineProps<DeliveryApplicationDrawerProps>(), {
  submitting: false,
  error: '',
})

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ submit: [message: string] }>()

const message = ref('')
const messageError = ref('')

const deliverySchema = z.string().trim().max(500, '交付说明不能超过 500 个字符')

function reset(): void {
  message.value = ''
  messageError.value = ''
}

watch(open, (isOpen) => {
  if (isOpen) reset()
})

function submit(): void {
  if (props.submitting) return
  messageError.value = ''

  const parsed = deliverySchema.safeParse(message.value)
  if (!parsed.success) {
    messageError.value = parsed.error.issues[0]?.message ?? '交付说明不能超过 500 个字符'
    return
  }

  emit('submit', parsed.data)
}
</script>

<template>
  <UiDrawer
    v-model="open"
    title="申请交付"
    :description="order ? `${order.code} · ${order.title}` : undefined"
    size="md"
  >
    <p class="delivery-drawer__hint">提交后由订单发布者确认交付，确认后托管资金将结算给工程师。</p>

    <UiAlert v-if="error" variant="error" title="提交失败">{{ error }}</UiAlert>

    <div class="delivery-drawer__field">
      <label class="delivery-drawer__label" for="delivery-message">交付说明（可选）</label>
      <textarea
        id="delivery-message"
        v-model="message"
        class="delivery-drawer__textarea"
        name="delivery-message"
        rows="5"
        :maxlength="500"
        :disabled="submitting"
        placeholder="简要说明交付物与验收方式…"
      />
      <p v-if="messageError" class="delivery-drawer__error" role="alert">{{ messageError }}</p>
      <p v-else class="delivery-drawer__help">已输入 {{ message.length }} / 500 字</p>
    </div>

    <template #footer>
      <UiButton variant="secondary" :disabled="submitting" @click="open = false">取消</UiButton>
      <UiButton :loading="submitting" @click="submit">提交交付申请</UiButton>
    </template>
  </UiDrawer>
</template>

<style scoped>
.delivery-drawer__hint {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.delivery-drawer__field {
  display: flex;
  flex-direction: column;
}

.delivery-drawer__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.delivery-drawer__textarea {
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

.delivery-drawer__textarea::placeholder {
  color: var(--color-fg-muted);
}

.delivery-drawer__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.delivery-drawer__textarea:disabled {
  color: var(--color-fg-muted);
  background-color: var(--color-bg);
  cursor: not-allowed;
}

.delivery-drawer__error {
  margin-top: var(--primitive-space-1);
  color: var(--color-danger);
  font-size: var(--font-size-caption);
}

.delivery-drawer__help {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}
</style>
