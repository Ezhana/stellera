import { describe, expect, it } from 'vitest'

import { CONSOLE_NAV, findNavGroupForRoute, navForViewer } from '@/models'

const labels = (groups: ReturnType<typeof navForViewer>): string[] =>
  groups.map((group) => group.label)

describe('navForViewer', () => {
  it('shows platform, account, FDE orders and wallet to non-admin viewers', () => {
    const groups = navForViewer({ isAdmin: false })

    expect(labels(groups)).toEqual(['平台', '个人', 'FDE 订单', '钱包'])
    expect(groups.some((group) => group.requiresAdmin)).toBe(false)
    expect(groups.flatMap((group) => group.children.map((leaf) => leaf.label))).toEqual(
      expect.arrayContaining([
        '个人信息',
        '订单大厅',
        '我发布的',
        '我接到的',
        '我的申请',
        '我的钱包',
      ]),
    )
  })

  it('orders the FDE leaves as hall, published, assigned, applications', () => {
    const fde = navForViewer({ isAdmin: false }).find((group) => group.key === 'fde')

    expect(fde?.children.map((leaf) => leaf.routeName)).toEqual([
      'fde-hall',
      'fde-published',
      'fde-assigned',
      'fde-applications',
    ])
    expect(fde?.children.map((leaf) => leaf.label)).toEqual([
      '订单大厅',
      '我发布的',
      '我接到的',
      '我的申请',
    ])
    expect(fde?.children[0]?.meta).toBe('实时')
  })

  it('adds the admin group with every console page for admins', () => {
    const groups = navForViewer({ isAdmin: true })

    expect(labels(groups)).toEqual(['平台', '个人', 'FDE 订单', '钱包', '管理'])
    const admin = groups.find((group) => group.key === 'admin')
    expect(admin?.requiresAdmin).toBe(true)
    expect(admin?.children.map((leaf) => leaf.routeName)).toEqual([
      'admin-users',
      'admin-certifications',
      'admin-redeem-codes',
      'admin-settings',
    ])
    expect(admin?.children.map((leaf) => leaf.label)).toEqual([
      '用户',
      '认证审核',
      '兑换码',
      '系统设置',
    ])
  })

  it('never mutates the shared console tree', () => {
    navForViewer({ isAdmin: true })
    expect(labels([...CONSOLE_NAV])).toEqual(['平台', '个人', 'FDE 订单', '钱包', '管理'])
  })
})

describe('findNavGroupForRoute', () => {
  it('resolves the profile route in the filtered tree', () => {
    const resolved = findNavGroupForRoute('profile', navForViewer({ isAdmin: false }))

    expect(resolved?.group.key).toBe('account')
    expect(resolved?.leaf.label).toBe('个人信息')
  })

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
