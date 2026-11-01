import '@ezhana/design-tokens/css/tokens.css'
import '@ezhana/design-theme-obsidian/style'
import './assets/app.css'
// 副作用导入：创建 Obsidian 主题管理器并把 data-theme / data-color-mode 应用到 <html>。
import './theme/manager'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { router } from './router'

createApp(App).use(createPinia()).use(router).mount('#app')
