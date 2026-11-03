import type {
  ApplicationListModel,
  ApplicationStatus,
  ApplicationType,
  BadgeTone,
  EscrowStatus,
  FdeOrderDetailView,
  FdeOrderStatus,
  FdeOrderStatusMeta,
  FdeOrderView,
  OrderApplicationView,
  OrderStatsView,
  WorkLogView,
} from '@/models'
import { APPLICATION_STATUSES, APPLICATION_TYPES, FDE_ORDER_STATUSES } from '@/models'

import { formatCents, formatDateTimeLabel } from '@/lib/money'

import { normalizeCertification } from '../certification'
import type {
  ApplicationDto,
  ApplicationListDto,
  OrderDetailDto,
  OrderDto,
  WorkLogDto,
} from './dto'

/** Label + tone pair rendered by a chip; unknown backend values keep the raw key. */
export type StatusPresentation = Pick<FdeOrderStatusMeta, 'label' | 'tone'>

const STATUS_META: ReadonlyMap<string, StatusPresentation> = new Map(
  FDE_ORDER_STATUSES.map((meta) => [meta.key, { label: meta.label, tone: meta.tone }]),
)

const APPLICATION_TYPE_META: ReadonlyMap<string, StatusPresentation> = new Map(
  APPLICATION_TYPES.map((meta) => [meta.key, { label: meta.label, tone: meta.tone }]),
)

const APPLICATION_STATUS_META: ReadonlyMap<string, StatusPresentation> = new Map(
  APPLICATION_STATUSES.map((meta) => [meta.key, { label: meta.label, tone: meta.tone }]),
)

const ESCROW_META: ReadonlyMap<string, StatusPresentation> = new Map([
  ['held', { label: '资金托管中', tone: 'accent' }],
  ['released', { label: '已结算', tone: 'success' }],
  ['refunded', { label: '已退回', tone: 'default' }],
])

/** Known status labels/tones; unknown values degrade to the raw key + default tone. */
export function formatStatus(status: string): StatusPresentation {
  return STATUS_META.get(status) ?? { label: status || '未知状态', tone: 'default' }
}

/** Known escrow labels/tones; unknown values degrade to the raw key + default tone. */
export function formatEscrow(escrowStatus: string): StatusPresentation {
  return ESCROW_META.get(escrowStatus) ?? { label: escrowStatus || '未知托管状态', tone: 'default' }
}

/** Known application-type labels/tones; unknown values degrade to the raw key. */
export function formatApplicationType(type: string): StatusPresentation {
  return APPLICATION_TYPE_META.get(type) ?? { label: type || '未知申请类型', tone: 'default' }
}

/** Known application-status labels/tones; unknown values degrade to the raw key. */
export function formatApplicationStatus(status: string): StatusPresentation {
  return APPLICATION_STATUS_META.get(status) ?? { label: status || '未知申请状态', tone: 'default' }
}

/** Backwards-compatible alias for the shared formatter in `lib/money`. */
export const formatPriceCents = formatCents

export { formatDateTimeLabel }

/** `7 天` */
export function formatDeliveryLabel(deliveryDays: number): string {
  const days = Number.isFinite(deliveryDays) ? Math.trunc(deliveryDays) : 0
  return `${days} 天`
}

export function toWorkLogView(dto: WorkLogDto): WorkLogView {
  return {
    id: String(dto.id),
    authorName: dto.author.display_name,
    content: dto.content,
    workedHours: dto.worked_hours,
    createdAtLabel: formatDateTimeLabel(dto.created_at),
  }
}

