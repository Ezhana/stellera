import { describe, expect, it, vi } from 'vitest'

import { BffError } from '../../errors'
import { HttpAuthGateway } from '../gateway'
import { request } from '@/lib/http'

vi.mock('@/lib/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/http')>()
  return { ...actual, request: vi.fn() }
})

describe('HttpAuthGateway', () => {
  const gateway = new HttpAuthGateway()

  it('validates and returns a login response', async () => {
    vi.mocked(request).mockResolvedValueOnce({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      token_type: 'bearer',
      expires_in: 900,
      user: {
        id: 1,
        username: 'admin',
        email: 'admin@example.com',
        full_name: '系统管理员',
        is_active: true,
        roles: ['admin'],
        permissions: [{ object: '/api/v1/*', action: '^(GET|POST)$' }],
        ignored_backend_field: 'stripped',
      },
    })

    const result = await gateway.login({ username: 'admin', password: 'secret' })

    expect(result.access_token).toBe('access-1')
    expect(result.user.username).toBe('admin')
    expect('ignored_backend_field' in result.user).toBe(false)
  })

  it('throws a stable malformed-response error instead of leaking a Zod error', async () => {
    vi.mocked(request).mockResolvedValueOnce({ access_token: 42 })

    await expect(gateway.login({ username: 'admin', password: 'secret' })).rejects.toMatchObject({
      name: 'BffError',
      code: 'malformed-response',
    })
    await expect(gateway.login({ username: 'admin', password: 'secret' })).rejects.toBeInstanceOf(
      BffError,
    )
  })

  it('defaults missing optional lists on /me', async () => {
    vi.mocked(request).mockResolvedValueOnce({
      id: 'u-1',
      username: 'luna',
    })

    const user = await gateway.me('access-1')

    expect(user.roles).toEqual([])
    expect(user.permissions).toEqual([])
    expect(user.email).toBeUndefined()
  })

  it('registers with the snake_case body and returns the login response shape', async () => {
    vi.mocked(request).mockResolvedValueOnce({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      user: {
        id: 12,
        username: 'newbie',
        email: 'newbie@example.com',
        full_name: '新会员',
        roles: ['member'],
      },
    })

    const result = await gateway.register({
      username: 'newbie',
      email: 'newbie@example.com',
      fullName: '新会员',
      password: 'secret123',
    })

    expect(request).toHaveBeenCalledWith('/auth/register', {
      method: 'POST',
      body: {
        username: 'newbie',
        email: 'newbie@example.com',
        full_name: '新会员',
        password: 'secret123',
      },
    })
    expect(result.access_token).toBe('access-1')
    expect(result.user.roles).toEqual(['member'])
  })
})
