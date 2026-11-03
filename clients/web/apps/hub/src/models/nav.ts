import { MODEL_SQUARE_URL } from '@/config/modelSquare'

import type { IconName } from './icons'

/** A navigation entry (second level of the console sidebar): internal route or external link. */
export interface NavLeaf {
  key: string
  label: string
  icon: IconName
  /** Vue Router route name for internal entries. */
  routeName?: string
  /** Absolute URL for external entries (rendered as a new-tab link). */
  href?: string
  external?: boolean
  /** Small right-aligned marker, e.g. the realtime hint on the order hall. */
  meta?: string
}

/** A first-level navigation group that owns one or more leaves. */
export interface NavGroup {
  key: string
  label: string
  icon: IconName
  children: readonly NavLeaf[]
  /** Admin-only groups are filtered out for every other viewer. */
  requiresAdmin?: boolean
}

/**
 * Frontend-owned sidebar tree.
 *
 * The backend never decides navigation labels or ordering. Groups are collapsible; the active leaf is
 * resolved from the current route name so pages never pass an `activeKey` down.
 */
export const CONSOLE_NAV: readonly NavGroup[] = [
  {
    key: 'platform',
    label: '平台',
    icon: 'intro',
    children: [
      { key: 'intro', label: '平台简介', icon: 'intro', routeName: 'intro' },
      {
        key: 'model-square',
        label: '模型广场',
        icon: 'spark',
        href: MODEL_SQUARE_URL,
        external: true,
      },
    ],
  },
  {
    key: 'account',
    label: '个人',
    icon: 'user',
    children: [{ key: 'profile', label: '个人信息', icon: 'user', routeName: 'profile' }],
  },
  {
    key: 'fde',
    label: 'FDE 订单',
    icon: 'briefcase',
    children: [
      {
        key: 'fde-hall',
        label: '订单大厅',
        icon: 'live',
        routeName: 'fde-hall',
        meta: '实时',
      },
      {
        key: 'fde-published',
        label: '我发布的',
        icon: 'orders',
        routeName: 'fde-published',
      },
      {
        key: 'fde-assigned',
        label: '我接到的',
        icon: 'wrench',
        routeName: 'fde-assigned',
      },
      {
        key: 'fde-applications',
        label: '我的申请',
        icon: 'logs',
        routeName: 'fde-applications',
      },
    ],
  },
  {
    key: 'wallet',
    label: '钱包',
    icon: 'wallet',
    children: [{ key: 'wallet', label: '我的钱包', icon: 'wallet', routeName: 'wallet' }],
  },
  {
    key: 'admin',
    label: '管理',
    icon: 'settings',
    requiresAdmin: true,
    children: [
      { key: 'admin-users', label: '用户', icon: 'user', routeName: 'admin-users' },
      {
        key: 'admin-certifications',
        label: '认证审核',
        icon: 'shield',
        routeName: 'admin-certifications',
      },
      {
        key: 'admin-redeem-codes',
        label: '兑换码',
        icon: 'ticket',
        routeName: 'admin-redeem-codes',
      },
      { key: 'admin-settings', label: '系统设置', icon: 'settings', routeName: 'admin-settings' },
    ],
  },
]

export interface ResolvedNavLeaf {
  group: NavGroup
  leaf: NavLeaf
}

/** Filter the console tree for the current viewer; admin groups never render for other roles. */
export function navForViewer(viewer: { isAdmin: boolean }): NavGroup[] {
  return CONSOLE_NAV.filter((group) => !group.requiresAdmin || viewer.isAdmin)
}

/** Resolve the group/leaf pair that owns a route name (used for active + expanded state). */
export function findNavGroupForRoute(
  routeName: string | symbol | null | undefined,
  groups: readonly NavGroup[] = CONSOLE_NAV,
): ResolvedNavLeaf | null {
  if (typeof routeName !== 'string') return null

  for (const group of groups) {
    const leaf = group.children.find((child) => child.routeName === routeName)
    if (leaf) return { group, leaf }
  }
  return null
}
