<script setup lang="ts">
import { ref, useId, useSlots } from 'vue'

import { useDialogOverlay } from './useDialogOverlay'

type UiDrawerSize = 'sm' | 'md' | 'lg'

interface UiDrawerProps {
  title: string
  description?: string
  size?: UiDrawerSize
  closeOnOverlay?: boolean
  closeOnEscape?: boolean
}

const props = withDefaults(defineProps<UiDrawerProps>(), {
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
    <Transition name="ui-drawer">
      <div v-if="open" class="ui-drawer" @click.self="handleOverlayClick">
        <aside
          ref="panelRef"
          class="ui-drawer__panel"
          :class="`ui-drawer__panel--${size}`"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
        >
          <header class="ui-drawer__head">
            <div class="ui-drawer__copy">
              <h2 :id="titleId" class="ui-drawer__title">{{ title }}</h2>
              <p v-if="description" class="ui-drawer__description">{{ description }}</p>
            </div>
            <button
              class="ui-drawer__close"
              type="button"
              aria-label="关闭抽屉"
              @click="open = false"
            >
              ×
            </button>
          </header>

          <div class="ui-drawer__body">
            <slot />
          </div>

          <footer v-if="slots.footer" class="ui-drawer__footer">
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.ui-drawer {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
  background-color: rgb(0 0 0 / 0.62);
  backdrop-filter: blur(3px);
}

.ui-drawer__panel {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background-color: var(--color-surface-elevated);
  border-left: var(--border-width-default) solid var(--obsidian-border-strong);
  box-shadow: var(--obsidian-panel-highlight), var(--shadow-lg);
}

.ui-drawer__panel:focus {
  outline: none;
}

.ui-drawer__panel--sm {
  max-width: 26rem;
}

.ui-drawer__panel--md {
  max-width: 32rem;
}

.ui-drawer__panel--lg {
  max-width: 40rem;
}

.ui-drawer__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-5) var(--primitive-space-5) var(--primitive-space-3);
  border-bottom: var(--border-width-default) solid var(--color-border-subtle);
}

.ui-drawer__copy {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
  min-width: 0;
}

.ui-drawer__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-strong);
}

.ui-drawer__description {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.ui-drawer__close {
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

.ui-drawer__close:hover {
  color: var(--color-fg);
  border-color: var(--obsidian-border-strong);
}

.ui-drawer__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--primitive-space-5);
  padding: var(--primitive-space-5);
  overflow-y: auto;
}

.ui-drawer__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--primitive-space-2);
  padding: var(--primitive-space-4) var(--primitive-space-5);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.ui-drawer-enter-active,
.ui-drawer-leave-active {
  transition: opacity var(--motion-duration-normal) var(--motion-easing-standard);
}

.ui-drawer-enter-active .ui-drawer__panel,
.ui-drawer-leave-active .ui-drawer__panel {
  transition: transform var(--motion-duration-normal) var(--motion-easing-standard);
}

.ui-drawer-enter-from,
.ui-drawer-leave-to {
  opacity: 0;
}

.ui-drawer-enter-from .ui-drawer__panel,
.ui-drawer-leave-to .ui-drawer__panel {
  transform: translateX(100%);
}

@media (max-width: 640px) {
  .ui-drawer__panel {
    max-width: none;
  }
}
</style>
