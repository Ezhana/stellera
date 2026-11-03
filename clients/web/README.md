# Frontend Monorepo Template

English | [简体中文](./README.zh-CN.md)

> **Where this lives:** this directory is `clients/web` of the Stellera monorepo — one Git
> repository, no nested repo. The pnpm workspace, lockfile and shared configs below are
> self-contained; run the `pnpm` commands below from this directory, or `just web` from the repo
> root. `just up` drives the Docker deploy (`deploy/compose.yaml`). `apps/hub` is the application
> generated from this template (Vue 3 + Vite).

A pnpm workspace starter generated from `frontend-template-source`. The template intentionally
ships **no application by default**: after cloning or using **Use this template**, choose React or
Vue with one command. In Stellera the Vue app `apps/hub` has already been generated on top of it.

```bash
pnpm create:app
```

The command prompts for the framework and app name, scaffolds with the official
`create-vite` / `create-vue` version, applies the theme integration (pass `--no-theme` to keep the
plain official scaffold), then installs the app under `apps/<name>`. The generator itself is the
published `create-ezhana-app` package, pinned as a regular devDependency, so it is versioned and
audited together with the rest of the workspace tooling.
Non-interactive usage:

```bash
pnpm create:app react my-app
pnpm create:app vue my-app

# write thin ESLint/Prettier configs that compose the shared packages
pnpm create:app react my-app --eslint --prettier

# keep the plain official scaffold instead of applying the theme overlay
pnpm create:app react my-app --no-theme

# or configure an existing app later
pnpm create:app configure apps/my-app --eslint --prettier
```

Generated apps keep the official scaffold's own lint/format tooling unless you ask for the shared
config. They share the root commit hooks and CI configuration.

## Requirements

- Node.js 24
- pnpm 12
- Run `pnpm install` once before `pnpm create:app`; it installs the pinned generator together with
  the root tooling
- Network access for the first `pnpm create:app` (the official scaffolders and npm packages are
  downloaded)

## Usage

```bash
pnpm install          # installs root tooling and the pinned create-ezhana-app generator
pnpm create:app       # choose React or Vue, then enter an app name
pnpm dev              # run generated apps
pnpm build            # build generated apps
pnpm lint
pnpm check            # format:check + lint + build
```

You can also use the workspace filters directly:

```bash
pnpm --filter ./apps/my-app dev
pnpm --filter ./apps/my-app build
```

## Lint and format

The lint/format rules live in the shared workspace packages under `packages/`:
`eslint-config-base`, `eslint-config-typescript`, `eslint-config-react`, `eslint-config-vue` and
`prettier-config`. The root `eslint.config.mjs` imports `@ezhana/eslint-config-base` and the root
`prettier.config.mjs` re-exports `@ezhana/prettier-config`, so a rule change in `packages/` applies
to the workspace root.

By default `create:app` leaves the scaffold's tooling untouched: a React app keeps the Oxlint config
created by Vite, and a Vue app has no lint/format setup. To write the shared config into an app,
either pass `--eslint` / `--prettier` when creating it or run:

```bash
pnpm create:app configure apps/my-app --eslint --prettier
```

`configure` writes thin configs: the app `eslint.config.mjs` imports
`@ezhana/eslint-config-<framework>` (with an extension point for app-specific overrides) and the app
`prettier.config.mjs` re-exports `@ezhana/prettier-config`. It adds the config packages to the app as
`workspace:*` dependencies with `pnpm add -D`. It does not delete Oxlint or rewrite `package.json`
scripts, so update those yourself if you want `pnpm lint` to run ESLint.

Change rules for every app in the matching `packages/eslint-config-*/index.js` (or
`packages/prettier-config/index.js`), or add overrides in the individual app config.

## Packages

`packages/` contains the shared lint/format config packages (the five config packages described
above). They are workspace packages, not published npm dependencies: the root and app configs
resolve them through the workspace, so keep the directory and the packages.

Add your own shared packages alongside them:

- create `packages/<name>` with a `package.json`, `src/` and a build script;
- reference it from an app with `"workspace:*"`;
- run `pnpm build:packages` before `pnpm build` (the config packages have no build step and are
  skipped).

See [`packages/README.md`](packages/README.md).

The published `@ezhana/*` theme and token packages are regular npm dependencies, not linked
workspace sources.

## Theming

Generated apps consume published design tokens, theme packages and the theme runtime from npm. The
stylesheets are imported in each app entry file; no local token build step is required.

- `@ezhana/design-tokens` ships the core token scale, the semantic contract and the default theme.
- `@ezhana/design-theme-ocean`, `@ezhana/design-theme-cerulean` and `@ezhana/design-theme-quest` are
  standalone theme packages, one package per theme. QuestUI is dark-only, so the registry/runtime
  support themes that declare a subset of the app's color modes.
- `@ezhana/theme` manages the theme and color-mode state.
- The color mode follows the operating system by default (`prefers-color-scheme`).
- `data-theme` selects the theme; `data-color-mode` is written only for an explicit color mode.
- A theme switcher is generated into both React and Vue apps.
- Pass `--no-theme` when creating an app to skip the overlay: no theme runtime, switcher or
  `@ezhana` theme dependencies are added.

Each app registers its themes in `src/theme/registry.ts` and derives `AppTheme` from that registry, so
the switcher and the theme manager always match the installed theme packages:

```ts
import { defaultThemeDefinition } from '@ezhana/design-tokens'
import { theme as cerulean } from '@ezhana/design-theme-cerulean'
import { theme as ocean } from '@ezhana/design-theme-ocean'
import { defineThemeRegistry } from '@ezhana/theme'

export const themeRegistry = defineThemeRegistry([defaultThemeDefinition, ocean, cerulean])
export type AppTheme = (typeof themeRegistry.themes)[number]
```

To add a theme, install its package in the app, import its stylesheet in the entry file and add its
`theme` export to `defineThemeRegistry([...])`. If the theme supports fewer color modes than the
app (for example a dark-only theme), also pass `themeModes: themeRegistry.themeModes` to
`createThemeManager` so the resolved mode is clamped to a supported one. Theme packages export `./style` (core stylesheet,
the theme's fonts if any and its overrides in one import), `./theme.css` (overrides only) and
`./standalone.css` (core plus overrides, for setups without a bundler).

See the npm package documentation for the token contract, theme model and runtime API:

- [`@ezhana/design-tokens`](https://www.npmjs.com/package/@ezhana/design-tokens)
- [`@ezhana/theme`](https://www.npmjs.com/package/@ezhana/theme)
- [`@ezhana/design-theme-cerulean`](https://www.npmjs.com/package/@ezhana/design-theme-cerulean)
- [`@ezhana/design-theme-ocean`](https://www.npmjs.com/package/@ezhana/design-theme-ocean)
- [`@ezhana/design-theme-quest`](https://www.npmjs.com/package/@ezhana/design-theme-quest)

## CI

CI is owned by the Stellera monorepo root: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
installs this workspace with `pnpm install --frozen-lockfile` and then runs this project's own pnpm
commands: `pnpm lint`, `pnpm -r --if-present run test`, `pnpm build` and
`pnpm -r --filter "./apps/*" --if-present run type-check`. CI calls these commands directly
instead of going through a root-level task runner. The template's standalone workflow was removed
when the workspace was merged into the monorepo — GitHub only reads the root
`.github/workflows` of a repository.
Equivalent local checks: `pnpm format:check`, `pnpm lint` and `pnpm build`.

## License

MIT
