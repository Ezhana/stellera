import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/http'
import type { LoginResponseDto, UserDto } from '../dto'
import type { AuthGateway } from '../gateway'
import { AuthBff } from '../service'
import { deriveInitials } from '../mapper'
import type { StoredAuth, TokenStore } from '../token-store'

const viewerUser: UserDto = {
  id: 7,
  username: 'viewer',
  email: 'viewer@example.com',
  full_name: '只读成员',
  is_active: true,
  roles: ['viewer'],
  permissions: [
    { object: '/api/v1/fde/orders', action: '^GET$' },
    { object: '/api/v1/fde/orders/*', action: '^GET$' },
    { object: '/api/v1/auth/me', action: '^GET$' },
  ],
}

const loginDto: LoginResponseDto = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  user: viewerUser,
}

class MemoryTokenStore implements TokenStore {
  value: StoredAuth | null = null

  read(): StoredAuth | null {
    return this.value
  }

  save(tokens: StoredAuth['tokens'], remember: boolean): void {
    this.value = { tokens, remember }
  }

  clear(): void {
    this.value = null
  }
}

function createGateway(): AuthGateway {
  return {
    login: vi.fn(async () => loginDto),
    refresh: vi.fn(async () => ({ access_token: 'access-2', refresh_token: 'refresh-2' })),
    me: vi.fn(async () => viewerUser),
    logout: vi.fn(async () => undefined),
  }
}

