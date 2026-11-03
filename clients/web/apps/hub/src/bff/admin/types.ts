import type { AdminRedeemCodeStatus } from '@/models'

/** Page-facing admin inputs (camelCase, already validated by the page). */
export interface AdminUserFilter {
  q?: string
  role?: string
  page?: number
  pageSize?: number
}

/** Payload for toggling a user's status or replacing its role set. */
export interface UpdateAdminUserInput {
  isActive?: boolean
  roles?: string[]
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
