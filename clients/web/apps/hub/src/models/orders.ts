import type { BadgeTone, Certification } from './identity'

/** FDE order lifecycle status (stable frontend union). */
export type FdeOrderStatus = 'open' | 'in_progress' | 'completed' | 'cancelled'

/** Escrow state of the money attached to an order. */
export type EscrowStatus = 'held' | 'released' | 'refunded'

/** Frontend-owned presentation metadata for a status value. */
export interface FdeOrderStatusMeta {
  key: FdeOrderStatus
  label: string
  tone: BadgeTone
}

/**
 * Status filter catalogue for the order pages.
 *
 * The backend never decides labels, ordering or tones; the frontend owns this list.
 */
export const FDE_ORDER_STATUSES: readonly FdeOrderStatusMeta[] = [
  { key: 'open', label: '待接单', tone: 'warning' },
  { key: 'in_progress', label: '交付中', tone: 'info' },
  { key: 'completed', label: '已完成', tone: 'success' },
  { key: 'cancelled', label: '已取消', tone: 'default' },
]

/** Industry catalogue used by the publish form and the hall filter. */
export const FDE_INDUSTRIES: readonly string[] = [
  '医疗健康',
  '金融保险',
  '智能制造',
  '能源电力',
  '零售消费',
  '教育科研',
  '政务公共服务',
  '其他',
]

/** A single delivery log entry shown on an order detail. */
export interface WorkLogView {
  id: string
  authorName: string
  content: string
  workedHours: number | null
  createdAtLabel: string
}

/** Stable page model of a single FDE order; no backend field names leak through. */
export interface FdeOrderView {
  id: string
  code: string
  title: string
  industry: string
  description: string
  deliveryDays: number
  deliveryLabel: string
  priceCents: number
  priceLabel: string
  status: FdeOrderStatus
  statusLabel: string
  statusTone: BadgeTone
  escrowStatus: EscrowStatus
  escrowLabel: string
  escrowTone: BadgeTone
  publisherId: string
  publisherName: string
  publisherCertifications: Certification[]
  engineerId: string | null
  engineerName: string | null
  engineerCertifications: Certification[]
  workLogCount: number
  createdAt: string
  publishedAtLabel: string
  updatedAtLabel: string
  claimedAtLabel: string | null
  completedAtLabel: string | null
}

/** Order detail page model (order + its delivery logs + every application on it). */
export interface FdeOrderDetailView extends FdeOrderView {
  logs: WorkLogView[]
  applications: OrderApplicationView[]
}

/** Client-side filter state shared by the hall and the published-orders page. */
export interface OrderListFilter {
  status?: FdeOrderStatus | 'all'
  industry?: string
  keyword?: string
}

/** Aggregate numbers shown by the stat cards. */
export interface OrderStatsView {
  total: number
  openCount: number
  inProgressCount: number
  completedCount: number
  escrowHeldCents: number
  escrowHeldLabel: string
}

/** Completed list page model returned by the orders BFF. */
export interface OrderListModel {
  orders: FdeOrderView[]
  total: number
  stats: OrderStatsView
  fetchedAt: string
}

export type OrderHallPageModel = OrderListModel
export type PublishedOrdersPageModel = OrderListModel
export type AssignedOrdersPageModel = OrderListModel

/** A publisher-side or engineer-side request attached to an order. */
export type ApplicationType = 'accept' | 'delivery'

/** Application lifecycle status (stable frontend union). */
export type ApplicationStatus = 'pending' | 'approved' | 'rejected' | 'withdrawn'

/** Frontend-owned presentation metadata for an application type. */
export interface ApplicationTypeMeta {
  key: ApplicationType
  label: string
  tone: BadgeTone
}

export const APPLICATION_TYPES: readonly ApplicationTypeMeta[] = [
  { key: 'accept', label: '接单申请', tone: 'info' },
  { key: 'delivery', label: '交付申请', tone: 'accent' },
]

/** Frontend-owned presentation metadata for an application status. */
export interface ApplicationStatusMeta {
  key: ApplicationStatus
  label: string
  tone: BadgeTone
}

export const APPLICATION_STATUSES: readonly ApplicationStatusMeta[] = [
  { key: 'pending', label: '待审批', tone: 'warning' },
  { key: 'approved', label: '已通过', tone: 'success' },
  { key: 'rejected', label: '已驳回', tone: 'error' },
  { key: 'withdrawn', label: '已撤回', tone: 'default' },
]

/** Stable page model of one order application. */
export interface OrderApplicationView {
  id: string
  order: FdeOrderView
  type: ApplicationType
  typeLabel: string
  typeTone: BadgeTone
  status: ApplicationStatus
  statusLabel: string
  statusTone: BadgeTone
  message: string | null
  reviewNote: string | null
  applicantId: string
  applicantName: string
  applicantCertifications: Certification[]
  reviewerId: string | null
  reviewerName: string | null
  reviewerCertifications: Certification[]
  reviewedAtLabel: string | null
  createdAtLabel: string
}

/** Filter shared by the "my applications" and "received applications" lists. */
export interface ApplicationListFilter {
  type?: ApplicationType | 'all'
  status?: ApplicationStatus | 'all'
  page?: number
  pageSize?: number
}

export interface ApplicationListModel {
  applications: OrderApplicationView[]
  total: number
  page: number
  pageSize: number
}

export type ApplicationsPageModel = ApplicationListModel
