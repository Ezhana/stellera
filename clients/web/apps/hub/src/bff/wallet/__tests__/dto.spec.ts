import { describe, expect, it } from 'vitest'

import {
  redeemResultDtoSchema,
  walletSummaryDtoSchema,
  walletTransactionDtoSchema,
  walletTransactionListDtoSchema,
} from '../dto'
import { buildRedeemResultDto, buildWalletTransactionDto } from './fixtures'

describe('wallet dto', () => {
  it('defaults missing summary fields instead of failing', () => {
    expect(walletSummaryDtoSchema.parse({})).toEqual({
      balance_cents: 0,
      usage_total_cents: 0,
      recharge_total_cents: 0,
      redeem_total_cents: 0,
      income_total_cents: 0,
      recharge_enabled: false,
      recharge_note: '',
      support_contact: '',
    })
  })

  it('keeps unknown transaction enums as raw strings for the mapper to degrade', () => {
    const parsed = walletTransactionDtoSchema.parse({
      ...buildWalletTransactionDto(),
      type: 'mystery_bonus',
      direction: 'sideways',
    })

    expect(parsed.type).toBe('mystery_bonus')
    expect(parsed.direction).toBe('sideways')
  })

  it('normalizes reference ids to strings and nullable references to null', () => {
    expect(
      walletTransactionDtoSchema.parse({ ...buildWalletTransactionDto(), reference_id: 12 })
        .reference_id,
    ).toBe('12')
    expect(
      walletTransactionDtoSchema.parse({ ...buildWalletTransactionDto(), reference_type: null })
        .reference_type,
    ).toBeNull()
  })

  it('defaults a missing transaction collection', () => {
    expect(walletTransactionListDtoSchema.parse({ items: null })).toEqual({
      items: [],
      total: 0,
      page: 1,
      page_size: 0,
    })
  })

  it('rejects rows without an id', () => {
    expect(() => walletTransactionDtoSchema.parse({ amount_cents: 100 })).toThrow()
  })

  it('parses a redeem result with its ledger row', () => {
    const parsed = redeemResultDtoSchema.parse(buildRedeemResultDto())

    expect(parsed.amount_cents).toBe(10_000)
    expect(parsed.balance_cents).toBe(1_010_000)
    expect(parsed.transaction.type).toBe('redeem')
  })
})
