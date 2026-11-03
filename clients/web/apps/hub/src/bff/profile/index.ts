import { authBff } from '@/bff/auth'

import { HttpProfileGateway } from './gateway'
import { ProfileBff } from './service'

/** App-wide profile BFF singleton; pages only consume this instance. */
export const profileBff = new ProfileBff(new HttpProfileGateway(), authBff)

export { ProfileBff } from './service'
export { HttpProfileGateway } from './gateway'
export type { ProfileGateway } from './gateway'
export {
  formatApplicationStatus,
  formatApplicationType,
  joinSkills,
  splitSkills,
  toCertificationApplicationListModel,
  toCertificationApplicationView,
  toCooperationStatsView,
  toProfilePartyView,
  toPublicProfileView,
  toUserProfileView,
} from './mapper'
export type { CertificationApplicationInput, UpdateMyProfileInput } from './types'
