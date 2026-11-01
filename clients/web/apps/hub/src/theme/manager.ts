import type { Mode } from '@ezhana/design-tokens'
import { createThemeManager } from '@ezhana/theme'

import { themeRegistry, type AppTheme } from './registry'

/**
 * Browser-wide theme singleton.
 *
 * The registry is the single source of truth for the available themes, so a
 * theme added in `src/theme/registry.ts` automatically shows up in the
 * switcher UI.
 */
export const themeManager = createThemeManager<AppTheme, Mode>({
  themes: [...themeRegistry.themes],
  modes: [...themeRegistry.modes],
  defaultTheme: themeRegistry.defaultTheme,
})
