import type { IconName } from './icons'

/** Business modules the hub fronts. Keys are stable frontend-owned identifiers. */
export type ModuleKey = 'wallet' | 'orders' | 'plaza'

/** Effective access the current viewer has on a module, derived by the BFF. */
export type ModuleAccess = 'write' | 'read' | 'none'

/**
 * Frontend-owned module catalog.
 *
 * The backend only returns permission objects/actions; it does not own labels, ordering,
 * descriptions or probe paths. The BFF uses `probePath` to derive module access, while pages render
 * the stable fields below.
 */
export interface ModuleDefinition {
  key: ModuleKey
  code: string
  label: string
  description: string
  icon: IconName
  /** Internal policy probe path; never exposed in page models. */
  probePath: string
}

export const MODULE_CATALOG: readonly ModuleDefinition[] = [
  {
    key: 'wallet',
    code: 'WALLET',
    label: '钱包',
    description: '账户余额、资金流水与结算视图。',
    icon: 'wallet',
    probePath: '/api/v1/wallet/overview',
  },
  {
    key: 'orders',
    code: 'ORDERS',
    label: '订单',
    description: '订单状态、履约进度与异常处理。',
    icon: 'orders',
    probePath: '/api/v1/orders',
  },
  {
    key: 'plaza',
    code: 'PLAZA',
    label: '广场',
    description: '公告、社区内容与运营活动。',
    icon: 'plaza',
    probePath: '/api/v1/plaza/overview',
  },
]
