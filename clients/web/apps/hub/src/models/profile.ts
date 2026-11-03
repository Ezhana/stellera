import type { BadgeTone, Certification, RoleView } from './identity'

/** Compact user reference rendered next to a cooperation record or an application. */
export interface ProfilePartyView {
  id: string
  displayName: string
  certifications: Certification[]
}

/** Role played by the viewer in one completed order. */
export type CooperationRole = 'publisher' | 'engineer'

export interface CooperationRecordView {
  orderId: string
  code: string
  title: string
  priceCents: number
  priceLabel: string
  completedAtLabel: string
  role: CooperationRole
  roleLabel: string
  counterpart: ProfilePartyView | null
}

export interface CooperationStatsView {
  completedCount: number
  partnerCount: number
  totalAmountCents: number
  totalAmountLabel: string
  records: CooperationRecordView[]
}

/** My own profile: everything the authenticated user may edit or see about themselves. */
export interface UserProfileView {
  id: string
  username: string
  nickname: string
  email: string | null
  realName: string | null
  bio: string
  skills: string[]
  city: string
  contactPhone: string
  contactWechat: string
  roles: RoleView[]
  certifications: Certification[]
  createdAtLabel: string
  cooperation: CooperationStatsView
}

/** Someone else's public profile; sensitive fields are simply absent from the model. */
export interface PublicProfileView {
  id: string
  nickname: string
  bio: string
  skills: string[]
  city: string
  certifications: Certification[]
  memberSinceLabel: string
  cooperation: CooperationStatsView
}

export type CertificationApplicationStatus = 'pending' | 'approved' | 'rejected'

export interface CertificationApplicationStatusMeta {
  key: CertificationApplicationStatus
  label: string
  tone: BadgeTone
}

/** Frontend-owned status catalogue for the certification-review screens. */
export const CERTIFICATION_APPLICATION_STATUSES: readonly CertificationApplicationStatusMeta[] = [
  { key: 'pending', label: '待审核', tone: 'warning' },
  { key: 'approved', label: '已通过', tone: 'success' },
  { key: 'rejected', label: '已驳回', tone: 'error' },
]

export type CertificationApplicationType = 'realname' | 'enterprise' | 'engineer'

export interface CertificationApplicationTypeMeta {
  key: CertificationApplicationType
  label: string
  tone: BadgeTone
}

/** Frontend-owned type catalogue; ordering matches the certification stack. */
export const CERTIFICATION_APPLICATION_TYPES: readonly CertificationApplicationTypeMeta[] = [
  { key: 'realname', label: '实名认证', tone: 'info' },
  { key: 'enterprise', label: '企业认证', tone: 'accent' },
  { key: 'engineer', label: '工程师认证', tone: 'success' },
]

/** One certification application with its review record. */
export interface CertificationApplicationView {
  id: string
  type: CertificationApplicationType
  typeLabel: string
  typeTone: BadgeTone
  status: CertificationApplicationStatus
  statusLabel: string
  statusTone: BadgeTone
  realName: string
  idNumber: string
  contactPhone: string
  companyName: string
  creditCode: string
  contactName: string
  skills: string
  workYears: number | null
  projectExperience: string
  description: string
  reviewNote: string | null
  reviewer: ProfilePartyView | null
  reviewedAtLabel: string | null
  createdAtLabel: string
}

export interface CertificationApplicationListModel {
  applications: CertificationApplicationView[]
}
