# packages/

This directory ships the shared lint/format config packages for this workspace:

```text
packages/
├── eslint-config-base/        # base ESLint flat config (JS rules, browser globals)
├── eslint-config-typescript/  # base + TypeScript rules
├── eslint-config-react/       # TypeScript + React and React Hooks rules
├── eslint-config-vue/         # TypeScript + Vue 3 rules
└── prettier-config/           # shared Prettier options
```

They are **workspace packages**, not published npm dependencies. The root `eslint.config.mjs` and
`prettier.config.mjs` compose them, and apps configured with `pnpm create:app configure --eslint
--prettier` import `@ezhana/eslint-config-<framework>` / `@ezhana/prettier-config` through
`workspace:*` dependencies. Keep this directory and these packages: deleting them breaks the root
and the app lint/format setup.

Themes do not live here: the published `@ezhana/design-theme-*` theme packages are npm dependencies
that themed generated apps install directly (apps created with `--no-theme` do not). Use this
directory for your own shared code, alongside the config packages.

## Changing rules

- Edit `packages/eslint-config-*/index.js` or `packages/prettier-config/index.js`. A rule change
  applies to the workspace root and to every configured app.
- Put app-specific overrides in the app's `eslint.config.mjs` / `prettier.config.mjs`, not here.
- The config packages have no build step, so `pnpm build:packages` skips them.

## Adding a package

1. Create `packages/<your-package>` with:

   ```
   packages/<your-package>/
   ├── package.json
   ├── src/index.ts
   └── tsconfig.json
   ```

   A minimal `package.json`:

   ```json
   {
     "name": "@your-scope/utils",
     "version": "0.1.0",
     "private": true,
     "type": "module",
     "exports": {
       ".": {
         "types": "./dist/index.d.ts",
         "default": "./dist/index.js"
       }
     },
     "files": ["dist"],
     "scripts": {
       "build": "tsc -p tsconfig.json"
     },
     "devDependencies": {
       "typescript": "catalog:"
     }
   }
   ```

2. Add it to an app as a workspace dependency:

   ```json
   {
     "dependencies": {
       "@your-scope/utils": "workspace:*"
     }
   }
   ```

3. Build it before building an app that imports its compiled output:

   ```bash
   pnpm --filter @your-scope/utils build
   # or build all packages:
   pnpm build:packages
   ```

The root `pnpm build` script builds packages before the apps. Your packages are private by default;
add your own release/versioning workflow (for example Changesets) if you want to publish them.

## Conventions

- Keep the config packages in place; all workspace and app lint/format configuration resolves them.
- Keep `type: "module"` and explicit `exports` with `types` and `default` entries.
- Build TypeScript packages to `dist/` and keep `dist/` out of git (already ignored).
- Prefer `workspace:*` for internal dependencies inside this monorepo.
- Do not commit `node_modules/` or build output.
