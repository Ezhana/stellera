import type {
  BadgeTone,
  RedeemResultView,
  WalletSummaryView,
  WalletTransactionListModel,
  WalletTransactionType,
  WalletTransactionView,
} from '@/models'
import { formatCents, formatDateTimeLabel } from '@/lib/money'

import type {
  RedeemResultDto,
  WalletSummaryDto,
  WalletTransactionDto,
  WalletTransactionListDto,
} from './dto'

/** Presentation pair rendered by a chip; unknown backend types keep the raw key. */
export interface TransactionTypePresentation {
  type: WalletTransactionType | 'unknown'
  label: string
  tone: BadgeTone
  direction: 'credit' | 'debit'
}

const TYPE_META: ReadonlyMap<string, Omit<TransactionTypePresentation, 'type'>> = new Map([
  ['recharge', { label: '充值', tone: 'success', direction: 'credit' }],
  ['redeem', { label: '兑换', tone: 'accent', direction: 'credit' }],
  ['order_payment', { label: '消费', tone: 'warning', direction: 'debit' }],
  ['order_refund', { label: '退款', tone: 'info', direction: 'credit' }],
  ['order_settlement', { label: '结算收入', tone: 'success', direction: 'credit' }],
  ['adjustment', { label: '余额调整', tone: 'info', direction: 'credit' }],
])

/** Known type labels/tones/signs; unknown values degrade to the raw key + default tone. */
export function formatTransactionType(type: string): TransactionTypePresentation {
  const meta = TYPE_META.get(type)
  if (meta) return { ...meta, type: type as WalletTransactionType }
  return {
    type: 'unknown',
    label: type || '未知类型',
    tone: 'default',
    direction: 'credit',
  }
}

/** `+¥100` / `-¥25.50` — the sign follows the ledger direction, not the raw amount. */
export function formatSignedAmount(cents: number, direction: 'credit' | 'debit'): string {
  const sign = direction === 'debit' ? '-' : '+'
  return `${sign}${formatCents(Math.abs(cents))}`
}

export function toWalletTransactionView(dto: WalletTransactionDto): WalletTransactionView {
  const type = formatTransactionType(dto.type)
  const direction =
    dto.direction === 'credit' || dto.direction === 'debit' ? dto.direction : type.direction

  return {
    id: String(dto.id),
    type: type.type,
    typeLabel: type.label,
    typeTone: type.tone,
    direction,
    amountCents: dto.amount_cents,
    amountLabel: formatSignedAmount(dto.amount_cents, direction),
    balanceAfterCents: dto.balance_after_cents,
    balanceAfterLabel: formatCents(dto.balance_after_cents),
    description: dto.description,
    referenceType: dto.reference_type,
    referenceId: dto.reference_id,
    createdAtLabel: formatDateTimeLabel(dto.created_at),
  }
}

export function toWalletSummaryView(dto: WalletSummaryDto): WalletSummaryView {
  return {
    balanceCents: dto.balance_cents,
    balanceLabel: formatCents(dto.balance_cents),
    usageTotalCents: dto.usage_total_cents,
    usageTotalLabel: formatCents(dto.usage_total_cents),
    rechargeTotalCents: dto.recharge_total_cents,
    rechargeTotalLabel: formatCents(dto.recharge_total_cents),
    redeemTotalCents: dto.redeem_total_cents,
    redeemTotalLabel: formatCents(dto.redeem_total_cents),
    incomeTotalCents: dto.income_total_cents,
    incomeTotalLabel: formatCents(dto.income_total_cents),
    rechargeEnabled: dto.recharge_enabled,
    rechargeNote: dto.recharge_note,
    supportContact: dto.support_contact,
  }
}

export function toWalletTransactionListModel(
  dto: WalletTransactionListDto,
): WalletTransactionListModel {
  const transactions = dto.items.map(toWalletTransactionView)
  return {
    transactions,
    total: dto.total > 0 ? dto.total : transactions.length,
    page: dto.page,
    pageSize: dto.page_size,
  }
}

export function toRedeemResultView(dto: RedeemResultDto): RedeemResultView {
  return {
    amountCents: dto.amount_cents,
    amountLabel: formatCents(dto.amount_cents),
    balanceCents: dto.balance_cents,
    balanceLabel: formatCents(dto.balance_cents),
    transaction: toWalletTransactionView(dto.transaction),
  }
}
