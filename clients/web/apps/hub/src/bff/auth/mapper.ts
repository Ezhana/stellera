import type { HubCapabilities, PermissionGroupView, RoleView, ViewerProfile } from '@/models'

import { certificationsFromRoles, normalizeCertifications } from '../certification'
import { actionOrder, describeActions, describeObject, groupOrder } from '../describe'
import { permissionAllows, type PermissionLike } from '../permissions'
import type { PermissionDto, UserDto } from './dto'

const ROLE_META: Readonly<Record<string, { label: string; tone: RoleView['tone'] }>> = {
  admin: { label: '管理员', tone: 'accent' },
  member: { label: '会员', tone: 'default' },
  realname: { label: '实名认证', tone: 'info' },
  enterprise: { label: '企业', tone: 'accent' },
  engineer: { label: '工程师', tone: 'success' },
}

/** Concrete probe paths for the viewer capabilities; the backend policies use the same prefixes. */
const CAPABILITY_PROBES = {
  publishOrder: { path: '/api/v1/fde/orders', method: 'POST' },
  applyOrder: { path: '/api/v1/fde/orders/1/applications', method: 'POST' },
  submitOrderLog: { path: '/api/v1/fde/orders/1/logs', method: 'POST' },
  viewWallet: { path: '/api/v1/wallet', method: 'GET' },
  redeemCode: { path: '/api/v1/wallet/redeem', method: 'POST' },
  manageAdmin: { path: '/api/v1/admin/users', method: 'GET' },
} as const

/** Known role label/tone; unknown keys degrade to the raw key + default tone. */
export function describeRole(key: string): RoleView {
  const meta = ROLE_META[key]
  return meta ? { key, label: meta.label, tone: meta.tone } : { key, label: key, tone: 'default' }
}

/** Map the backend user DTO into the stable viewer page model. */
export function toViewerProfile(user: UserDto): ViewerProfile {
  const username = user.username
  const nickname = normalizeOptional(user.nickname)
  const displayName = nickname ?? normalizeOptional(user.full_name) ?? username
  const status = user.is_active === false ? 'inactive' : 'active'
  const roles = toRoleViews(user.roles)
  const permissions = user.permissions ?? []
  const certifications = normalizeCertifications(user.certifications)
  const resolvedCertifications =
    certifications.length > 0 ? certifications : certificationsFromRoles(user.roles)

  return {
    id: String(user.id),
    username,
    nickname: nickname ?? displayName,
    displayName,
    email: normalizeOptional(user.email),
    initials: deriveInitials(displayName),
    status,
    statusLabel: status === 'active' ? '已启用' : '已停用',
    isAdmin: roles.some((role) => role.key === 'admin'),
    certifications: resolvedCertifications,
    roles,
    permissionGroups: toPermissionGroups(permissions),
    permissionCount: permissions.length,
    capabilities: toCapabilities(permissions),
  }
}

function toRoleViews(roleKeys: readonly string[]): RoleView[] {
  return [...new Set(roleKeys)].map(describeRole)
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
    applyOrder: permissionAllows(
      permissions,
      CAPABILITY_PROBES.applyOrder.path,
      CAPABILITY_PROBES.applyOrder.method,
    ),
    submitOrderLog: permissionAllows(
      permissions,
      CAPABILITY_PROBES.submitOrderLog.path,
      CAPABILITY_PROBES.submitOrderLog.method,
    ),
    viewWallet: permissionAllows(
      permissions,
      CAPABILITY_PROBES.viewWallet.path,
      CAPABILITY_PROBES.viewWallet.method,
    ),
    redeemCode: permissionAllows(
      permissions,
      CAPABILITY_PROBES.redeemCode.path,
      CAPABILITY_PROBES.redeemCode.method,
    ),
    manageAdmin: permissionAllows(
      permissions,
      CAPABILITY_PROBES.manageAdmin.path,
      CAPABILITY_PROBES.manageAdmin.method,
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
