import type { BadgeTone, Certification, RoleView } from './identity'
import type { CertificationApplicationView } from './profile'

/** A user row in the admin console. */
export interface AdminUserView {
  id: string
  username: string
  nickname: string
  displayName: string
  fullName: string | null
  initials: string
  email: string | null
  certifications: Certification[]
  isActive: boolean
  statusLabel: string
  roleKeys: string[]
  roles: RoleView[]
  balanceCents: number
  balanceLabel: string
  createdAtLabel: string
}

export interface AdminUserListModel {
  users: AdminUserView[]
  total: number
  page: number
  pageSize: number
}

/** Role option loaded from the backend and labelled by the frontend. */
export interface AdminRoleOption {
  key: string
  label: string
  tone: BadgeTone
}

/** Applicant summary attached to an admin certification-review row. */
export interface AdminCertificationApplicantView {
  id: string
  username: string
  nickname: string
  displayName: string
  initials: string
  email: string | null
  roles: RoleView[]
  certifications: Certification[]
}

/** Certification application plus its applicant, as rendered by the review console. */
export interface AdminCertificationApplicationView extends CertificationApplicationView {
  applicant: AdminCertificationApplicantView | null
}

export interface AdminCertificationApplicationListModel {
  applications: AdminCertificationApplicationView[]
  total: number
  page: number
  pageSize: number
}

export type AdminRedeemCodeStatus = 'active' | 'used' | 'disabled'

/** Frontend-owned presentation metadata for a redeem-code status. */
export interface AdminRedeemCodeStatusMeta {
  key: AdminRedeemCodeStatus
  label: string
  tone: BadgeTone
}

export const ADMIN_REDEEM_CODE_STATUSES: readonly AdminRedeemCodeStatusMeta[] = [
  { key: 'active', label: '可用', tone: 'success' },
  { key: 'used', label: '已使用', tone: 'default' },
  { key: 'disabled', label: '已停用', tone: 'warning' },
]

export interface AdminRedeemCodeView {
  id: string
  code: string
  amountCents: number
  amountLabel: string
  status: AdminRedeemCodeStatus
  statusLabel: string
  statusTone: BadgeTone
  isExpired: boolean
  batchNo: string
  note: string | null
  usedByName: string | null
  usedAtLabel: string | null
  expiresAtLabel: string | null
  createdAtLabel: string
}

export interface AdminRedeemCodeListModel {
  codes: AdminRedeemCodeView[]
  total: number
  page: number
  pageSize: number
}

export interface AdminRedeemCodeBatch {
  batchNo: string
  codes: AdminRedeemCodeView[]
}

/** One editable system setting; labels and descriptions are frontend-owned. */
export interface AdminSettingView {
  key: string
  label: string
  description: string
  value: string
  multiline: boolean
  updatedAtLabel: string | null
}

export interface AdminSettingsModel {
  settings: AdminSettingView[]
}
