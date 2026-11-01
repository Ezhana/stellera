/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API 基地址前缀，默认 `/api`；Vite 开发/预览服务器会把 `/api` 代理到本地后端。 */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
