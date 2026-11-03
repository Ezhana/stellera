import type {
  AdminRedeemCodeStatus,
  CertificationApplicationStatus,
  CertificationApplicationType,
} from '@/models'

/** Page-facing admin inputs (camelCase, already validated by the page). */
export interface AdminUserFilter {
  q?: string
  role?: string
  page?: number
  pageSize?: number
}

/** Payload for editing a user's nickname/email or enable state; roles are never edited directly. */
export interface UpdateAdminUserInput {
  nickname?: string
  email?: string | null
  isActive?: boolean
}

/** Payload for an admin balance adjustment; amounts travel in integer cents. */
export interface AdminWalletAdjustmentInput {
  direction: 'credit' | 'debit'
  amountCents: number
  note: string
}

export interface AdminRedeemCodeFilter {
  status?: AdminRedeemCodeStatus | 'all'
  q?: string
  page?: number
  pageSize?: number
}

/** Filter for the certification review console. */
export interface AdminCertificationApplicationFilter {
  status?: CertificationApplicationStatus | 'all'
  type?: CertificationApplicationType | 'all'
  q?: string
  page?: number
  pageSize?: number
}

/** Payload for generating one redeem-code batch; the gateway converts it to the wire shape. */
export interface CreateRedeemCodeInput {
  amountCents: number
  quantity: number
  expiresInDays: number | null
  note: string | null
}
