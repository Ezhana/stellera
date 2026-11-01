import type {
  PermissionGroupView,
  RoleView,
  ViewerProfile,
  ModuleAccess,
  ModuleKey,
} from '@/models'
import { MODULE_CATALOG } from '@/models/modules'

import { actionOrder, describeActions, describeObject, groupOrder } from '../describe'
import { permissionAllows } from '../permissions'
import type { PermissionDto, UserDto } from './dto'

const ROLE_META: Readonly<Record<string, { label: string; tone: RoleView['tone'] }>> = {
  admin: { label: '管理员', tone: 'accent' },
  operator: { label: '运营', tone: 'info' },
  viewer: { label: '只读成员', tone: 'default' },
  authenticated: { label: '已认证', tone: 'default' },
}

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
    moduleAccess: toModuleAccess(permissions),
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

function toModuleAccess(permissions: readonly PermissionDto[]): Record<ModuleKey, ModuleAccess> {
  const access: Record<ModuleKey, ModuleAccess> = {
    wallet: 'none',
    orders: 'none',
    plaza: 'none',
  }

  for (const module of MODULE_CATALOG) {
    const canRead = permissionAllows(permissions, module.probePath, 'GET')
    const canWrite = permissionAllows(permissions, module.probePath, 'POST')
    access[module.key] = canWrite ? 'write' : canRead ? 'read' : 'none'
  }

  return access
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
