import type {
  RedeemResultView,
  WalletPageModel,
  WalletSummaryView,
  WalletTransactionListModel,
  WalletTransactionView,
} from '@/models'

import type {
  RedeemResultDto,
  WalletSummaryDto,
  WalletTransactionDto,
  WalletTransactionListDto,
} from '../dto'
import { toRedeemResultView, toWalletSummaryView, toWalletTransactionView } from '../mapper'

/** Deterministic DTO/view fixtures shared by the wallet BFF and page tests. */
export function buildWalletTransactionDto(
  overrides: Partial<WalletTransactionDto> = {},
): WalletTransactionDto {
  return {
    id: 1,
    type: 'order_payment',
    direction: 'debit',
    amount_cents: 50_000,
    balance_after_cents: 950_000,
    description: '发布需求托管',
    reference_type: 'order',
    reference_id: '42',
    created_at: '2026-11-01T06:20:00.000Z',
    ...overrides,
  }
}

export function buildWalletTransactionView(
  overrides: Partial<WalletTransactionView> = {},
): WalletTransactionView {
  return { ...toWalletTransactionView(buildWalletTransactionDto()), ...overrides }
}

export function buildWalletSummaryDto(overrides: Partial<WalletSummaryDto> = {}): WalletSummaryDto {
  return {
    balance_cents: 1_000_000,
    usage_total_cents: 200_000,
    recharge_total_cents: 500_000,
    redeem_total_cents: 100_000,
    income_total_cents: 300_000,
    recharge_enabled: false,
    recharge_note: '在线充值暂未开放，可联系客服线下充值。',
    support_contact: '客服微信：stellera-support',
    ...overrides,
  }
}

export function buildWalletSummaryView(
  overrides: Partial<WalletSummaryView> = {},
): WalletSummaryView {
  return { ...toWalletSummaryView(buildWalletSummaryDto()), ...overrides }
}

export function buildWalletTransactionListDto(
  items: WalletTransactionDto[] = [buildWalletTransactionDto()],
  overrides: Partial<WalletTransactionListDto> = {},
): WalletTransactionListDto {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 50,
    ...overrides,
  }
}

export function buildWalletTransactionListModel(
  transactions: WalletTransactionView[] = [buildWalletTransactionView()],
  overrides: Partial<WalletTransactionListModel> = {},
): WalletTransactionListModel {
  return { transactions, total: transactions.length, page: 1, pageSize: 50, ...overrides }
}

export function buildRedeemResultDto(overrides: Partial<RedeemResultDto> = {}): RedeemResultDto {
  return {
    amount_cents: 10_000,
    balance_cents: 1_010_000,
    transaction: buildWalletTransactionDto({
      id: 9,
      type: 'redeem',
      direction: 'credit',
      amount_cents: 10_000,
      balance_after_cents: 1_010_000,
      description: '兑换码充值',
      reference_type: 'redeem_code',
      reference_id: '3',
    }),
    ...overrides,
  }
}

export function buildRedeemResultView(overrides: Partial<RedeemResultView> = {}): RedeemResultView {
  return { ...toRedeemResultView(buildRedeemResultDto()), ...overrides }
}

export function buildWalletPageModel(overrides: Partial<WalletPageModel> = {}): WalletPageModel {
  return {
    summary: buildWalletSummaryView(),
    transactions: buildWalletTransactionListModel(),
    rechargeRecords: [],
    ...overrides,
  }
}
