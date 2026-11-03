import type { AdminRedeemCodeStatus } from '@/models'

/** Page-facing admin inputs (camelCase, already validated by the page). */
export interface AdminUserFilter {
  q?: string
  role?: string
  page?: number
  pageSize?: number
}

/** Certification value accepted by the PATCH endpoint; `none` revokes the role. */
export type AdminCertificationInput = 'none' | 'enterprise' | 'engineer'

/** Payload for editing a user's profile/status or granting a certification. */
export interface UpdateAdminUserInput {
  fullName?: string
  email?: string | null
  isActive?: boolean
  certification?: AdminCertificationInput
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

/** Payload for generating one redeem-code batch; the gateway converts it to the wire shape. */
export interface CreateRedeemCodeInput {
  amountCents: number
  quantity: number
  expiresInDays: number | null
  note: string | null
}
