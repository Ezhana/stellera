import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { adminBff } from '@/bff/admin'
import { buildAdminUserListModel, buildAdminUserView } from '@/bff/admin/__tests__/fixtures'
import { BffError } from '@/bff/errors'
import { buildViewer } from '@/bff/orders/__tests__/fixtures'
import type { AdminRoleOption } from '@/models'
import AdminUsersPage from '@/pages/admin/AdminUsersPage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/admin', () => ({
  adminBff: {
    listUsers: vi.fn(),
    listRoles: vi.fn(),
    updateUser: vi.fn(),
    walletAdjustment: vi.fn(),
  },
}))

const EmptyView = { template: '<div />' }

const roleOptions: AdminRoleOption[] = [
  { key: 'admin', label: '管理员', tone: 'accent' },
  { key: 'member', label: '会员', tone: 'default' },
  { key: 'realname', label: '实名认证', tone: 'info' },
  { key: 'enterprise', label: '企业', tone: 'accent' },
  { key: 'engineer', label: '工程师', tone: 'success' },
]

const enterpriseUser = buildAdminUserView({
  id: '7',
  username: 'luna',
  nickname: 'Luna Chen',
  displayName: 'Luna Chen',
  fullName: 'Luna Chen',
  email: 'luna@example.com',
  certifications: ['realname', 'enterprise'],
  isActive: true,
  statusLabel: '已启用',
  roleKeys: ['realname', 'enterprise'],
  roles: [
    { key: 'realname', label: '实名认证', tone: 'info' },
    { key: 'enterprise', label: '企业', tone: 'accent' },
  ],
  balanceCents: 1_000_000,
  balanceLabel: '¥10,000',
})

const memberUser = buildAdminUserView({
  id: '8',
  username: 'member',
  nickname: '会员（演示）',
  displayName: '会员（演示）',
  fullName: null,
  email: null,
  certifications: [],
  isActive: false,
  statusLabel: '已停用',
  roleKeys: ['member'],
  roles: [{ key: 'member', label: '会员', tone: 'default' }],
  balanceCents: 0,
  balanceLabel: '¥0',
})

const adminViewer = buildViewer({
  isAdmin: true,
  certifications: [],
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
      { path: '/profile', name: 'profile', component: EmptyView },
      { path: '/profiles/:id', name: 'public-profile', component: EmptyView },
      { path: '/fde/orders/:id', name: 'fde-order-detail', component: EmptyView },
      { path: '/intro', name: 'intro', component: EmptyView },
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
      { path: '/fde/published', name: 'fde-published', component: EmptyView },
      { path: '/fde/assigned', name: 'fde-assigned', component: EmptyView },
      { path: '/fde/applications', name: 'fde-applications', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
      { path: '/admin/users', name: 'admin-users', component: EmptyView },
      { path: '/admin/certifications', name: 'admin-certifications', component: EmptyView },
      { path: '/admin/redeem-codes', name: 'admin-redeem-codes', component: EmptyView },
      { path: '/admin/settings', name: 'admin-settings', component: EmptyView },
    ],
  })
  await router.push('/admin/users')
  await router.isReady()

  const wrapper = mount(AdminUsersPage, {
    global: { plugins: [pinia, router], stubs: { teleport: true } },
  })
  await flushPromises()
  return { wrapper, router }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

async function openEditor(wrapper: VueWrapper): Promise<void> {
  await findButton(wrapper, '编辑')?.trigger('click')
  await flushPromises()
}

