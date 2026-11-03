import { z } from 'zod'

/** Wire schemas: the only place in the frontend that knows backend field names. */
export const permissionDtoSchema = z.object({
  object: z.string().min(1),
  action: z.string().min(1),
})

export const userDtoSchema = z.object({
  id: z.union([z.string(), z.number()]),
  username: z.string().min(1),
  nickname: z
    .string()
    .nullish()
    .transform((value) => value ?? null),
  email: z.string().nullable().optional(),
  full_name: z.string().nullable().optional(),
  certifications: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
  is_active: z.boolean().optional(),
  roles: z
    .array(z.string())
    .nullish()
    .transform((value) => value ?? []),
  permissions: z
    .array(permissionDtoSchema)
    .nullish()
    .transform((value) => value ?? []),
})

export const tokenPairDtoSchema = z.object({
  access_token: z.string().min(1),
  refresh_token: z.string().min(1),
})

export const loginResponseDtoSchema = tokenPairDtoSchema.extend({
  user: userDtoSchema,
})

export type PermissionDto = z.infer<typeof permissionDtoSchema>
export type UserDto = z.infer<typeof userDtoSchema>
export type TokenPairDto = z.infer<typeof tokenPairDtoSchema>
export type LoginResponseDto = z.infer<typeof loginResponseDtoSchema>
