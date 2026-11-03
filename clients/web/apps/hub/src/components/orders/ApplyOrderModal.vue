<script setup lang="ts">
import { ref, watch } from 'vue'

import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiModal from '@/components/ui/UiModal.vue'
import type { FdeOrderView } from '@/models'

interface ApplyOrderModalProps {
  order: FdeOrderView | null
  submitting?: boolean
  error?: string
}

const props = withDefaults(defineProps<ApplyOrderModalProps>(), {
  submitting: false,
  error: '',
})

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ confirm: [message: string] }>()

const message = ref('')

watch(open, (isOpen) => {
  if (isOpen) message.value = ''
})

function clearMessage(): void {
  message.value = ''
}

function cancel(): void {
  if (props.submitting) return
  open.value = false
}

function confirm(): void {
  if (props.submitting) return
  emit('confirm', message.value.trim())
}
</script>

<template>
  <UiModal v-model="open" title="申请接单" size="md">
    <div v-if="order" class="apply-order">
      <dl class="apply-order__facts">
        <div class="apply-order__fact">
          <dt>订单标题</dt>
          <dd>{{ order.title }}</dd>
        </div>
        <div class="apply-order__fact">
          <dt>订单编号</dt>
          <dd class="apply-order__mono">{{ order.code }}</dd>
        </div>
        <div class="apply-order__fact">
          <dt>订单价格</dt>
          <dd class="apply-order__price">{{ order.priceLabel }}</dd>
        </div>
        <div class="apply-order__fact">
          <dt>发布方</dt>
          <dd>{{ order.publisherName }}</dd>
        </div>
      </dl>

      <p class="apply-order__hint">申请接单后需发布者审批，通过后订单会出现在「我接到的」。</p>

      <UiAlert v-if="error" variant="error" title="申请失败">{{ error }}</UiAlert>

      <div class="apply-order__field">
        <label class="apply-order__label" for="apply-order-message">申请备注（可选）</label>
        <textarea
          id="apply-order-message"
          v-model="message"
          class="apply-order__textarea"
          name="apply-message"
          rows="4"
          :maxlength="500"
          :disabled="submitting"
          placeholder="介绍相关经验或交付计划，便于发布者审批…"
        />
        <p class="apply-order__help">已输入 {{ message.length }} / 500 字</p>
      </div>
    </div>
    <p v-else class="apply-order__hint">订单信息加载中…</p>

    <template #footer>
      <UiButton variant="ghost" :disabled="submitting" @click="clearMessage">清空</UiButton>
      <UiButton variant="secondary" :disabled="submitting" @click="cancel">取消</UiButton>
      <UiButton :loading="submitting" :disabled="!order" @click="confirm">确认申请</UiButton>
    </template>
  </UiModal>
</template>

<style scoped>
.apply-order {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.apply-order__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-4);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.apply-order__fact {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.apply-order__fact dt {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.apply-order__fact dd {
  color: var(--color-fg);
  font-size: var(--font-size-small);
  overflow-wrap: anywhere;
}

.apply-order__mono {
  font-family: var(--font-family-mono);
  font-size: var(--font-size-code);
}

.apply-order__price {
  color: var(--obsidian-gold-text);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-body);
  font-variant-numeric: tabular-nums;
}

.apply-order__hint {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}

.apply-order__field {
  display: flex;
  flex-direction: column;
}

.apply-order__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.apply-order__textarea {
  min-height: 96px;
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

.apply-order__textarea::placeholder {
  color: var(--color-fg-muted);
}

.apply-order__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.apply-order__textarea:disabled {
  color: var(--color-fg-muted);
  background-color: var(--color-bg);
  cursor: not-allowed;
}

.apply-order__help {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}
</style>
