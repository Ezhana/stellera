import type { Mode } from '@ezhana/design-tokens'
import { SYSTEM_MODE } from '@ezhana/theme'
import { onScopeDispose, shallowRef } from 'vue'

import { themeManager } from './manager'
import type { AppTheme } from './registry'

/**
 * Vue adapter around the framework-agnostic theme manager.
 *
 * `getState()` returns a frozen, referentially stable snapshot, so a
 * `shallowRef` is enough to keep components in sync. The subscription is tied
 * to the current effect scope and released when the component unmounts.
 */
export function useTheme() {
  const state = shallowRef(themeManager.getState())
  const unsubscribe = themeManager.subscribe((next) => {
    state.value = next
  })
  onScopeDispose(unsubscribe)

  return {
    state,
    setTheme: (theme: AppTheme) => themeManager.setTheme(theme),
    setMode: (mode: Mode | typeof SYSTEM_MODE) => themeManager.setMode(mode),
  }
}