describe('AuthBff', () => {
  let gateway: AuthGateway
  let tokenStore: MemoryTokenStore
  let bff: AuthBff

  beforeEach(() => {
    gateway = createGateway()
    tokenStore = new MemoryTokenStore()
    bff = new AuthBff(gateway, tokenStore)
  })

  it('maps the backend user DTO into a stable viewer page model', async () => {
    const session = await bff.login({ username: 'viewer', password: 'secret' }, true)

    expect(gateway.login).toHaveBeenCalledWith({ username: 'viewer', password: 'secret' })
    expect(session.remember).toBe(true)
    expect(session.viewer).toMatchObject({
      id: '7',
      username: 'viewer',
      displayName: '只读成员',
      email: 'viewer@example.com',
      initials: '只读',
      status: 'active',
      statusLabel: '已启用',
      isAdmin: false,
      permissionCount: 3,
    })
    expect(session.viewer.roles).toEqual([{ key: 'viewer', label: '只读成员', tone: 'default' }])
    expect(session.viewer.capabilities).toEqual({
      publishOrder: false,
      claimOrder: false,
      submitOrderLog: false,
      completeOrder: false,
      viewWallet: false,
      redeemCode: false,
      manageAdmin: false,
    })
    expect(session.viewer.permissionGroups.map((group) => group.label)).toEqual([
      '账户资料',
      'FDE 订单',
    ])
    expect(session.viewer.permissionGroups[1]?.actions).toEqual([{ key: 'GET', label: '查看' }])
    expect(tokenStore.value).toEqual({
      tokens: { accessToken: 'access-1', refreshToken: 'refresh-1' },
      remember: true,
    })
    expect(session.authenticatedAt).toEqual(expect.any(String))
  })

  it('derives FDE capabilities from enterprise and engineer policies', async () => {
    vi.mocked(gateway.login).mockResolvedValueOnce({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      user: {
        ...viewerUser,
        roles: ['enterprise', 'engineer'],
        permissions: [
          { object: '/api/v1/fde/orders', action: '^POST$' },
          { object: '/api/v1/fde/orders/*/complete', action: '^POST$' },
          { object: '/api/v1/fde/orders/*/claim', action: '^POST$' },
          { object: '/api/v1/fde/orders/*/logs', action: '^POST$' },
        ],
      },
    })

    const session = await bff.login({ username: 'enterprise', password: 'secret' }, false)

    expect(session.viewer.capabilities).toEqual({
      publishOrder: true,
      claimOrder: true,
      submitOrderLog: true,
      completeOrder: true,
      viewWallet: false,
      redeemCode: false,
      manageAdmin: false,
    })
  })

  it('derives wallet and admin capabilities from their policy probes', async () => {
    vi.mocked(gateway.login).mockResolvedValueOnce({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      user: {
        ...viewerUser,
        roles: ['admin'],
        permissions: [
          { object: '/api/v1/wallet', action: '^GET$' },
          { object: '/api/v1/wallet/redeem', action: '^POST$' },
          { object: '/api/v1/admin/users', action: '^GET$' },
        ],
      },
    })

    const session = await bff.login({ username: 'admin', password: 'secret' }, false)

    expect(session.viewer.isAdmin).toBe(true)
    expect(session.viewer.capabilities).toEqual({
      publishOrder: false,
      claimOrder: false,
      submitOrderLog: false,
      completeOrder: false,
      viewWallet: true,
      redeemCode: true,
      manageAdmin: true,
    })
    expect(session.viewer.permissionGroups.map((group) => group.label)).toEqual([
      '钱包',
      '管理接口',
    ])
  })

  it('supplies defaults for sparse backend payloads', async () => {
    vi.mocked(gateway.login).mockResolvedValueOnce({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      user: {
        id: 'u-1',
        username: 'luna',
        email: '',
        full_name: '   ',
        is_active: undefined,
        roles: [],
        permissions: [],
      },
    })

    const session = await bff.login({ username: 'luna', password: 'secret' }, false)

    expect(session.viewer).toMatchObject({
      id: 'u-1',
      displayName: 'luna',
      email: null,
      initials: 'LU',
      status: 'active',
      roles: [],
      permissionGroups: [],
      permissionCount: 0,
      capabilities: {
        publishOrder: false,
        claimOrder: false,
        submitOrderLog: false,
        completeOrder: false,
        viewWallet: false,
        redeemCode: false,
        manageAdmin: false,
      },
    })
  })

  it('exposes the current access token to other frontend BFFs only', async () => {
    expect(bff.accessToken()).toBeNull()

    await bff.login({ username: 'viewer', password: 'secret' }, false)

    expect(bff.accessToken()).toBe('access-1')

    await bff.logout()

    expect(bff.accessToken()).toBeNull()
  })

  it('normalizes a 401 login into invalid-credentials', async () => {
    vi.mocked(gateway.login).mockRejectedValueOnce(new ApiError(401, 'bad credentials'))

    await expect(bff.login({ username: 'luna', password: 'bad' }, false)).rejects.toMatchObject({
      name: 'BffError',
      code: 'invalid-credentials',
    })
    expect(tokenStore.value).toBeNull()
  })

  it('refreshes exactly once when restore hits an expired access token', async () => {
    tokenStore.value = {
      tokens: { accessToken: 'expired', refreshToken: 'refresh-1' },
      remember: false,
    }
    vi.mocked(gateway.me)
      .mockRejectedValueOnce(new ApiError(401, 'expired'))
      .mockResolvedValueOnce(viewerUser)

    const session = await bff.restore()

    expect(gateway.refresh).toHaveBeenCalledTimes(1)
    expect(gateway.refresh).toHaveBeenCalledWith('refresh-1')
    expect(gateway.me).toHaveBeenNthCalledWith(1, 'expired')
    expect(gateway.me).toHaveBeenNthCalledWith(2, 'access-2')
    expect(session?.viewer.username).toBe('viewer')
    expect(session?.remember).toBe(false)
    expect(tokenStore.value).toEqual({
      tokens: { accessToken: 'access-2', refreshToken: 'refresh-2' },
      remember: false,
    })
  })

  it('clears the session when refresh also fails', async () => {
    tokenStore.value = {
      tokens: { accessToken: 'expired', refreshToken: 'refresh-1' },
      remember: true,
    }
    vi.mocked(gateway.me).mockRejectedValue(new ApiError(401, 'expired'))
    vi.mocked(gateway.refresh).mockRejectedValue(new ApiError(401, 'invalid refresh token'))

    const session = await bff.restore()

    expect(session).toBeNull()
    expect(tokenStore.value).toBeNull()
  })

  it('clears tokens on logout even when the revoke call fails', async () => {
    tokenStore.value = {
      tokens: { accessToken: 'access-1', refreshToken: 'refresh-1' },
      remember: true,
    }
    vi.mocked(gateway.logout).mockRejectedValueOnce(new ApiError(0, 'network down'))

    await bff.logout()

    expect(gateway.logout).toHaveBeenCalledWith('access-1', 'refresh-1')
    expect(tokenStore.value).toBeNull()
  })

  it('dedupes repeated human action labels from multiple regex patterns', async () => {
    vi.mocked(gateway.login).mockResolvedValueOnce({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      user: {
        ...viewerUser,
        roles: ['operator'],
        permissions: [
          { object: '/api/v1/fde/orders', action: '^(POST|PATCH)$' },
          { object: '/api/v1/fde/orders/*', action: '^(PATCH|PUT)$' },
        ],
      },
    })

    const session = await bff.login({ username: 'operator', password: 'secret' }, false)
    const orders = session.viewer.permissionGroups.find((group) => group.key === 'fde')

    expect(orders?.actions).toEqual([
      { key: 'POST', label: '创建' },
      { key: 'PATCH', label: '更新' },
    ])
  })

  it('derives CJK and Latin initials', () => {
    expect(deriveInitials('系统管理员')).toBe('系统')
    expect(deriveInitials('Luna Chen')).toBe('LC')
    expect(deriveInitials('luna')).toBe('LU')
    expect(deriveInitials('   ')).toBe('?')
  })
})
