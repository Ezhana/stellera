import { z } from 'zod'

/**
 * Wire schemas for the profile / certification application API.
 *
 * The only place in the frontend that knows backend field names (`real_name`, `contact_phone`,
 * `work_years`, …). Enum-like fields parse as plain strings so unknown values degrade in the mapper.
 */

const idDtoSchema = z.union([z.number(), z.string()])

export const profilePartyDtoSchema = z.object({
  id: idDtoSchema,
  display_name: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  certifications: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
})

export const cooperationRecordDtoSchema = z.object({
  order_id: idDtoSchema,
  code: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  title: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  price_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  completed_at: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  role: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  counterpart: profilePartyDtoSchema.nullish().transform((value) => value ?? null),
})

export const cooperationDtoSchema = z.object({
  completed_count: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  partner_count: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  total_amount_cents: z
    .number()
    .nullish()
    .transform((value) => value ?? 0),
  records: z
    .array(cooperationRecordDtoSchema)
    .nullish()
    .transform((value) => value ?? []),
})

export const userProfileDtoSchema = z.object({
  id: idDtoSchema,
  username: z.string(),
  nickname: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  email: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  real_name: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  bio: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  skills: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  city: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  contact_phone: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  contact_wechat: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  roles: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
  certifications: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
  created_at: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  cooperation: cooperationDtoSchema,
})

export const publicProfileDtoSchema = z.object({
  id: idDtoSchema,
  nickname: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  bio: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  skills: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  city: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  certifications: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
  member_since: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  cooperation: cooperationDtoSchema,
})

export const certificationApplicationDtoSchema = z.object({
  id: idDtoSchema,
  type: z.string(),
  status: z.string(),
  real_name: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  id_number: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  contact_phone: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  company_name: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  credit_code: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  contact_name: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  skills: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  work_years: z
    .number()
    .nullish()
    .transform((value) => value ?? null),
  project_experience: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  description: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
  review_note: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  reviewer: profilePartyDtoSchema.nullish().transform((value) => value ?? null),
  reviewed_at: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  created_at: z
    .string()
    .nullish()
    .transform((value) => value ?? ''),
})

export const certificationApplicationListDtoSchema = z.object({
  items: z
    .array(certificationApplicationDtoSchema)
    .nullish()
    .transform((value) => value ?? []),
})

export type ProfilePartyDto = z.infer<typeof profilePartyDtoSchema>
export type CooperationRecordDto = z.infer<typeof cooperationRecordDtoSchema>
export type CooperationDto = z.infer<typeof cooperationDtoSchema>
export type UserProfileDto = z.infer<typeof userProfileDtoSchema>
export type PublicProfileDto = z.infer<typeof publicProfileDtoSchema>
export type CertificationApplicationDto = z.infer<typeof certificationApplicationDtoSchema>
export type CertificationApplicationListDto = z.infer<typeof certificationApplicationListDtoSchema>
