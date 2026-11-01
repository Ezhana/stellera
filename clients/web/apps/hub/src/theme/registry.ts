import { defaultThemeDefinition } from '@ezhana/design-tokens'
import { theme as quest } from '@ezhana/design-theme-quest'
import { defineThemeRegistry } from '@ezhana/theme'

/**
 * Theme registry for this app.
 *
 * Every theme package exports a frozen `ThemeDefinition`. `defineThemeRegistry` validates the set
 * (unique ids, non-empty labels, valid mode lists) and freezes the result. Themes may support a
 * subset of the app's color modes; pass `themeModes: themeRegistry.themeModes` to the theme manager
 * when you add such a theme. The registry is the single source of truth for the theme switcher and
 * the theme manager.
 *
 * To add a theme: install its package and add its `theme` export to this array.
 */
export const themeRegistry = defineThemeRegistry([defaultThemeDefinition, quest])

/** Theme ids available in this app, derived from the registry. */
export type AppTheme = (typeof themeRegistry.themes)[number]
