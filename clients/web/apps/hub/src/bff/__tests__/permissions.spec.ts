import { describe, expect, it } from 'vitest'

import { describeActions, describeObject } from '../describe'
import { permissionAllows } from '../permissions'

describe('permissionAllows', () => {
  it('matches exact and wildcard object paths', () => {
    const permissions = [
      { object: '/api/v1/fde/orders/*', action: '^GET$' },
      { object: '/api/v1/fde/orders', action: '^(POST|PATCH)$' },
    ]

    expect(permissionAllows(permissions, '/api/v1/fde/orders/12', 'GET')).toBe(true)
    expect(permissionAllows(permissions, '/api/v1/fde/orders/12', 'POST')).toBe(false)
    expect(permissionAllows(permissions, '/api/v1/fde/orders', 'POST')).toBe(true)
    expect(permissionAllows(permissions, '/api/v1/fde/orders', 'DELETE')).toBe(false)
  })

  it('matches keyMatch2-style mid-pattern wildcards and :params', () => {
    const permissions = [
      { object: '/api/v1/fde/orders/*/claim', action: '^POST$' },
      { object: '/api/v1/fde/orders/:id/logs', action: '^POST$' },
    ]

    expect(permissionAllows(permissions, '/api/v1/fde/orders/42/claim', 'POST')).toBe(true)
    expect(permissionAllows(permissions, '/api/v1/fde/orders/42/logs', 'POST')).toBe(true)
    expect(permissionAllows(permissions, '/api/v1/fde/orders/42/complete', 'POST')).toBe(false)
  })

  it('lets the admin wildcard cover every module and method', () => {
    const permissions = [{ object: '/api/v1/*', action: '^(GET|POST|PUT|PATCH|DELETE)$' }]

    expect(permissionAllows(permissions, '/api/v1/fde/orders', 'GET')).toBe(true)
    expect(permissionAllows(permissions, '/api/v1/fde/orders/1/claim', 'POST')).toBe(true)
    expect(permissionAllows(permissions, '/api/v1/admin/users', 'DELETE')).toBe(true)
  })

  it('treats invalid regexes and unknown patterns as no access', () => {
    expect(
      permissionAllows([{ object: '/api/v1/*', action: '([' }], '/api/v1/fde/orders', 'GET'),
    ).toBe(false)
    expect(
      permissionAllows([{ object: '/other/*', action: 'GET' }], '/api/v1/fde/orders', 'GET'),
    ).toBe(false)
  })
})

describe('describeObject / describeActions', () => {
  it('maps backend policy objects to business labels', () => {
    expect(describeObject('/api/v1/fde/orders')).toEqual({ key: 'fde', label: 'FDE 订单' })
    expect(describeObject('/api/v1/fde/orders/*/claim')).toEqual({
      key: 'fde',
      label: 'FDE 订单',
    })
    expect(describeObject('/api/v1/auth/me')).toEqual({ key: 'profile', label: '账户资料' })
    expect(describeObject('/api/v1/auth/logout')).toEqual({ key: 'session', label: '登录会话' })
    expect(describeObject('/api/v1/*')).toEqual({ key: 'business', label: '全部业务接口' })
    expect(describeObject('/custom')).toEqual({ key: 'other', label: '其他接口' })
  })

  it('turns regex action patterns into readable actions', () => {
    expect(describeActions('^GET$')).toEqual([{ key: 'GET', label: '查看' }])
    expect(describeActions('^(GET|POST)$')).toEqual([
      { key: 'GET', label: '查看' },
      { key: 'POST', label: '创建' },
    ])
    expect(describeActions('^(GET|POST|PUT|PATCH|DELETE)$')).toEqual([
      { key: 'all', label: '全部操作' },
    ])
  })
})
