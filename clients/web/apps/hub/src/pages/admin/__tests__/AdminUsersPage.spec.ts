import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { adminBff } from '@/bff/admin'
import { buildAdminUserListModel, buildAdminUserView } from '@/bff/admin/__tests__/fixtures'
import { buildViewer } from '@/bff/orders/__tests__/fixtures'
import type { AdminRoleOption } from '@/models'
import AdminUsersPage from '@/pages/admin/AdminUsersPage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/admin', () => ({
  adminBff: {
    listUsers: vi.fn(),
    listRoles: vi.fn(),
    updateUser: vi.fn(),
  },
}))

const EmptyView = { template: '<div />' }

const roleOptions: AdminRoleOption[] = [
  { key: 'admin', label: '管理员', tone: 'accent' },
  { key: 'operator', label: '运营', tone: 'info' },
  { key: 'enterprise', label: '企业', tone: 'accent' },
]

const enterpriseUser = buildAdminUserView({
  id: '7',
  username: 'luna',
  displayName: 'Luna Chen',
  email: 'luna@example.com',
  isActive: true,
  statusLabel: '已启用',
  roleKeys: ['enterprise'],
  roles: [{ key: 'enterprise', label: '企业', tone: 'accent' }],
  balanceCents: 1_000_000,
  balanceLabel: '¥10,000',
})

const disabledUser = buildAdminUserView({
  id: '8',
  username: 'kane',
  displayName: 'Kane',
  email: null,
  isActive: false,
  statusLabel: '已停用',
  roleKeys: ['operator'],
  roles: [{ key: 'operator', label: '运营', tone: 'info' }],
  balanceCents: 0,
  balanceLabel: '¥0',
})

const adminViewer = buildViewer({
  isAdmin: true,
  roles: [{ key: 'admin', label: '管理员', tone: 'accent' }],
  capabilities: {
    publishOrder: true,
    claimOrder: true,
    submitOrderLog: true,
    completeOrder: true,
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
      { path: '/wallet', name: 'wallet', component: EmptyView },
      { path: '/admin/users', name: 'admin-users', component: EmptyView },
      { path: '/admin/redeem-codes', name: 'admin-redeem-codes', component: EmptyView },
      { path: '/admin/settings', name: 'admin-settings', component: EmptyView },
    ],
  })
  await router.push('/admin/users')
  await router.isReady()

  const wrapper = mount(AdminUsersPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

describe('AdminUsersPage', () => {
  beforeEach(() => {
    vi.mocked(adminBff.listRoles).mockResolvedValue(roleOptions)
    vi.mocked(adminBff.listUsers).mockResolvedValue(
      buildAdminUserListModel([enterpriseUser, disabledUser]),
    )
    vi.mocked(adminBff.updateUser).mockResolvedValue(enterpriseUser)
  })

  it('renders the user rows, roles and balances', async () => {
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
    expect(wrapper.text()).toContain('企业')
    expect(wrapper.text()).toContain('¥10,000')
    expect(wrapper.text()).toContain('已停用')
    expect(wrapper.text()).toContain('共 2 位用户')
  })

  it('reloads the first page when searching', async () => {
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
  })

  it('saves an updated role set from the inline editor', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '调整角色')?.trigger('click')
    await flushPromises()

    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes).toHaveLength(3)
    expect(wrapper.text()).toContain('调整「Luna Chen」的角色')

    await checkboxes[0]!.setValue(true)
    await findButton(wrapper, '保存角色')?.trigger('click')
    await flushPromises()

    expect(adminBff.updateUser).toHaveBeenCalledWith('7', {
      roles: ['enterprise', 'admin'],
    })
    expect(adminBff.listUsers).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('已更新 Luna Chen 的角色。')
  })

  it('refuses to save an empty role set', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '调整角色')?.trigger('click')
    await flushPromises()

    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    await checkboxes[2]!.setValue(false)
    await findButton(wrapper, '保存角色')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('至少保留一个角色')
    expect(adminBff.updateUser).not.toHaveBeenCalled()
  })

  it('toggles a user status through the PATCH endpoint', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '停用')?.trigger('click')
    await flushPromises()

    expect(adminBff.updateUser).toHaveBeenCalledWith('7', { isActive: false })
    expect(wrapper.text()).toContain('已停用 Luna Chen。')
  })
})
