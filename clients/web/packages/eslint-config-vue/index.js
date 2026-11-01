// Shared Vue rules: base rules + TypeScript + Vue, used by generated apps.
import { defineConfig } from 'eslint/config'
import eslintPluginVue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import tseslint from 'typescript-eslint'

import { prettierConfig } from '@ezhana/eslint-config-base'

import typescriptConfig from '@ezhana/eslint-config-typescript'

export default defineConfig([
  ...typescriptConfig,

  ...eslintPluginVue.configs['flat/recommended'],

  {
    files: ['**/*.vue'],

    languageOptions: {
      parser: vueParser,

      parserOptions: {
        parser: tseslint.parser,
        ecmaVersion: 'latest',
        sourceType: 'module',
      },
    },

    rules: {
      'vue/multi-word-component-names': 'off',
    },
  },

  prettierConfig,
])
