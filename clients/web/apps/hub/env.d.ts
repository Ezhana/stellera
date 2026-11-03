/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API 基地址前缀，默认 `/api`；Vite 开发/预览服务器会把 `/api` 代理到本地后端。 */
  readonly VITE_API_BASE_URL?: string
  /** 模型广场（new-api）地址；留空时使用当前主机 3000 端口。 */
  readonly VITE_MODEL_SQUARE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
