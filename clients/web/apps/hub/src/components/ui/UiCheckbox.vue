<script setup lang="ts">
import { computed, useId } from 'vue'

interface UiCheckboxProps {
  id?: string
  label?: string
  disabled?: boolean
  name?: string
}

const props = withDefaults(defineProps<UiCheckboxProps>(), {
  id: undefined,
  label: undefined,
  disabled: false,
  name: undefined,
})

const model = defineModel<boolean>({ default: false })
const generatedId = useId()
const inputId = computed(() => props.id ?? generatedId)
</script>

<template>
  <label class="ui-checkbox" :class="{ 'ui-checkbox--disabled': disabled }">
    <input
      :id="inputId"
      v-model="model"
      class="ui-checkbox__input"
      type="checkbox"
      :name="name"
      :disabled="disabled"
    />
    <span class="ui-checkbox__box" aria-hidden="true">
      <svg class="ui-checkbox__check" viewBox="0 0 12 12" fill="none">
        <path d="M2 6.2 4.8 9 10 3.2" stroke="currentColor" stroke-width="2" />
      </svg>
    </span>
    <span v-if="label || $slots.default" class="ui-checkbox__label">
      <slot>{{ label }}</slot>
    </span>
  </label>
</template>

<style scoped>
.ui-checkbox {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.ui-checkbox--disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Visually hidden but still focusable so the native checkbox keeps its semantics. */
.ui-checkbox__input {
  position: absolute;
  width: 20px;
  height: 20px;
  margin: 0;
  opacity: 0;
}

.ui-checkbox__box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex: none;
  color: var(--color-on-accent);
  background-color: var(--color-surface);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-small);
  transition:
    background-color var(--motion-duration-normal) var(--motion-easing-standard),
    border-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.ui-checkbox__input:hover + .ui-checkbox__box {
  border-color: var(--color-accent);
}

.ui-checkbox__input:focus-visible + .ui-checkbox__box {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.ui-checkbox__input:checked + .ui-checkbox__box {
  background-color: var(--color-accent);
  border-color: transparent;
}

.ui-checkbox__check {
  width: 12px;
  height: 12px;
  opacity: 0;
  transition: opacity var(--motion-duration-fast) var(--motion-easing-standard);
}

.ui-checkbox__input:checked + .ui-checkbox__box .ui-checkbox__check {
  opacity: 1;
}

.ui-checkbox__label {
  margin-left: var(--primitive-space-2);
  color: var(--color-fg);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
}
</style>
