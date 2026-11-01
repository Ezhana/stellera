<script setup lang="ts">
import { modeLabels, modes, type Mode } from '@ezhana/design-tokens'
import { SYSTEM_MODE } from '@ezhana/theme'

import { themeRegistry } from '../theme/registry'
import { useTheme } from '../theme/useTheme'

const { themes, themeLabels } = themeRegistry
const { state, setTheme, setMode } = useTheme()

type ModeOptionValue = Mode | typeof SYSTEM_MODE

const modeOptions: readonly { value: ModeOptionValue; label: string }[] = [
  ...modes.map((mode) => ({ value: mode, label: modeLabels[mode] })),
  { value: SYSTEM_MODE, label: 'System' },
]

function onThemeChange(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLSelectElement)) return
  const nextTheme = themes.find((candidate) => candidate === target.value)
  if (nextTheme) setTheme(nextTheme)
}
</script>

<template>
  <div class="theme-switcher" role="group" aria-label="Theme settings">
    <div class="theme-field">
      <label class="visually-hidden" for="theme-select">Theme</label>
      <select id="theme-select" class="theme-select" :value="state.theme" @change="onThemeChange">
        <option v-for="theme in themes" :key="theme" :value="theme">
          {{ themeLabels[theme] }}
        </option>
      </select>
    </div>

    <div class="mode-group" role="group" aria-label="Color mode">
      <button
        v-for="option in modeOptions"
        :key="option.value"
        type="button"
        class="mode-button"
        :aria-pressed="state.mode === option.value"
        @click="setMode(option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.theme-switcher {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  max-width: calc(100vw - 2rem);
  padding: 0.25rem;
  font-size: var(--font-size-small);
  background: var(--color-bg);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
}

.theme-field {
  display: flex;
  min-width: 0;
}

.theme-select,
.mode-button {
  font-family: inherit;
  font-size: var(--font-size-small);
  line-height: 1.2;
  color: var(--color-fg-muted);
  border-radius: var(--radius-control);
  transition:
    color var(--motion-duration-fast) var(--motion-easing-standard),
    background-color var(--motion-duration-fast) var(--motion-easing-standard),
    border-color var(--motion-duration-fast) var(--motion-easing-standard),
    box-shadow var(--motion-duration-fast) var(--motion-easing-standard);
}

.theme-select {
  padding: 0.25rem 0.5rem;
  color: var(--color-fg);
  background: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border);
  cursor: pointer;
}

.theme-select:hover {
  border-color: var(--color-accent-border);
}

.theme-select:focus-visible,
.mode-button:focus-visible {
  outline: var(--border-width-strong) solid var(--color-focus-ring);
  outline-offset: 2px;
}

.mode-group {
  display: flex;
  gap: 0.125rem;
  padding: 0.125rem;
  background: var(--color-bg-subtle);
  border-radius: var(--radius-pill);
}

.mode-button {
  padding: 0.25rem 0.625rem;
  background: transparent;
  border: var(--border-width-default) solid transparent;
  cursor: pointer;
}

.mode-button:hover {
  color: var(--color-fg);
  background: var(--color-bg);
}

.mode-button[aria-pressed='true'] {
  color: var(--color-on-accent);
  background: var(--color-accent);
  border-color: var(--color-accent);
}

@media (max-width: 560px) {
  .theme-switcher {
    left: auto;
    right: 1rem;
    flex-direction: column;
    align-items: stretch;
    gap: 0.375rem;
    width: 13.5rem;
    padding: 0.375rem;
  }

  .theme-select {
    width: 100%;
  }

  .mode-button {
    flex: 1;
  }
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}
</style>
