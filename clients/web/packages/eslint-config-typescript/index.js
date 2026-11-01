// Shared TypeScript rules, composed by the React and Vue config packages.
import { defineConfig } from 'eslint/config'
import tseslint from 'typescript-eslint'

import baseConfig from '@ezhana/eslint-config-base'

export default defineConfig([
  ...baseConfig,

  {
    files: ['**/*.{ts,mts,cts,tsx}'],

    extends: [tseslint.configs.recommended],
  },
])
