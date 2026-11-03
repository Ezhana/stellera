import { describe, expect, it } from 'vitest'

import {
  formatSignedAmount,
  formatTransactionType,
  toRedeemResultView,
  toWalletSummaryView,
  toWalletTransactionListModel,
  toWalletTransactionView,
} from '../mapper'
import {
  buildRedeemResultDto,
  buildWalletSummaryDto,
  buildWalletTransactionDto,
  buildWalletTransactionListDto,
} from './fixtures'

describe('wallet mapper type presentation', () => {
  it('maps known transaction types to labels, tones and default signs', () => {
    expect(formatTransactionType('recharge')).toEqual({
      type: 'recharge',
      label: '充值',
      tone: 'success',
      direction: 'credit',
    })
    expect(formatTransactionType('redeem')).toMatchObject({ label: '兑换', tone: 'accent' })
    expect(formatTransactionType('order_payment')).toMatchObject({
      label: '消费',
      tone: 'warning',
      direction: 'debit',
    })
    expect(formatTransactionType('order_refund')).toMatchObject({ label: '退款', tone: 'info' })
    expect(formatTransactionType('order_settlement')).toMatchObject({
      label: '结算收入',
      tone: 'success',
    })
  })

  it('degrades unknown and empty types to the raw key with a default tone', () => {
    expect(formatTransactionType('mystery_bonus')).toEqual({
      type: 'unknown',
      label: 'mystery_bonus',
      tone: 'default',
      direction: 'credit',
    })
    expect(formatTransactionType('')).toMatchObject({ label: '未知类型', tone: 'default' })
  })

  it('formats signed amounts from the ledger direction', () => {
    expect(formatSignedAmount(10_000, 'credit')).toBe('+¥100')
    expect(formatSignedAmount(2_550, 'debit')).toBe('-¥25.50')
    expect(formatSignedAmount(-2_550, 'debit')).toBe('-¥25.50')
  })
})

describe('wallet mapper DTO → page model', () => {
  it('maps a credit transaction row', () => {
    const view = toWalletTransactionView(
      buildWalletTransactionDto({
        id: 'tx-1',
        type: 'recharge',
        direction: 'credit',
        amount_cents: 10_000,
        balance_after_cents: 1_010_000,
        description: '线下充值',
        reference_type: 'manual',
        reference_id: '5',
      }),
    )

    expect(view).toMatchObject({
      id: 'tx-1',
      type: 'recharge',
      typeLabel: '充值',
      typeTone: 'success',
      direction: 'credit',
      amountCents: 10_000,
      amountLabel: '+¥100',
      balanceAfterCents: 1_010_000,
      balanceAfterLabel: '¥10,100',
      description: '线下充值',
      referenceType: 'manual',
      referenceId: '5',
      createdAtLabel: expect.any(String),
    })
  })

  it('falls back to the type default direction when the wire direction is unknown', () => {
    const view = toWalletTransactionView(
      buildWalletTransactionDto({
        type: 'order_payment',
        direction: '',
        amount_cents: 50_000,
      }),
    )

    expect(view.direction).toBe('debit')
    expect(view.amountLabel).toBe('-¥500')
  })

  it('keeps unknown transaction types renderable', () => {
    const view = toWalletTransactionView(
      buildWalletTransactionDto({ type: 'mystery_bonus', direction: '' }),
    )

    expect(view.type).toBe('unknown')
    expect(view.typeLabel).toBe('mystery_bonus')
    expect(view.typeTone).toBe('default')
    expect(view.direction).toBe('credit')
    expect(view.amountLabel).toBe('+¥500')
  })

  it('maps the wallet summary totals', () => {
    const summary = toWalletSummaryView(buildWalletSummaryDto())

    expect(summary).toMatchObject({
      balanceCents: 1_000_000,
      balanceLabel: '¥10,000',
      usageTotalLabel: '¥2,000',
      rechargeTotalLabel: '¥5,000',
      redeemTotalLabel: '¥1,000',
      incomeTotalLabel: '¥3,000',
      rechargeEnabled: false,
      rechargeNote: '在线充值暂未开放，可联系客服线下充值。',
      supportContact: '客服微信：stellera-support',
    })
  })

  it('maps a transaction list and falls back to the page length for total', () => {
    const model = toWalletTransactionListModel(
      buildWalletTransactionListDto(
        [buildWalletTransactionDto({ id: 1 }), buildWalletTransactionDto({ id: 2 })],
        { total: 0, page_size: 20 },
      ),
    )

    expect(model.transactions).toHaveLength(2)
    expect(model.total).toBe(2)
    expect(model.page).toBe(1)
    expect(model.pageSize).toBe(20)
  })

  it('maps the redeem result amount and updated balance', () => {
    const result = toRedeemResultView(buildRedeemResultDto())

    expect(result).toMatchObject({
      amountCents: 10_000,
      amountLabel: '¥100',
      balanceCents: 1_010_000,
      balanceLabel: '¥10,100',
    })
    expect(result.transaction.typeLabel).toBe('兑换')
    expect(result.transaction.amountLabel).toBe('+¥100')
  })
})
