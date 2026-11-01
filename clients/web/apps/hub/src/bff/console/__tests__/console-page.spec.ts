import { describe, expect, it } from 'vitest'

import type { ViewerProfile } from '@/models'
import { buildConsolePageModel } from '../index'

const viewer: ViewerProfile = {
  id: '7',
  username: 'operator',
  displayName: '运营',
  email: 'operator@example.com',
  initials: '运营',
  status: 'active',
  statusLabel: '已启用',
  isAdmin: false,
  roles: [{ key: 'operator', label: '运营', tone: 'info' }],
  permissionGroups: [
    {
      key: 'wallet',
      label: '钱包',
      actions: [{ key: 'GET', label: '查看' }],
      rawObjects: ['/api/v1/wallet/*'],
    },
  ],
  permissionCount: 3,
  moduleAccess: { wallet: 'read', orders: 'write', plaza: 'none' },
}

describe('buildConsolePageModel', () => {
  it('aggregates viewer capabilities with the frontend module catalog', () => {
    const model = buildConsolePageModel(viewer)

    expect(model.viewer).toBe(viewer)
    expect(model.modules.map((module) => module.label)).toEqual(['钱包', '订单', '广场'])
    expect(model.modules.map((module) => module.accessLabel)).toEqual(['只读', '可写', '无权限'])
    expect(model.modules.map((module) => module.availability)).toEqual([
      'planned',
      'planned',
      'planned',
    ])
    expect(model.modules.map((module) => module.availabilityLabel)).toEqual([
      '即将上线',
      '即将上线',
      '即将上线',
    ])
    expect(model.modules[0]?.accessTone).toBe('info')
    expect(model.modules[1]?.accessTone).toBe('success')
    expect(model.modules[2]?.accessTone).toBe('default')
    expect(model.summary).toEqual({
      roleCount: 1,
      permissionCount: 3,
      readableModuleCount: 2,
      writableModuleCount: 1,
    })
    expect(model.permissionGroups).toBe(viewer.permissionGroups)
  })

  it('does not expose the internal probe path on page modules', () => {
    const model = buildConsolePageModel(viewer)

    expect(model.modules.every((module) => !('probePath' in module))).toBe(true)
  })
})
