# @ezhana/eslint-config-base

> **Shared workspace package.** The workspace root and the framework config packages compose it. It
> is workspace source under `packages/`, not an npm dependency; edit the shared rules in
> [`index.js`](./index.js). Apps import the package from their thin `eslint.config.mjs`.

Base ESLint flat config for frontend JavaScript projects.

## Usage

```js
// eslint.config.mjs (workspace root)
import config from '@ezhana/eslint-config-base'

export default config
```

The React and Vue config packages extend it, so configured apps normally get these rules through
`@ezhana/eslint-config-react` or `@ezhana/eslint-config-vue`.

## Include

- ESLint recommended rules for JavaScript files
- Browser globals
- Basic JavaScript rules
- Prettier compatibility, exported as `prettierConfig` for the framework configs
