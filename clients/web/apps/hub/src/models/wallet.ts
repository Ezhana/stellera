import type { BadgeTone } from './identity'

/** Ledger transaction types exposed by the wallet API. */
export type WalletTransactionType =
  'recharge' | 'redeem' | 'order_payment' | 'order_refund' | 'order_settlement'

/** Frontend-owned presentation metadata for a transaction type. */
export interface WalletTransactionTypeMeta {
  key: WalletTransactionType
  label: string
  tone: BadgeTone
}

/** Filter catalogue for the usage tab; the backend never decides these labels. */
export const WALLET_TRANSACTION_TYPES: readonly WalletTransactionTypeMeta[] = [
  { key: 'order_payment', label: '消费', tone: 'warning' },
  { key: 'order_refund', label: '退款', tone: 'info' },
  { key: 'order_settlement', label: '结算', tone: 'success' },
  { key: 'redeem', label: '兑换', tone: 'accent' },
  { key: 'recharge', label: '充值', tone: 'success' },
]

/** A single ledger row; no backend field names leak through. */
export interface WalletTransactionView {
  id: string
  type: WalletTransactionType | 'unknown'
  typeLabel: string
  typeTone: BadgeTone
  direction: 'credit' | 'debit'
  amountCents: number
  /** Signed, e.g. `+¥100` / `-¥25.50`. */
  amountLabel: string
  balanceAfterCents: number
  balanceAfterLabel: string
  description: string
  referenceType: string | null
  referenceId: string | null
  createdAtLabel: string
}

/** Wallet header numbers plus the recharge copy maintained by the backend settings. */
export interface WalletSummaryView {
  balanceCents: number
  balanceLabel: string
  usageTotalCents: number
  usageTotalLabel: string
  rechargeTotalCents: number
  rechargeTotalLabel: string
  redeemTotalCents: number
  redeemTotalLabel: string
  incomeTotalCents: number
  incomeTotalLabel: string
  rechargeEnabled: boolean
  rechargeNote: string
  supportContact: string
}

/** One page of ledger rows. */
export interface WalletTransactionListModel {
  transactions: WalletTransactionView[]
  total: number
  page: number
  pageSize: number
}

export interface WalletTransactionFilter {
  type?: WalletTransactionType | 'all'
  page?: number
  pageSize?: number
}

export interface RedeemResultView {
  amountCents: number
  amountLabel: string
  balanceCents: number
  balanceLabel: string
  transaction: WalletTransactionView
}

/** Page model consumed by `WalletPage`: summary, recent usage and recharge history. */
export interface WalletPageModel {
  summary: WalletSummaryView
  transactions: WalletTransactionListModel
  rechargeRecords: WalletTransactionView[]
}
