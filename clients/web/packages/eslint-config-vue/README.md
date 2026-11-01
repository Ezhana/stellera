# @ezhana/eslint-config-vue

> **Shared workspace package.** Apps configured with `--eslint` import it from their thin
> `eslint.config.mjs`. It is workspace source under `packages/`, not an npm dependency; edit the
> shared rules in [`index.js`](./index.js).

ESLint flat config for Vue and TypeScript projects.

## Usage

```js
// apps/<name>/eslint.config.mjs
import config from '@ezhana/eslint-config-vue'

export default config
```

## Include

- Base and TypeScript rules composed from `@ezhana/eslint-config-base` and
  `@ezhana/eslint-config-typescript`
- Vue 3 flat/recommended rules
- Prettier compatibility
