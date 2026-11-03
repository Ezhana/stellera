import { z } from 'zod'

/**
 * Wire schemas for the wallet API.
 *
 * This is the only place in the frontend that knows backend field names (`balance_cents`,
 * `reference_type`, …). Enum-like fields parse as plain strings so an unknown transaction type or
 * direction degrades in the mapper instead of breaking the page.
 */

const idDtoSchema = z.union([z.number(), z.string()])

const nullableIdDto = idDtoSchema
  .nullish()
  .transform((value) => (value === null || value === undefined ? null : String(value)))

export const walletSummaryDtoSchema = z.object({
  balance_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  usage_total_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  recharge_total_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  redeem_total_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  income_total_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  recharge_enabled: z
    .boolean()
    .nullish()
    .transform((value) => value ?? false),
  recharge_note: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  support_contact: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
})

export const walletTransactionDtoSchema = z.object({
  id: idDtoSchema,
  type: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  direction: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  amount_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  balance_after_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  description: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  reference_type: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  reference_id: nullableIdDto,
  created_at: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
})

export const walletTransactionListDtoSchema = z.object({
  items: z
    .array(walletTransactionDtoSchema)
    .nullish()
    .transform((value) => value ?? []),
  total: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  page: z
    .number()
    .nullish()
    .transform((value) => value ?? 1),
  page_size: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
})

export const redeemResultDtoSchema = z.object({
  amount_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  balance_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  transaction: walletTransactionDtoSchema,
})

export type WalletSummaryDto = z.infer<typeof walletSummaryDtoSchema>
export type WalletTransactionDto = z.infer<typeof walletTransactionDtoSchema>
export type WalletTransactionListDto = z.infer<typeof walletTransactionListDtoSchema>
export type RedeemResultDto = z.infer<typeof redeemResultDtoSchema>
