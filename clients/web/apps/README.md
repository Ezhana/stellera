# apps/

Applications generated with `pnpm create:app` live here.

This directory is intentionally empty in the template. After cloning, run:

```bash
pnpm create:app
```

and choose React or Vue. The generated app is placed in `apps/<name>` and becomes part of the pnpm
workspace automatically.

## Theming

Apps generated with the theme overlay (the default) wire the published `@ezhana/*` packages together
in `src/theme/`:

- `registry.ts` lists the installed theme packages and derives `AppTheme` from the registry;
- `manager.ts` creates the theme manager from the registry;
- `useTheme.ts` is the React / Vue adapter used by the switcher.

Add a theme by installing its package (for example `@ezhana/design-theme-ocean`), importing its
stylesheet in the entry file and adding its `theme` export to `src/theme/registry.ts`. Create an app
with `--no-theme` to skip the overlay and keep the plain official scaffold.
