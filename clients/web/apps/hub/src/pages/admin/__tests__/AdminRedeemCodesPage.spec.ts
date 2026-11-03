import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { adminBff } from '@/bff/admin'
import {
  buildRedeemCodeBatch,
  buildRedeemCodeListModel,
  buildRedeemCodeView,
} from '@/bff/admin/__tests__/fixtures'
import { buildViewer } from '@/bff/orders/__tests__/fixtures'
import AdminRedeemCodesPage from '@/pages/admin/AdminRedeemCodesPage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/admin', () => ({
  adminBff: {
    listRedeemCodes: vi.fn(),
    createRedeemCodes: vi.fn(),
    updateRedeemCodeStatus: vi.fn(),
  },
}))

const EmptyView = { template: '<div />' }

const activeCode = buildRedeemCodeView({
  id: '3',
  code: 'RDM-AAAA-BBBB-CCCC',
  amountCents: 10_000,
  amountLabel: '¥100',
  status: 'active',
  statusLabel: '可用',
  statusTone: 'success',
  batchNo: 'B-20261101-01',
  expiresAtLabel: '12-01 00:00',
})

const usedCode = buildRedeemCodeView({
  id: '4',
  code: 'RDM-DDDD-EEEE-FFFF',
  amountCents: 50_000,
  amountLabel: '¥500',
  status: 'used',
  statusLabel: '已使用',
  statusTone: 'default',
  batchNo: 'B-20261101-01',
  usedByName: 'Luna Chen',
  usedAtLabel: '11-02 09:00',
  expiresAtLabel: null,
})

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
  await router.push('/admin/redeem-codes')
  await router.isReady()

  const wrapper = mount(AdminRedeemCodesPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

describe('AdminRedeemCodesPage', () => {
  beforeEach(() => {
    vi.mocked(adminBff.listRedeemCodes).mockResolvedValue(
      buildRedeemCodeListModel([activeCode, usedCode]),
    )
    vi.mocked(adminBff.createRedeemCodes).mockResolvedValue(
      buildRedeemCodeBatch(
        [
          buildRedeemCodeView({ id: '11', code: 'RDM-1111-2222-3333' }),
          buildRedeemCodeView({ id: '12', code: 'RDM-4444-5555-6666' }),
        ],
        'B-20261102-02',
      ),
    )
    vi.mocked(adminBff.updateRedeemCodeStatus).mockResolvedValue(
      buildRedeemCodeView({ ...activeCode, status: 'disabled', statusLabel: '已停用' }),
    )
  })

  it('lists codes with status, batch and usage information', async () => {
    const { wrapper } = await mountPage()

    expect(adminBff.listRedeemCodes).toHaveBeenCalledWith({
      status: 'all',
      q: undefined,
      page: 1,
      pageSize: 20,
    })
    expect(wrapper.findAll('.admin-table tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('RDM-AAAA-BBBB-CCCC')
    expect(wrapper.text()).toContain('RDM-DDDD-EEEE-FFFF')
    expect(wrapper.text()).toContain('¥100')
    expect(wrapper.text()).toContain('可用')
    expect(wrapper.text()).toContain('已使用')
    expect(wrapper.text()).toContain('Luna Chen')
    expect(wrapper.text()).toContain('永久有效')
  })

  it('validates the generation form before calling the BFF', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('input[name="redeem-quantity"]').setValue('')
    await wrapper.findAll('form')[0]!.trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入面额')
    expect(wrapper.text()).toContain('请输入生成数量')
    expect(adminBff.createRedeemCodes).not.toHaveBeenCalled()
  })

  it('generates a batch and reports the batch number and count', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('input[name="redeem-amount"]').setValue('100.50')
    await wrapper.find('input[name="redeem-quantity"]').setValue('2')
    await wrapper.find('input[name="redeem-expires"]').setValue('30')
    await wrapper.find('input[name="redeem-note"]').setValue('双十一活动')
    await wrapper.findAll('form')[0]!.trigger('submit')
    await flushPromises()

    expect(adminBff.createRedeemCodes).toHaveBeenCalledWith({
      amountCents: 10_050,
      quantity: 2,
      expiresInDays: 30,
      note: '双十一活动',
    })
    expect(wrapper.text()).toContain('已生成 2 个兑换码')
    expect(wrapper.text()).toContain('B-20261102-02')
    expect(adminBff.listRedeemCodes).toHaveBeenCalledTimes(2)
  })

  it('disables an active code and refreshes the list', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '停用')?.trigger('click')
    await flushPromises()

    expect(adminBff.updateRedeemCodeStatus).toHaveBeenCalledWith('3', 'disabled')
    expect(wrapper.text()).toContain('已停用兑换码 RDM-AAAA-BBBB-CCCC。')
    expect(adminBff.listRedeemCodes).toHaveBeenCalledTimes(2)
  })

  it('does not offer status actions on used codes', async () => {
    const { wrapper } = await mountPage()

    const rows = wrapper.findAll('.admin-table tbody tr')
    expect(rows[1]?.text()).toContain('已使用')
    expect(rows[1]?.findAll('button')).toHaveLength(0)
  })
})
