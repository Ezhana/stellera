import { z } from 'zod'

import { certificationApplicationDtoSchema } from '../profile/dto'

/**
 * Wire schemas for the admin API.
 *
 * This is the only place in the frontend that knows backend field names (`full_name`, `is_active`,
 * `amount_cents`, …). Enum-like fields parse as plain strings so unknown statuses degrade in the
 * mapper instead of breaking the console.
 */

const idDtoSchema = z.union([z.number(), z.string()])

export const adminUserDtoSchema = z.object({
  id: idDtoSchema,
  username: z.string(),
  nickname: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  email: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  full_name: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  is_active: z
    .boolean()
    .nullish()
    .transform((value) => value ?? true),
  roles: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
  certifications: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
  balance_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  created_at: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
})

export const adminUserListDtoSchema = z.object({
  items: z
    .array(adminUserDtoSchema)
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

const adminCertificationUserDtoSchema = z.object({
  id: idDtoSchema,
  username: z.string(),
  nickname: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  email: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  roles: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
  certifications: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
})

export const adminCertificationApplicationDtoSchema = certificationApplicationDtoSchema.extend({
  user: adminCertificationUserDtoSchema.nullish().transform((value) => value ?? null),
})

export const adminCertificationApplicationListDtoSchema = z.object({
  items: z
    .array(adminCertificationApplicationDtoSchema)
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

export const adminRoleDtoSchema = z.object({
  name: z.string(),
  description: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
})

export const adminRoleListDtoSchema = z.object({
  items: z
    .array(adminRoleDtoSchema)
    .nullish()
    .transform((value) => value ?? []),
})

export const redeemCodeUserDtoSchema = z.object({
  id: idDtoSchema,
  display_name: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
})

export const adminRedeemCodeDtoSchema = z.object({
  id: idDtoSchema,
  code: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  amount_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  status: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  batch_no: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  note: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  is_expired: z
    .boolean()
    .nullish()
    .transform((value) => value ?? false),
  used_by: redeemCodeUserDtoSchema.nullish().transform((value) => value ?? null),
  used_at: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  expires_at: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  created_at: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
})

export const adminRedeemCodeListDtoSchema = z.object({
  items: z
    .array(adminRedeemCodeDtoSchema)
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

export const createRedeemCodeResponseDtoSchema = z.object({
  batch_no: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  items: z
    .array(adminRedeemCodeDtoSchema)
    .nullish()
    .transform((value) => value ?? []),
})

export const adminSettingDtoSchema = z.object({
  key: z.string(),
  value: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  updated_at: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
})

export const adminSettingsDtoSchema = z.object({
  items: z
    .array(adminSettingDtoSchema)
    .nullish()
    .transform((value) => value ?? []),
})

export type AdminUserDto = z.infer<typeof adminUserDtoSchema>
export type AdminUserListDto = z.infer<typeof adminUserListDtoSchema>
export type AdminCertificationApplicationDto = z.infer<
  typeof adminCertificationApplicationDtoSchema
>
export type AdminCertificationApplicationListDto = z.infer<
  typeof adminCertificationApplicationListDtoSchema
>
export type AdminRoleDto = z.infer<typeof adminRoleDtoSchema>
export type AdminRoleListDto = z.infer<typeof adminRoleListDtoSchema>
export type AdminRedeemCodeDto = z.infer<typeof adminRedeemCodeDtoSchema>
export type AdminRedeemCodeListDto = z.infer<typeof adminRedeemCodeListDtoSchema>
export type CreateRedeemCodeResponseDto = z.infer<typeof createRedeemCodeResponseDtoSchema>
export type AdminSettingDto = z.infer<typeof adminSettingDtoSchema>
export type AdminSettingsDto = z.infer<typeof adminSettingsDtoSchema>
