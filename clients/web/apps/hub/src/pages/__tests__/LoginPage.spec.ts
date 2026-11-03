import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authBff } from '@/bff/auth'
import { BffError } from '@/bff/errors'
import { DEMO_ACCOUNTS } from '@/config/demoAccounts'
import type { SessionView, ViewerProfile } from '@/models'
import LoginPage from '@/pages/LoginPage.vue'

vi.mock('@/bff/auth', () => ({
  authBff: {
    login: vi.fn(),
    restore: vi.fn(),
    logout: vi.fn(),
  },
}))

const EmptyView = { template: '<div />' }

const viewer: ViewerProfile = {
  id: '7',
  username: 'luna',
  displayName: 'Luna',
  email: 'luna@example.com',
  initials: 'LU',
  status: 'active',
  statusLabel: '已启用',
  isAdmin: true,
  certification: null,
  roles: [{ key: 'admin', label: '管理员', tone: 'accent' }],
  permissionGroups: [],
  permissionCount: 0,
  capabilities: {
    publishOrder: true,
    applyOrder: true,
    submitOrderLog: true,
    viewWallet: true,
    redeemCode: true,
    manageAdmin: true,
  },
}

const session: SessionView = {
  viewer,
  remember: false,
  authenticatedAt: '2026-01-01T00:00:00.000Z',
}

interface MountResult {
  wrapper: VueWrapper
  router: Router
}

async function mountLogin(query: Record<string, string> = {}): Promise<MountResult> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: EmptyView },
      { path: '/register', name: 'register', component: EmptyView },
      { path: '/intro', name: 'intro', component: EmptyView },
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
    ],
  })
  await router.push({ path: '/login', query })
  await router.isReady()
  const wrapper = mount(LoginPage, { global: { plugins: [pinia, router] } })
  return { wrapper, router }
}

async function fillAndSubmit(wrapper: VueWrapper, username = '', password = ''): Promise<void> {
  if (username) await wrapper.find('input[name="username"]').setValue(username)
  if (password) await wrapper.find('input[name="password"]').setValue(password)
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows Chinese validation errors and never calls the BFF for an empty form', async () => {
    const { wrapper, router } = await mountLogin()

    await fillAndSubmit(wrapper)

    expect(wrapper.text()).toContain('请输入用户名')
    expect(wrapper.text()).toContain('请输入密码')
    expect(authBff.login).not.toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('rejects credentials longer than the allowed length', async () => {
    const { wrapper } = await mountLogin()

    await fillAndSubmit(wrapper, 'a'.repeat(65), 'b'.repeat(129))

    expect(wrapper.text()).toContain('用户名长度不能超过 64 个字符')
    expect(wrapper.text()).toContain('密码长度不能超过 128 个字符')
    expect(authBff.login).not.toHaveBeenCalled()
  })

  it('renders a Chinese error message for invalid credentials', async () => {
    vi.mocked(authBff.login).mockRejectedValue(
      new BffError('invalid-credentials', '用户名或密码不正确。'),
    )
    const { wrapper, router } = await mountLogin()

    await fillAndSubmit(wrapper, 'luna', 'wrong-password')

    expect(authBff.login).toHaveBeenCalledWith(
      { username: 'luna', password: 'wrong-password' },
      false,
    )
    expect(wrapper.text()).toContain('用户名或密码不正确')
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('renders a Chinese error message on a network failure', async () => {
    vi.mocked(authBff.login).mockRejectedValue(new BffError('network', 'network down'))
    const { wrapper } = await mountLogin()

    await fillAndSubmit(wrapper, 'luna', 'secret')

    expect(wrapper.text()).toContain('无法连接到服务')
  })

  it('logs in and follows a safe internal redirect', async () => {
    vi.mocked(authBff.login).mockResolvedValue(session)
    const { wrapper, router } = await mountLogin({ redirect: '/fde/hall?status=open' })

    await fillAndSubmit(wrapper, ' luna ', 'secret')

    expect(authBff.login).toHaveBeenCalledWith({ username: 'luna', password: 'secret' }, false)
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/fde/hall?status=open')
  })

  it('ignores an unsafe redirect target and falls back to /intro', async () => {
    vi.mocked(authBff.login).mockResolvedValue(session)
    const { wrapper, router } = await mountLogin({ redirect: '//evil.example.com/steal' })

    await fillAndSubmit(wrapper, 'luna', 'secret')

    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/intro')
  })

  it('links to the public registration page', async () => {
    const { wrapper } = await mountLogin()

    const link = wrapper.findAll('a').find((node) => node.text() === '注册')
    expect(link?.attributes('href')).toBe('/register')
  })

  it('lists every demo account with its plaintext password', async () => {
    const { wrapper } = await mountLogin()

    expect(wrapper.text()).toContain('测试环境演示账号')
    expect(wrapper.text()).toContain('点击填入')
    expect(DEMO_ACCOUNTS.map((account) => account.username)).toEqual([
      'admin',
      'member',
      'enterprise',
      'engineer',
    ])
    expect(DEMO_ACCOUNTS.find((account) => account.username === 'member')?.password).toBe(
      'member12345',
    )
    expect(wrapper.findAll('[data-demo-account]')).toHaveLength(DEMO_ACCOUNTS.length)

    for (const account of DEMO_ACCOUNTS) {
      const card = wrapper.find(`[data-demo-account="${account.username}"]`)
      expect(card.exists()).toBe(true)
      expect(card.text()).toContain(account.role)
      expect(card.text()).toContain(account.username)
      expect(card.text()).toContain(account.password)
      expect(card.attributes('title')).toContain(account.password)
    }
  })

  it('fills the form from a demo account and submits those credentials', async () => {
    vi.mocked(authBff.login).mockResolvedValue(session)
    const { wrapper, router } = await mountLogin()

    await fillAndSubmit(wrapper)
    expect(wrapper.text()).toContain('请输入用户名')
    expect(wrapper.text()).toContain('请输入密码')

    const account = DEMO_ACCOUNTS[1]!
    await wrapper.find(`[data-demo-account="${account.username}"]`).trigger('click')
    await flushPromises()

    expect((wrapper.find('input[name="username"]').element as HTMLInputElement).value).toBe(
      account.username,
    )
    expect((wrapper.find('input[name="password"]').element as HTMLInputElement).value).toBe(
      account.password,
    )
    expect(wrapper.text()).not.toContain('请输入用户名')
    expect(wrapper.text()).not.toContain('请输入密码')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(authBff.login).toHaveBeenCalledWith(
      { username: account.username, password: account.password },
      false,
    )
    expect(router.currentRoute.value.name).toBe('intro')
  })

  it('clears a previous login error when a demo account is picked', async () => {
    vi.mocked(authBff.login).mockRejectedValue(new BffError('invalid-credentials', 'bad admin'))
    const { wrapper } = await mountLogin()

    await fillAndSubmit(wrapper, 'luna', 'wrong-password')
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)

    await wrapper.find(`[data-demo-account="${DEMO_ACCOUNTS[0]!.username}"]`).trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect((wrapper.find('input[name="username"]').element as HTMLInputElement).value).toBe(
      DEMO_ACCOUNTS[0]!.username,
    )
  })
})
