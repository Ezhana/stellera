<script setup lang="ts">
import { computed, useId, useSlots } from 'vue'

interface UiInputProps {
  id?: string
  label?: string
  type?: 'text' | 'password' | 'email' | 'search'
  name?: string
  autocomplete?: string
  placeholder?: string
  help?: string
  error?: string
  required?: boolean
  disabled?: boolean
  maxlength?: number | string
  inputmode?: 'text' | 'email' | 'numeric' | 'decimal' | 'search' | 'tel' | 'url'
}

const props = withDefaults(defineProps<UiInputProps>(), {
  id: undefined,
  label: undefined,
  type: 'text',
  name: undefined,
  autocomplete: undefined,
  placeholder: undefined,
  help: undefined,
  error: undefined,
  required: false,
  disabled: false,
  maxlength: undefined,
  inputmode: undefined,
})

defineOptions({ inheritAttrs: false })

const model = defineModel<string>({ default: '' })
const slots = useSlots()
const generatedId = useId()

const inputId = computed(() => props.id ?? generatedId)
const hasSuffix = computed(() => Boolean(slots.suffix))
const describedBy = computed(() => {
  if (props.error) return `${inputId.value}-error`
  if (props.help) return `${inputId.value}-help`
  return undefined
})
</script>

<template>
  <div class="ui-field">
    <label v-if="label" class="ui-field__label" :for="inputId">{{ label }}</label>
    <div
      class="ui-input"
      :class="{
        'ui-input--invalid': Boolean(error),
        'ui-input--disabled': disabled,
        'ui-input--with-suffix': hasSuffix,
      }"
    >
      <input
        :id="inputId"
        v-model="model"
        v-bind="$attrs"
        class="ui-input__control"
        :type="type"
        :name="name"
        :autocomplete="autocomplete"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :maxlength="maxlength"
        :inputmode="inputmode"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="describedBy"
      />
      <span v-if="hasSuffix" class="ui-input__suffix">
        <slot name="suffix" />
      </span>
    </div>
    <p v-if="error" :id="`${inputId}-error`" class="ui-field__error" role="alert">
      {{ error }}
    </p>
    <p v-else-if="help" :id="`${inputId}-help`" class="ui-field__help">{{ help }}</p>
  </div>
</template>

<style scoped>
.ui-field {
  display: flex;
  flex-direction: column;
}

.ui-field__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.ui-field__help,
.ui-field__error {
  margin-top: var(--primitive-space-1);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}

.ui-field__help {
  color: var(--color-fg-muted);
}

.ui-field__error {
  color: var(--color-danger);
}

.ui-input {
  position: relative;
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 var(--primitive-space-4);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  transition: border-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.ui-input:hover:not(.ui-input--disabled) {
  border-color: var(--color-accent-border);
}

.ui-input:focus-within {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.ui-input--invalid {
  border-color: var(--color-danger);
}

.ui-input--invalid:focus-within {
  border-color: var(--color-danger);
  outline-color: var(--color-focus-ring);
}

.ui-input--disabled {
  background-color: var(--color-bg);
  border-color: var(--color-border-subtle);
}

.ui-input__control {
  width: 100%;
  height: 100%;
  padding: 0;
  color: var(--color-fg);
  background: transparent;
  border: 0;
  outline: none;
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
}

.ui-input__control::placeholder {
  color: var(--color-fg-muted);
}

/* The wrapper draws the focus ring, so the inner control suppresses its own. */
.ui-input__control:focus-visible {
  outline: none;
}

.ui-input__control:disabled {
  color: var(--color-fg-muted);
  cursor: not-allowed;
}

.ui-input--with-suffix .ui-input__control {
  padding-right: 36px;
}

.ui-input__suffix {
  position: absolute;
  top: 50%;
  right: var(--primitive-space-3);
  display: flex;
  align-items: center;
  transform: translateY(-50%);
}
</style>
