import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authBff } from '@/bff/auth'
import { BffError } from '@/bff/errors'
import type { SessionView } from '@/models'
import RegisterPage from '@/pages/RegisterPage.vue'

vi.mock('@/bff/auth', () => ({
  authBff: {
    login: vi.fn(),
    register: vi.fn(),
    restore: vi.fn(),
    logout: vi.fn(),
  },
}))

const EmptyView = { template: '<div />' }

const session: SessionView = {
  viewer: {
    id: '12',
    username: 'newbie',
    displayName: '新会员',
    email: 'newbie@example.com',
    initials: '新会',
    status: 'active',
    statusLabel: '已启用',
    isAdmin: false,
    certification: null,
    roles: [{ key: 'member', label: '会员', tone: 'default' }],
    permissionGroups: [],
    permissionCount: 0,
    capabilities: {
      publishOrder: true,
      applyOrder: true,
      submitOrderLog: false,
      viewWallet: true,
      redeemCode: true,
      manageAdmin: false,
    },
  },
  remember: false,
  authenticatedAt: '2026-11-01T00:00:00.000Z',
}

interface MountResult {
  wrapper: VueWrapper
  router: Router
}

async function mountPage(): Promise<MountResult> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: EmptyView },
      { path: '/register', name: 'register', component: EmptyView },
      { path: '/intro', name: 'intro', component: EmptyView },
    ],
  })
  await router.push('/register')
  await router.isReady()

  const wrapper = mount(RegisterPage, { global: { plugins: [pinia, router] } })
  return { wrapper, router }
}

async function fill(
  wrapper: VueWrapper,
  values: {
    username?: string
    fullName?: string
    email?: string
    password?: string
    confirmPassword?: string
  },
): Promise<void> {
  if (values.username !== undefined)
    await wrapper.find('input[name="username"]').setValue(values.username)
  if (values.fullName !== undefined)
    await wrapper.find('input[name="fullName"]').setValue(values.fullName)
  if (values.email !== undefined) await wrapper.find('input[name="email"]').setValue(values.email)
  if (values.password !== undefined)
    await wrapper.find('input[name="password"]').setValue(values.password)
  if (values.confirmPassword !== undefined)
    await wrapper.find('input[name="confirmPassword"]').setValue(values.confirmPassword)
}

async function submit(wrapper: VueWrapper): Promise<void> {
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows Chinese validation errors and never calls the BFF for an empty form', async () => {
    const { wrapper, router } = await mountPage()

    await submit(wrapper)

    expect(wrapper.text()).toContain('用户名至少 3 个字符')
    expect(wrapper.text()).toContain('请输入姓名')
    expect(wrapper.text()).toContain('请输入邮箱')
    expect(wrapper.text()).toContain('密码至少 8 个字符')
    expect(wrapper.text()).toContain('请再次输入密码')
    expect(authBff.register).not.toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('register')
  })

  it('rejects an invalid username, email and mismatched passwords', async () => {
    const { wrapper } = await mountPage()

    await fill(wrapper, {
      username: 'bad name!',
      fullName: '新会员',
      email: 'not-an-email',
      password: 'secret123',
      confirmPassword: 'secret456',
    })
    await submit(wrapper)

    expect(wrapper.text()).toContain('用户名只能包含字母、数字、下划线、点或短横线')
    expect(wrapper.text()).toContain('请输入有效的邮箱地址')
    expect(wrapper.text()).toContain('两次输入的密码不一致')
    expect(authBff.register).not.toHaveBeenCalled()
  })

  it('registers through the store and enters the console', async () => {
    vi.mocked(authBff.register).mockResolvedValue(session)
    const { wrapper, router } = await mountPage()

    await fill(wrapper, {
      username: ' newbie ',
      fullName: ' 新会员 ',
      email: ' newbie@example.com ',
      password: 'secret123',
      confirmPassword: 'secret123',
    })
    await submit(wrapper)

    expect(authBff.register).toHaveBeenCalledWith(
      {
        username: 'newbie',
        fullName: '新会员',
        email: 'newbie@example.com',
        password: 'secret123',
      },
      false,
    )
    expect(router.currentRoute.value.name).toBe('intro')
  })

  it('shows the conflict copy when the username or email is taken', async () => {
    vi.mocked(authBff.register).mockRejectedValue(
      new BffError('conflict', '用户名或邮箱已被占用', { status: 409 }),
    )
    const { wrapper, router } = await mountPage()

    await fill(wrapper, {
      username: 'member',
      fullName: '会员',
      email: 'member@example.com',
      password: 'secret123',
      confirmPassword: 'secret123',
    })
    await submit(wrapper)

    expect(wrapper.text()).toContain('用户名或邮箱已被占用，请更换后重试。')
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(router.currentRoute.value.name).toBe('register')
  })

  it('shows the backend message for an invalid registration payload', async () => {
    vi.mocked(authBff.register).mockRejectedValue(
      new BffError('invalid-input', '密码强度不足', { status: 422 }),
    )
    const { wrapper } = await mountPage()

    await fill(wrapper, {
      username: 'newbie',
      fullName: '新会员',
      email: 'newbie@example.com',
      password: 'weakpass',
      confirmPassword: 'weakpass',
    })
    await submit(wrapper)

    expect(wrapper.text()).toContain('密码强度不足')
  })

  it('links back to the login page', async () => {
    const { wrapper } = await mountPage()

    const link = wrapper.findAll('a').find((node) => node.text() === '返回登录')
    expect(link?.attributes('href')).toBe('/login')
  })
})
