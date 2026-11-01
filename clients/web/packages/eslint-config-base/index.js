// Shared ESLint base rules: the workspace root and the framework config packages compose them.
import js from '@eslint/js'
import eslintConfigPrettier from 'eslint-config-prettier/flat'
import globals from 'globals'
import { defineConfig } from 'eslint/config'

export const prettierConfig = eslintConfigPrettier

export default defineConfig([
  {
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/coverage/**',
      '**/.vite/**',
      '**/.next/**',
      '**/.nuxt/**',
    ],
  },

  {
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },

    rules: {
      'no-console': 'warn',
      'no-debugger': 'warn',
      'no-var': 'error',
      'prefer-const': 'error',
      eqeqeq: ['error', 'always'],
    },
  },

  {
    files: ['**/*.{js,mjs,cjs}'],
    extends: [js.configs.recommended],
  },
])
