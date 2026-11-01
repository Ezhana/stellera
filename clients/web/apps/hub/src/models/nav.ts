import type { IconName } from './icons'

/** A routable navigation entry (second level of the console sidebar). */
export interface NavLeaf {
  key: string
  label: string
  icon: IconName
  routeName: string
  /** Small right-aligned marker, e.g. the realtime hint on the order hall. */
  meta?: string
}

/** A first-level navigation group that owns one or more leaves. */
export interface NavGroup {
  key: string
  label: string
  icon: IconName
  children: readonly NavLeaf[]
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
    children: [{ key: 'intro', label: '平台简介', icon: 'intro', routeName: 'intro' }],
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
    ],
  },
]

export interface ResolvedNavLeaf {
  group: NavGroup
  leaf: NavLeaf
}

/** Resolve the group/leaf pair that owns a route name (used for active + expanded state). */
export function findNavGroupForRoute(
  routeName: string | symbol | null | undefined,
): ResolvedNavLeaf | null {
  if (typeof routeName !== 'string') return null

  for (const group of CONSOLE_NAV) {
    const leaf = group.children.find((child) => child.routeName === routeName)
    if (leaf) return { group, leaf }
  }
  return null
}
