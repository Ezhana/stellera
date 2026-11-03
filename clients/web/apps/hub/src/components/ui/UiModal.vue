<script setup lang="ts">
import { ref, useId, useSlots } from 'vue'

import { useDialogOverlay } from './useDialogOverlay'

type UiModalSize = 'sm' | 'md'

interface UiModalProps {
  title?: string
  description?: string
  size?: UiModalSize
  closeOnOverlay?: boolean
  closeOnEscape?: boolean
}

const props = withDefaults(defineProps<UiModalProps>(), {
  title: undefined,
  description: undefined,
  size: 'md',
  closeOnOverlay: true,
  closeOnEscape: true,
})

const open = defineModel<boolean>({ default: false })
const slots = useSlots()
const titleId = useId()
const panelRef = ref<HTMLElement | null>(null)

useDialogOverlay(open, panelRef, {
  closeOnEscape: () => props.closeOnEscape,
  onClose: () => {
    open.value = false
  },
})

function handleOverlayClick(): void {
  if (props.closeOnOverlay) open.value = false
}
</script>

<template>
  <Teleport to="body">
    <Transition name="ui-modal">
      <div v-if="open" class="ui-modal" @click.self="handleOverlayClick">
        <div
          ref="panelRef"
          class="ui-modal__panel"
          :class="`ui-modal__panel--${size}`"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="title ? titleId : undefined"
          :aria-label="title ? undefined : '对话框'"
          tabindex="-1"
        >
          <header class="ui-modal__head">
            <div class="ui-modal__copy">
              <h2 v-if="title" :id="titleId" class="ui-modal__title">{{ title }}</h2>
              <p v-if="description" class="ui-modal__description">{{ description }}</p>
            </div>
            <button
              class="ui-modal__close"
              type="button"
              aria-label="关闭弹窗"
              @click="open = false"
            >
              ×
            </button>
          </header>

          <div class="ui-modal__body">
            <slot />
          </div>

          <footer v-if="slots.footer" class="ui-modal__footer">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.ui-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--primitive-space-5);
  background-color: rgb(0 0 0 / 0.62);
  backdrop-filter: blur(3px);
  overflow-y: auto;
}

.ui-modal__panel {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: calc(100vh - 2 * var(--primitive-space-5));
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-surface);
  box-shadow: var(--obsidian-panel-highlight), var(--shadow-lg);
}

.ui-modal__panel:focus {
  outline: none;
}

.ui-modal__panel--sm {
  max-width: 24rem;
}

.ui-modal__panel--md {
  max-width: 32rem;
}

.ui-modal__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-5) var(--primitive-space-5) var(--primitive-space-3);
}

.ui-modal__copy {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
  min-width: 0;
}

.ui-modal__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-strong);
}

.ui-modal__description {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.ui-modal__close {
  flex: none;
  width: 32px;
  height: 32px;
  color: var(--color-fg-muted);
  background: transparent;
  border: var(--border-width-default) solid transparent;
  border-radius: var(--radius-control);
  font-size: var(--font-size-body-lg);
  line-height: 1;
  transition: color var(--motion-duration-fast) var(--motion-easing-standard);
}

.ui-modal__close:hover {
  color: var(--color-fg);
  border-color: var(--obsidian-border-strong);
}

.ui-modal__body {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
  padding: 0 var(--primitive-space-5) var(--primitive-space-5);
  overflow-y: auto;
}

.ui-modal__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--primitive-space-2);
  padding: var(--primitive-space-4) var(--primitive-space-5);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.ui-modal-enter-active,
.ui-modal-leave-active {
  transition: opacity var(--motion-duration-normal) var(--motion-easing-standard);
}

.ui-modal-enter-active .ui-modal__panel,
.ui-modal-leave-active .ui-modal__panel {
  transition:
    transform var(--motion-duration-normal) var(--motion-easing-standard),
    opacity var(--motion-duration-normal) var(--motion-easing-standard);
}

.ui-modal-enter-from,
.ui-modal-leave-to {
  opacity: 0;
}

.ui-modal-enter-from .ui-modal__panel,
.ui-modal-leave-to .ui-modal__panel {
  opacity: 0;
  transform: scale(0.96);
}
</style>