describe('AdminUsersPage', () => {
  beforeEach(() => {
    vi.mocked(adminBff.listRoles).mockResolvedValue(roleOptions)
    vi.mocked(adminBff.listUsers).mockResolvedValue(
      buildAdminUserListModel([enterpriseUser, memberUser]),
    )
    vi.mocked(adminBff.updateUser).mockResolvedValue(enterpriseUser)
    vi.mocked(adminBff.walletAdjustment).mockResolvedValue({
      ...enterpriseUser,
      balanceCents: 1_050_000,
      balanceLabel: '¥10,500',
    })
  })

  it('renders users with certification badges, roles, balances and role filter options', async () => {
    const { wrapper } = await mountPage()

    expect(adminBff.listUsers).toHaveBeenCalledWith({
      q: undefined,
      role: undefined,
      page: 1,
      pageSize: 20,
    })
    expect(wrapper.findAll('.admin-table__row')).toHaveLength(2)
    expect(wrapper.text()).toContain('Luna Chen')
    expect(wrapper.text()).toContain('@luna')
    expect(wrapper.text()).toContain('luna@example.com')
    expect(wrapper.text()).toContain('实名认证')
    expect(wrapper.text()).toContain('企业认证')
    expect(wrapper.text()).toContain('未认证')
    expect(wrapper.text()).toContain('会员')
    expect(wrapper.text()).toContain('¥10,000')
    expect(wrapper.text()).toContain('已停用')
    expect(wrapper.text()).toContain('共 2 位用户')
    expect(findButton(wrapper, '调整角色')).toBeUndefined()

    const options = wrapper.findAll('#user-role-filter option').map((node) => node.text())
    expect(options).toEqual(['全部角色', '管理员', '会员', '实名认证', '企业', '工程师'])
    expect(wrapper.find('#edit-certification').exists()).toBe(false)
  })

  it('reloads the first page when searching and filtering by role', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('input[name="user-search"]').setValue('luna')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(adminBff.listUsers).toHaveBeenCalledTimes(2)
    expect(adminBff.listUsers).toHaveBeenLastCalledWith({
      q: 'luna',
      role: undefined,
      page: 1,
      pageSize: 20,
    })

    await wrapper.find('#user-role-filter').setValue('enterprise')
    await flushPromises()

    expect(adminBff.listUsers).toHaveBeenLastCalledWith({
      q: 'luna',
      role: 'enterprise',
      page: 1,
      pageSize: 20,
    })
  })

  it('saves the nickname and email from the drawer editor without editing certifications', async () => {
    vi.mocked(adminBff.updateUser).mockResolvedValue({
      ...enterpriseUser,
      nickname: 'Luna Zhang',
      displayName: 'Luna Zhang',
      email: 'luna.zhang@example.com',
      certifications: ['realname', 'engineer'],
    })
    const { wrapper } = await mountPage()
    await openEditor(wrapper)

    expect(wrapper.text()).toContain('编辑用户 · Luna Chen')
    expect(wrapper.find('input[name="edit-nickname"]').exists()).toBe(true)
    expect(wrapper.find('#edit-certification').exists()).toBe(false)
    expect(wrapper.find('textarea[name="detail-reject-note"]').exists()).toBe(false)

    await wrapper.find('input[name="edit-nickname"]').setValue(' Luna Zhang ')
    await wrapper.find('input[name="edit-email"]').setValue(' luna.zhang@example.com ')
    await findButton(wrapper, '保存资料')?.trigger('click')
    await flushPromises()

    expect(adminBff.updateUser).toHaveBeenCalledWith('7', {
      nickname: 'Luna Zhang',
      email: 'luna.zhang@example.com',
    })
    expect(wrapper.text()).toContain('已保存 Luna Zhang 的资料。')
    expect(adminBff.listUsers).toHaveBeenCalledTimes(2)
    expect(wrapper.find('input[name="edit-nickname"]').exists()).toBe(false)
  })

  it('validates the profile fields before calling the PATCH endpoint', async () => {
    const { wrapper } = await mountPage()
    await openEditor(wrapper)

    await wrapper.find('input[name="edit-nickname"]').setValue('')
    await wrapper.find('input[name="edit-email"]').setValue('not-an-email')
    await findButton(wrapper, '保存资料')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入昵称')
    expect(wrapper.text()).toContain('请输入有效的邮箱地址')
    expect(adminBff.updateUser).not.toHaveBeenCalled()
    expect(wrapper.find('input[name="edit-nickname"]').exists()).toBe(true)
  })

  it('credits a user balance with yuan converted to cents', async () => {
    const { wrapper } = await mountPage()
    await openEditor(wrapper)

    await wrapper.find('input[name="wallet-amount"]').setValue('100.50')
    await wrapper.find('input[name="wallet-note"]').setValue('活动奖励')
    await wrapper.find('form.admin-editor__grid').trigger('submit')
    await flushPromises()

    expect(adminBff.walletAdjustment).toHaveBeenCalledWith('7', {
      direction: 'credit',
      amountCents: 10_050,
      note: '活动奖励',
    })
    expect(wrapper.text()).toContain('已为 Luna Chen 增加余额，当前余额 ¥10,500。')
    expect(adminBff.listUsers).toHaveBeenCalledTimes(2)
    expect(wrapper.find('form.admin-editor__grid').exists()).toBe(false)
  })

  it('debits a user balance and surfaces the backend overdraft conflict', async () => {
    vi.mocked(adminBff.walletAdjustment).mockRejectedValue(
      new BffError('conflict', '扣减金额超过可用余额', { status: 409 }),
    )
    const { wrapper } = await mountPage()
    await openEditor(wrapper)

    await wrapper.find('#wallet-direction').setValue('debit')
    await wrapper.find('input[name="wallet-amount"]').setValue('20000')
    await wrapper.find('input[name="wallet-note"]').setValue('退款')
    await wrapper.find('form.admin-editor__grid').trigger('submit')
    await flushPromises()

    expect(adminBff.walletAdjustment).toHaveBeenCalledWith('7', {
      direction: 'debit',
      amountCents: 2_000_000,
      note: '退款',
    })
    expect(wrapper.text()).toContain('扣减金额超过可用余额')
    expect(adminBff.listUsers).toHaveBeenCalledTimes(1)
  })

  it('validates the balance adjustment amount and note', async () => {
    const { wrapper } = await mountPage()
    await openEditor(wrapper)

    await wrapper.find('form.admin-editor__grid').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入调整金额')
    expect(wrapper.text()).toContain('请填写调整备注')
    expect(adminBff.walletAdjustment).not.toHaveBeenCalled()
  })

  it('toggles a user status through the PATCH endpoint', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '停用')?.trigger('click')
    await flushPromises()

    expect(adminBff.updateUser).toHaveBeenCalledWith('7', { isActive: false })
    expect(wrapper.text()).toContain('已停用 Luna Chen。')
  })
})
