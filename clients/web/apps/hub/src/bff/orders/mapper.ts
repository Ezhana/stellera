import type {
  BadgeTone,
  EscrowStatus,
  FdeOrderDetailView,
  FdeOrderStatus,
  FdeOrderStatusMeta,
  FdeOrderView,
  OrderStatsView,
  WorkLogView,
} from '@/models'
import { FDE_ORDER_STATUSES } from '@/models'

import type { OrderDetailDto, OrderDto, WorkLogDto } from './dto'

/** Label + tone pair rendered by a chip; unknown backend values keep the raw key. */
export type StatusPresentation = Pick<FdeOrderStatusMeta, 'label' | 'tone'>

const STATUS_META: ReadonlyMap<string, StatusPresentation> = new Map(
  FDE_ORDER_STATUSES.map((meta) => [meta.key, { label: meta.label, tone: meta.tone }]),
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

/** `¥86,000` / `¥123.45` — grouped yuan with tabular-friendly output (no locale surprises). */
export function formatPriceCents(cents: number): string {
  const safe = Number.isFinite(cents) ? Math.round(cents) : 0
  const sign = safe < 0 ? '-' : ''
  const absolute = Math.abs(safe)
  const yuan = Math.floor(absolute / 100)
  const fen = absolute % 100
  const grouped = String(yuan).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const fraction = fen === 0 ? '' : `.${String(fen).padStart(2, '0')}`
  return `${sign}¥${grouped}${fraction}`
}

function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

/**
 * `11-01 14:20` (other day) or `今天 14:20` (same local day).
 *
 * Uses the browser's local timezone; `now` is injectable so tests stay deterministic.
 */
export function formatDateTimeLabel(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'

  const time = `${pad2(date.getHours())}:${pad2(date.getMinutes())}`
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  if (sameDay) return `今天 ${time}`

  return `${pad2(date.getMonth() + 1)}-${pad2(date.getDate())} ${time}`
}

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
    engineerId: dto.engineer ? String(dto.engineer.id) : null,
    engineerName: dto.engineer?.display_name ?? null,
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
