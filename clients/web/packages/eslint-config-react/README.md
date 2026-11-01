# @ezhana/eslint-config-react

> **Shared workspace package.** Apps configured with `--eslint` import it from their thin
> `eslint.config.mjs`. It is workspace source under `packages/`, not an npm dependency; edit the
> shared rules in [`index.js`](./index.js).

ESLint flat config for React and TypeScript projects.

## Usage

```js
// apps/<name>/eslint.config.mjs
import config from '@ezhana/eslint-config-react'

export default config
```

## Include

- Base and TypeScript rules composed from `@ezhana/eslint-config-base` and
  `@ezhana/eslint-config-typescript`
- React and React Hooks recommended rules
- Prettier compatibility
