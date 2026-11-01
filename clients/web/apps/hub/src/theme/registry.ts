import { theme as obsidian } from '@ezhana/design-theme-obsidian'
import { defineThemeRegistry } from '@ezhana/theme'

/**
 * Theme registry for the hub app.
 *
 * STELLERA HUB uses Obsidian, the template's Obsidian & Gold business identity: 24K gold on warm
 * near-black obsidian with Inter body copy and Playfair Display headings. The registry contains Obsidian only, so it is both the default and the
 * single available theme. There is no theme switcher UI; `data-theme="obsidian"` is already present on
 * `<html>` in index.html, and the manager keeps it in sync.
 *
 * To add a theme: install its package, add its `theme` export to this array, and pass
 * `themeModes: themeRegistry.themeModes` to the manager (see `src/theme/manager.ts`).
 */
export const themeRegistry = defineThemeRegistry([obsidian])

/** Theme ids available in this app, derived from the registry. */
export type AppTheme = (typeof themeRegistry.themes)[number]
