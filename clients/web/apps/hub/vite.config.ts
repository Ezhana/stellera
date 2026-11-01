import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

/** 本地后端地址：开发与预览服务器都把 /api 代理到这里。 */
const API_PROXY_TARGET = 'http://127.0.0.1:8000'

const apiProxy = {
  '/api': {
    target: API_PROXY_TARGET,
    changeOrigin: true,
    // 订单大厅使用 WebSocket 接收实时订单事件，开发代理必须升级连接。
    ws: true,
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: apiProxy,
  },
  preview: {
    proxy: apiProxy,
  },
})
