# @ezhana/prettier-config

> **Shared workspace package.** The workspace root and configured apps re-export it from their
> `prettier.config.mjs`. It is workspace source under `packages/`, not an npm dependency; edit the
> shared options in [`index.js`](./index.js).

Shared Prettier configuration for frontend projects.

## Usage

```js
// prettier.config.mjs
export { default } from '@ezhana/prettier-config'
```

## Include

- Shared Prettier options used by the workspace root and by apps generated in it
