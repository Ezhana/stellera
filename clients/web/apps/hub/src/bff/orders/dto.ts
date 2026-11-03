import { z } from 'zod'

/**
 * Wire schemas for the FDE order API.
 *
 * This is the only place in the frontend that knows backend field names (`price_cents`,
 * `escrow_status`, `review_note`, …). Everything above this layer consumes camelCase page models.
 *
 * Enum-like fields intentionally parse as `z.string()`: a new backend status must never make the
 * order hall crash. The mapper degrades unknown values to the raw key + a default tone.
 */

const idDtoSchema = z.union([z.number(), z.string()])

export const orderPartyDtoSchema = z.object({
  id: idDtoSchema,
  display_name: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  certification: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
})

export const orderDtoSchema = z.object({
  id: idDtoSchema,
  code: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  title: z.string(),
  industry: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  description: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  delivery_days: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  price_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  status: z.string(),
  escrow_status: z.string(),
  publisher: orderPartyDtoSchema,
  engineer: orderPartyDtoSchema.nullish().transform((value) => value ?? null),
  work_log_count: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  created_at: z.string(),
  updated_at: z.string(),
  claimed_at: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  completed_at: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
})

export const workLogDtoSchema = z.object({
  id: idDtoSchema,
  order_id: idDtoSchema,
  author: orderPartyDtoSchema,
  content: z.string(),
  worked_hours: z
    .number()
    .nullish()
    .transform((value) => value ?? null),
  created_at: z.string(),
})

export const orderListDtoSchema = z.object({
  items: z
    .array(orderDtoSchema)
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

export const orderDetailDtoSchema = orderDtoSchema.extend({
  logs: z
    .array(workLogDtoSchema)
    .nullish()
    .transform((value) => value ?? []),
})

export const applicationDtoSchema = z.object({
  id: idDtoSchema,
  order: orderDtoSchema,
  type: z.string(),
  status: z.string(),
  message: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  review_note: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  applicant: orderPartyDtoSchema,
  reviewer: orderPartyDtoSchema.nullish().transform((value) => value ?? null),
  reviewed_at: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  created_at: z.string(),
})

export const applicationListDtoSchema = z.object({
  items: z
    .array(applicationDtoSchema)
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

export type OrderPartyDto = z.infer<typeof orderPartyDtoSchema>
export type OrderDto = z.infer<typeof orderDtoSchema>
export type WorkLogDto = z.infer<typeof workLogDtoSchema>
export type OrderListDto = z.infer<typeof orderListDtoSchema>
export type OrderDetailDto = z.infer<typeof orderDetailDtoSchema>
export type ApplicationDto = z.infer<typeof applicationDtoSchema>
export type ApplicationListDto = z.infer<typeof applicationListDtoSchema>
