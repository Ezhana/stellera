import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PlatformIntroPage from '../PlatformIntroPage.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    viewer: {
      id: '1',
      username: 'admin',
      displayName: '系统管理员',
      email: 'admin@example.com',
      initials: '系统',
      status: 'active',
      statusLabel: '已启用',
      isAdmin: true,
      roles: [{ key: 'admin', label: '管理员', tone: 'accent' }],
      permissionGroups: [],
      permissionCount: 0,
      capabilities: {
        publishOrder: true,
        claimOrder: true,
        submitOrderLog: true,
        completeOrder: true,
        viewWallet: true,
        redeemCode: true,
        manageAdmin: true,
      },
    },
    logout: vi.fn(async () => undefined),
  }),
}))

const EmptyView = { template: '<div />' }

async function mountIntro() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/intro', name: 'intro', component: EmptyView },
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
      { path: '/fde/published', name: 'fde-published', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
      { path: '/admin/users', name: 'admin-users', component: EmptyView },
      { path: '/admin/redeem-codes', name: 'admin-redeem-codes', component: EmptyView },
      { path: '/admin/settings', name: 'admin-settings', component: EmptyView },
      { path: '/login', name: 'login', component: EmptyView },
    ],
  })
  await router.push('/intro')
  await router.isReady()

  const wrapper = mount(PlatformIntroPage, {
    global: { plugins: [pinia, router] },
  })
  return { wrapper, router }
}

describe('PlatformIntroPage', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders the first carousel slide plus the narrative sections', async () => {
    const { wrapper } = await mountIntro()

    expect(wrapper.text()).toContain('让 AI 真正落到业务现场')
    expect(wrapper.text()).toContain('进入订单大厅')
    expect(wrapper.text()).toContain('AI 落地的最后一公里，需要站在现场的人')
    expect(wrapper.text()).toContain('第三方资金托管')
    expect(wrapper.text()).toContain('一条订单，完成一次可信交付')
  })

  it('advances the carousel with the next/previous controls', async () => {
    const { wrapper } = await mountIntro()

    await wrapper.find('[aria-label="下一张"]').trigger('click')
    expect(wrapper.text()).toContain('资金先托管，交付才结算')

    await wrapper.find('[aria-label="上一张"]').trigger('click')
    expect(wrapper.text()).toContain('让 AI 真正落到业务现场')
  })

  it('exposes the order hall entry link', async () => {
    const { wrapper } = await mountIntro()

    const link = wrapper.findAll('a').find((node) => node.text().includes('进入订单大厅'))
    expect(link?.attributes('href')).toBe('/fde/hall')
  })
})
