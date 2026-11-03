import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { adminBff } from '@/bff/admin'
import { buildAdminSettingsModel } from '@/bff/admin/__tests__/fixtures'
import { buildViewer } from '@/bff/orders/__tests__/fixtures'
import AdminSettingsPage from '@/pages/admin/AdminSettingsPage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/admin', () => ({
  adminBff: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
  },
}))

const EmptyView = { template: '<div />' }

const adminViewer = buildViewer({
  isAdmin: true,
  roles: [{ key: 'admin', label: '管理员', tone: 'accent' }],
  capabilities: {
    publishOrder: true,
    applyOrder: true,
    submitOrderLog: true,
    viewWallet: true,
    redeemCode: true,
    manageAdmin: true,
  },
})

async function mountPage(): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.$patch({
    session: { viewer: adminViewer, remember: false, authenticatedAt: '2026-11-01T00:00:00.000Z' },
    status: 'authenticated',
  })

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: EmptyView },
      { path: '/intro', name: 'intro', component: EmptyView },
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
      { path: '/fde/published', name: 'fde-published', component: EmptyView },
      { path: '/fde/assigned', name: 'fde-assigned', component: EmptyView },
      { path: '/fde/applications', name: 'fde-applications', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
      { path: '/admin/users', name: 'admin-users', component: EmptyView },
      { path: '/admin/redeem-codes', name: 'admin-redeem-codes', component: EmptyView },
      { path: '/admin/settings', name: 'admin-settings', component: EmptyView },
    ],
  })
  await router.push('/admin/settings')
  await router.isReady()

  const wrapper = mount(AdminSettingsPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('AdminSettingsPage', () => {
  beforeEach(() => {
    vi.mocked(adminBff.getSettings).mockResolvedValue(buildAdminSettingsModel())
    vi.mocked(adminBff.updateSettings).mockResolvedValue(
      buildAdminSettingsModel([
        ...buildAdminSettingsModel()
          .settings.slice(0, 1)
          .map((setting) => ({
            ...setting,
            value: 'STELLERA HUB',
          })),
        ...buildAdminSettingsModel().settings.slice(1),
      ]),
    )
  })

  it('loads the three whitelisted settings and the online-recharge status', async () => {
    const { wrapper } = await mountPage()

    expect(adminBff.getSettings).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('平台名称')
    expect(wrapper.text()).toContain('客服联系方式')
    expect(wrapper.text()).toContain('充值说明')
    expect(wrapper.text()).toContain('未开放（接入支付渠道后开启）')

    const platformInput = wrapper.find('input[name="setting-platform_name"]')
    expect((platformInput.element as HTMLInputElement).value).toBe('STELLERA')
    expect(wrapper.find('textarea#setting-wallet_recharge_note').exists()).toBe(true)
    expect(wrapper.text()).toContain('最后更新')
  })

  it('saves the edited values through the admin BFF', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('input[name="setting-platform_name"]').setValue('STELLERA HUB')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(adminBff.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        platform_name: 'STELLERA HUB',
        support_contact: '客服微信：stellera-support',
        wallet_recharge_note: '在线充值暂未开放。',
      }),
    )
    expect(wrapper.text()).toContain('系统设置已保存')
  })

  it('edits the multiline recharge note', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('textarea#setting-wallet_recharge_note').setValue('充值请联系客服。')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(adminBff.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ wallet_recharge_note: '充值请联系客服。' }),
    )
  })
})
