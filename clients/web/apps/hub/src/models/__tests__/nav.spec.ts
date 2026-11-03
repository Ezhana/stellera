import { describe, expect, it } from 'vitest'

import { CONSOLE_NAV, findNavGroupForRoute, navForViewer } from '@/models'

const labels = (groups: ReturnType<typeof navForViewer>): string[] =>
  groups.map((group) => group.label)

describe('navForViewer', () => {
  it('shows platform, FDE orders and wallet to non-admin viewers', () => {
    const groups = navForViewer({ isAdmin: false })

    expect(labels(groups)).toEqual(['平台', 'FDE 订单', '钱包'])
    expect(groups.some((group) => group.requiresAdmin)).toBe(false)
    expect(groups.flatMap((group) => group.children.map((leaf) => leaf.label))).toContain(
      '我的钱包',
    )
  })

  it('adds the admin group with all three console pages for admins', () => {
    const groups = navForViewer({ isAdmin: true })

    expect(labels(groups)).toEqual(['平台', 'FDE 订单', '钱包', '管理'])
    const admin = groups.find((group) => group.key === 'admin')
    expect(admin?.requiresAdmin).toBe(true)
    expect(admin?.children.map((leaf) => leaf.routeName)).toEqual([
      'admin-users',
      'admin-redeem-codes',
      'admin-settings',
    ])
    expect(admin?.children.map((leaf) => leaf.label)).toEqual(['用户', '兑换码', '系统设置'])
  })

  it('never mutates the shared console tree', () => {
    navForViewer({ isAdmin: true })
    expect(labels([...CONSOLE_NAV])).toEqual(['平台', 'FDE 订单', '钱包', '管理'])
  })
})

describe('findNavGroupForRoute', () => {
  it('resolves wallet routes in the filtered tree', () => {
    const groups = navForViewer({ isAdmin: false })
    const resolved = findNavGroupForRoute('wallet', groups)

    expect(resolved?.group.key).toBe('wallet')
    expect(resolved?.leaf.label).toBe('我的钱包')
  })

  it('resolves admin routes for admins', () => {
    const groups = navForViewer({ isAdmin: true })
    const resolved = findNavGroupForRoute('admin-redeem-codes', groups)

    expect(resolved?.group.key).toBe('admin')
    expect(resolved?.leaf.label).toBe('兑换码')
  })

  it('does not resolve admin routes for non-admin groups', () => {
    expect(findNavGroupForRoute('admin-users', navForViewer({ isAdmin: false }))).toBeNull()
  })

  it('returns null for unknown or non-string route names', () => {
    expect(findNavGroupForRoute('nope')).toBeNull()
    expect(findNavGroupForRoute(null)).toBeNull()
    expect(findNavGroupForRoute(Symbol('x'))).toBeNull()
  })
})
