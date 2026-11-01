import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    /** Document title suffix, e.g. "登录 · STELLERA HUB". */
    title?: string
    /** Route only reachable with an authenticated session. */
    requiresAuth?: boolean
    /** Route only reachable while anonymous (login). */
    publicOnly?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/intro',
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { title: '登录', publicOnly: true },
  },
  {
    // 平台简介：轮播图 + 叙事，作为登录后的默认落地页。
    path: '/intro',
    name: 'intro',
    component: () => import('@/pages/PlatformIntroPage.vue'),
    meta: { title: '平台简介', requiresAuth: true },
  },
  {
    // 旧控制台入口保留为兼容跳转，避免历史链接 404。
    path: '/console',
    redirect: '/intro',
  },
  {
    path: '/fde/hall',
    name: 'fde-hall',
    component: () => import('@/pages/fde/OrderHallPage.vue'),
    meta: { title: '订单大厅', requiresAuth: true },
  },
  {
    path: '/fde/published',
    name: 'fde-published',
    component: () => import('@/pages/fde/PublishedOrdersPage.vue'),
    meta: { title: '我发布的', requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: { title: '页面不存在' },
  },
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.bootstrap()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.publicOnly && auth.isAuthenticated) {
    return { name: 'intro' }
  }

  return true
})

router.afterEach((to) => {
  const title = to.meta.title
  document.title = title ? `${title} · STELLERA HUB` : 'STELLERA HUB'
})
