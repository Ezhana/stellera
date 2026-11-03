import { authBff } from '@/bff/auth'

import { HttpAdminGateway } from './gateway'
import { AdminBff } from './service'

/** App-wide admin BFF singleton; pages only consume this instance. */
export const adminBff = new AdminBff(new HttpAdminGateway(), authBff)

export { AdminBff } from './service'
export { HttpAdminGateway } from './gateway'
export type { AdminGateway } from './gateway'
export {
  formatRedeemCodeStatus,
  toAdminRedeemCodeBatch,
  toAdminRedeemCodeListModel,
  toAdminRedeemCodeView,
  toAdminRoleOption,
  toAdminSettingView,
  toAdminSettingsModel,
  toAdminUserListModel,
  toAdminUserView,
} from './mapper'
export type {
  AdminRedeemCodeFilter,
  AdminUserFilter,
  CreateRedeemCodeInput,
  UpdateAdminUserInput,
} from './types'