/** Map a wire order DTO into the stable page model. */
export function toOrderView(dto: OrderDto): FdeOrderView {
  const status = formatStatus(dto.status)
  const escrow = formatEscrow(dto.escrow_status)

  return {
    id: String(dto.id),
    code: dto.code,
    title: dto.title,
    industry: dto.industry,
    description: dto.description,
    deliveryDays: dto.delivery_days,
    deliveryLabel: formatDeliveryLabel(dto.delivery_days),
    priceCents: dto.price_cents,
    priceLabel: formatPriceCents(dto.price_cents),
    status: dto.status as FdeOrderStatus,
    statusLabel: status.label,
    statusTone: status.tone,
    escrowStatus: dto.escrow_status as EscrowStatus,
    escrowLabel: escrow.label,
    escrowTone: escrow.tone,
    publisherId: String(dto.publisher.id),
    publisherName: dto.publisher.display_name,
    publisherCertification: normalizeCertification(dto.publisher.certification),
    engineerId: dto.engineer ? String(dto.engineer.id) : null,
    engineerName: dto.engineer?.display_name ?? null,
    engineerCertification: normalizeCertification(dto.engineer?.certification),
    workLogCount: dto.work_log_count,
    createdAt: dto.created_at,
    publishedAtLabel: formatDateTimeLabel(dto.created_at),
    updatedAtLabel: formatDateTimeLabel(dto.updated_at),
    claimedAtLabel: dto.claimed_at ? formatDateTimeLabel(dto.claimed_at) : null,
    completedAtLabel: dto.completed_at ? formatDateTimeLabel(dto.completed_at) : null,
  }
}

/** Map a detail DTO (order + logs) into the detail page model. */
export function toOrderDetailView(dto: OrderDetailDto): FdeOrderDetailView {
  return {
    ...toOrderView(dto),
    logs: dto.logs.map(toWorkLogView),
  }
}

/** Map one application DTO into the stable page model. */
export function toApplicationView(dto: ApplicationDto): OrderApplicationView {
  const type = formatApplicationType(dto.type)
  const status = formatApplicationStatus(dto.status)

  return {
    id: String(dto.id),
    order: toOrderView(dto.order),
    type: dto.type as ApplicationType,
    typeLabel: type.label,
    typeTone: type.tone,
    status: dto.status as ApplicationStatus,
    statusLabel: status.label,
    statusTone: status.tone,
    message: dto.message,
    reviewNote: dto.review_note,
    applicantName: dto.applicant.display_name,
    applicantCertification: normalizeCertification(dto.applicant.certification),
    reviewerName: dto.reviewer?.display_name ?? null,
    reviewedAtLabel: dto.reviewed_at ? formatDateTimeLabel(dto.reviewed_at) : null,
    createdAtLabel: formatDateTimeLabel(dto.created_at),
  }
}

/** Map one application list page. */
export function toApplicationListModel(dto: ApplicationListDto): ApplicationListModel {
  const applications = dto.items.map(toApplicationView)
  return {
    applications,
    total: dto.total > 0 ? dto.total : applications.length,
    page: dto.page,
    pageSize: dto.page_size,
  }
}

/** Aggregate the stat cards from the loaded orders (client-side, filter-independent). */
export function summarizeOrders(orders: readonly FdeOrderView[]): OrderStatsView {
  let openCount = 0
  let inProgressCount = 0
  let completedCount = 0
  let escrowHeldCents = 0

  for (const order of orders) {
    if (order.status === 'open') openCount += 1
    else if (order.status === 'in_progress') inProgressCount += 1
    else if (order.status === 'completed') completedCount += 1

    if (order.escrowStatus === 'held') escrowHeldCents += order.priceCents
  }

  return {
    total: orders.length,
    openCount,
    inProgressCount,
    completedCount,
    escrowHeldCents,
    escrowHeldLabel: formatPriceCents(escrowHeldCents),
  }
}

function compareNewestFirst(left: FdeOrderView, right: FdeOrderView): number {
  const leftTime = Date.parse(left.createdAt)
  const rightTime = Date.parse(right.createdAt)
  const leftValid = Number.isFinite(leftTime)
  const rightValid = Number.isFinite(rightTime)

  if (leftValid && rightValid && leftTime !== rightTime) return rightTime - leftTime
  if (leftValid !== rightValid) return leftValid ? -1 : 1

  const leftId = Number(left.id)
  const rightId = Number(right.id)
  if (Number.isFinite(leftId) && Number.isFinite(rightId) && leftId !== rightId) {
    return rightId - leftId
  }
  return right.id.localeCompare(left.id)
}

/**
 * Replace an order by id (or insert it) and keep the list newest-first.
 * Realtime events use this so a changed order keeps one row in the hall.
 */
export function upsertOrder(orders: readonly FdeOrderView[], order: FdeOrderView): FdeOrderView[] {
  const next = orders.filter((existing) => existing.id !== order.id)
  next.push(order)
  return next.sort(compareNewestFirst)
}

/** Tone helper for components that render a raw status key. */
export function toneForStatus(status: FdeOrderStatus | string): BadgeTone {
  return formatStatus(status).tone
}
