# @ezhana/eslint-config-typescript

> **Shared workspace package.** The React and Vue config packages compose it. It is workspace source
> under `packages/`, not an npm dependency; edit the shared rules in [`index.js`](./index.js). Apps
> import the package from their thin `eslint.config.mjs`.

ESLint flat config for TypeScript projects.

## Usage

```js
// composed by @ezhana/eslint-config-react / @ezhana/eslint-config-vue
import config from '@ezhana/eslint-config-typescript'

export default config
```

## Include

- Base rules composed from `@ezhana/eslint-config-base`
- TypeScript ESLint recommended rules for TypeScript files
