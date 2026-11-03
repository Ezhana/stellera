import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { authBff } from '@/bff/auth'
import type { SessionView, ViewerProfile } from '@/models'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/auth', () => ({
  authBff: {
    login: vi.fn(),
    register: vi.fn(),
    restore: vi.fn(),
    logout: vi.fn(),
  },
}))

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
  permissionGroups: [
    {
      key: 'fde',
      label: 'FDE 订单',
      actions: [{ key: 'GET', label: '查看' }],
      rawObjects: ['/api/v1/fde/orders/*'],
    },
  ],
  permissionCount: 1,
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
  remember: true,
  authenticatedAt: '2026-01-01T00:00:00.000Z',
}

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('delegates login to the BFF and exposes the stable viewer model', async () => {
    vi.mocked(authBff.login).mockResolvedValue(session)

    const store = useAuthStore()
    const result = await store.login({ username: 'luna', password: 'secret' }, true)

    expect(authBff.login).toHaveBeenCalledWith({ username: 'luna', password: 'secret' }, true)
    expect(result).toBe(session)
    expect(store.status).toBe('authenticated')
    expect(store.isAuthenticated).toBe(true)
    expect(store.viewer).toEqual(viewer)
    expect(store.roles).toEqual(viewer.roles)
    expect(store.permissionGroups).toEqual(viewer.permissionGroups)
    expect(store.bootstrapped).toBe(true)
  })

  it('delegates registration to the BFF and stores the returned session', async () => {
    vi.mocked(authBff.register).mockResolvedValue({ ...session, remember: false })

    const store = useAuthStore()
    const result = await store.register(
      {
        username: 'newbie',
        email: 'newbie@example.com',
        fullName: '新会员',
        password: 'secret123',
      },
      false,
    )

    expect(authBff.register).toHaveBeenCalledWith(
      {
        username: 'newbie',
        email: 'newbie@example.com',
        fullName: '新会员',
        password: 'secret123',
      },
      false,
    )
    expect(result.remember).toBe(false)
    expect(store.status).toBe('authenticated')
    expect(store.isAuthenticated).toBe(true)
    expect(store.bootstrapped).toBe(true)
  })

  it('returns to anonymous when registration fails', async () => {
    vi.mocked(authBff.register).mockRejectedValue(new Error('conflict'))

    const store = useAuthStore()

    await expect(
      store.register(
        { username: 'luna', email: 'luna@example.com', fullName: 'Luna', password: 'secret123' },
        false,
      ),
    ).rejects.toThrow('conflict')
    expect(store.session).toBeNull()
    expect(store.status).toBe('anonymous')
  })

  it('clears the session on logout even when the BFF fails', async () => {
    vi.mocked(authBff.login).mockResolvedValue(session)
    vi.mocked(authBff.logout).mockRejectedValue(new Error('network down'))

    const store = useAuthStore()
    await store.login({ username: 'luna', password: 'secret' }, true)
    await expect(store.logout()).rejects.toThrow('network down')

    expect(authBff.logout).toHaveBeenCalledTimes(1)
    expect(store.session).toBeNull()
    expect(store.viewer).toBeNull()
    expect(store.status).toBe('anonymous')
    expect(store.isAuthenticated).toBe(false)
  })

  it('restores a persisted session through the BFF', async () => {
    vi.mocked(authBff.restore).mockResolvedValue(session)

    const store = useAuthStore()
    await store.bootstrap()

    expect(authBff.restore).toHaveBeenCalledTimes(1)
    expect(store.viewer).toEqual(viewer)
    expect(store.status).toBe('authenticated')
    expect(store.bootstrapped).toBe(true)
  })

  it('becomes anonymous when there is no persisted session', async () => {
    vi.mocked(authBff.restore).mockResolvedValue(null)

    const store = useAuthStore()
    await store.bootstrap()

    expect(store.session).toBeNull()
    expect(store.status).toBe('anonymous')
    expect(store.bootstrapped).toBe(true)
  })

  it('becomes anonymous when the BFF restore throws unexpectedly', async () => {
    vi.mocked(authBff.restore).mockRejectedValue(new Error('boom'))

    const store = useAuthStore()
    await store.bootstrap()

    expect(store.session).toBeNull()
    expect(store.status).toBe('anonymous')
    expect(store.bootstrapped).toBe(true)
  })

  it('returns to anonymous when login fails', async () => {
    vi.mocked(authBff.login).mockRejectedValue(new Error('invalid credentials'))

    const store = useAuthStore()

    await expect(store.login({ username: 'luna', password: 'bad' }, false)).rejects.toThrow(
      'invalid credentials',
    )
    expect(store.session).toBeNull()
    expect(store.status).toBe('anonymous')
  })
})
