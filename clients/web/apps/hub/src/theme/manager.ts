import type { Mode } from '@ezhana/design-tokens'
import { createThemeManager } from '@ezhana/theme'

import { themeRegistry, type AppTheme } from './registry'

/**
 * Browser-wide theme singleton.
 *
 * Obsidian is a fixed dark-mode theme (it declares a single `dark` mode), so the manager receives the
 * registry's per-theme mode map and a `dark` default preference. The runtime clamps any saved
 * light/system preference to the mode the theme actually supports.
 */
export const themeManager = createThemeManager<AppTheme, Mode>({
  themes: [...themeRegistry.themes],
  modes: [...themeRegistry.modes],
  themeModes: themeRegistry.themeModes,
  defaultTheme: themeRegistry.defaultTheme,
  defaultMode: 'dark',
})
