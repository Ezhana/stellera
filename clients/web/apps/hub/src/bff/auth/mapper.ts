import type { HubCapabilities, PermissionGroupView, RoleView, ViewerProfile } from '@/models'

import { actionOrder, describeActions, describeObject, groupOrder } from '../describe'
import { permissionAllows, type PermissionLike } from '../permissions'
import type { PermissionDto, UserDto } from './dto'

const ROLE_META: Readonly<Record<string, { label: string; tone: RoleView['tone'] }>> = {
  admin: { label: '管理员', tone: 'accent' },
  operator: { label: '运营', tone: 'info' },
  enterprise: { label: '企业', tone: 'accent' },
  engineer: { label: '工程师', tone: 'success' },
  viewer: { label: '只读成员', tone: 'default' },
  authenticated: { label: '已认证', tone: 'default' },
}

/** Concrete probe paths for the FDE capabilities; the backend policies use the same prefixes. */
const CAPABILITY_PROBES = {
  publishOrder: { path: '/api/v1/fde/orders', method: 'POST' },
  claimOrder: { path: '/api/v1/fde/orders/1/claim', method: 'POST' },
  submitOrderLog: { path: '/api/v1/fde/orders/1/logs', method: 'POST' },
  completeOrder: { path: '/api/v1/fde/orders/1/complete', method: 'POST' },
} as const

/** Map the backend user DTO into the stable viewer page model. */
export function toViewerProfile(user: UserDto): ViewerProfile {
  const username = user.username
  const fullName = normalizeOptional(user.full_name)
  const displayName = fullName ?? username
  const status = user.is_active === false ? 'inactive' : 'active'
  const roles = toRoleViews(user.roles)
  const permissions = user.permissions ?? []

  return {
    id: String(user.id),
    username,
    displayName,
    email: normalizeOptional(user.email),
    initials: deriveInitials(displayName),
    status,
    statusLabel: status === 'active' ? '已启用' : '已停用',
    isAdmin: roles.some((role) => role.key === 'admin'),
    roles,
    permissionGroups: toPermissionGroups(permissions),
    permissionCount: permissions.length,
    capabilities: toCapabilities(permissions),
  }
}

function toRoleViews(roleKeys: readonly string[]): RoleView[] {
  return [...new Set(roleKeys)].map((key) => {
    const meta = ROLE_META[key]
    return meta ? { key, label: meta.label, tone: meta.tone } : { key, label: key, tone: 'default' }
  })
}

function toPermissionGroups(permissions: readonly PermissionDto[]): PermissionGroupView[] {
  const groups = new Map<string, PermissionGroupView>()

  for (const permission of permissions) {
    const meta = describeObject(permission.object)
    let group = groups.get(meta.key)
    if (!group) {
      group = { key: meta.key, label: meta.label, actions: [], rawObjects: [] }
      groups.set(meta.key, group)
    }

    for (const action of describeActions(permission.action)) {
      if (
        !group.actions.some(
          (existing) => existing.key === action.key || existing.label === action.label,
        )
      ) {
        group.actions.push(action)
      }
    }

    if (!group.rawObjects.includes(permission.object)) {
      group.rawObjects.push(permission.object)
    }
  }

  const result = [...groups.values()]
  for (const group of result) {
    group.actions.sort((left, right) => actionOrder(left.key) - actionOrder(right.key))
    group.rawObjects.sort()
  }
  result.sort((left, right) => groupOrder(left.key) - groupOrder(right.key))
  return result
}

function toCapabilities(permissions: readonly PermissionLike[]): HubCapabilities {
  return {
    publishOrder: permissionAllows(
      permissions,
      CAPABILITY_PROBES.publishOrder.path,
      CAPABILITY_PROBES.publishOrder.method,
    ),
    claimOrder: permissionAllows(
      permissions,
      CAPABILITY_PROBES.claimOrder.path,
      CAPABILITY_PROBES.claimOrder.method,
    ),
    submitOrderLog: permissionAllows(
      permissions,
      CAPABILITY_PROBES.submitOrderLog.path,
      CAPABILITY_PROBES.submitOrderLog.method,
    ),
    completeOrder: permissionAllows(
      permissions,
      CAPABILITY_PROBES.completeOrder.path,
      CAPABILITY_PROBES.completeOrder.method,
    ),
  }
}

function normalizeOptional(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

/** 1–2 glyph initials for avatars: CJK keeps the first two characters, Latin uses word initials. */
export function deriveInitials(displayName: string): string {
  const trimmed = displayName.trim()
  if (!trimmed) return '?'

  if (/^[\u3400-\u9fff]/.test(trimmed)) {
    return Array.from(trimmed).slice(0, 2).join('')
  }

  const words = trimmed.split(/\s+/).filter(Boolean)
  if (words.length >= 2) {
    return `${words[0]?.[0] ?? ''}${words[1]?.[0] ?? ''}`.toUpperCase()
  }

  return Array.from(trimmed).slice(0, 2).join('').toUpperCase()
}
