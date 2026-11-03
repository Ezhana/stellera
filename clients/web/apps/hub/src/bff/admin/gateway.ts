import type { ZodType } from 'zod'

import type { AdminRedeemCodeStatus } from '@/models'
import { request } from '@/lib/http'

import { BffError } from '../errors'
import {
  adminRedeemCodeDtoSchema,
  adminRedeemCodeListDtoSchema,
  adminRoleListDtoSchema,
  adminSettingsDtoSchema,
  adminUserDtoSchema,
  adminUserListDtoSchema,
  createRedeemCodeResponseDtoSchema,
  type AdminRedeemCodeDto,
  type AdminRedeemCodeListDto,
  type AdminRoleListDto,
  type AdminSettingsDto,
  type AdminUserDto,
  type AdminUserListDto,
  type CreateRedeemCodeResponseDto,
} from './dto'
import type {
  AdminRedeemCodeFilter,
  AdminUserFilter,
  CreateRedeemCodeInput,
  UpdateAdminUserInput,
} from './types'

const DEFAULT_PAGE_SIZE = 20

function parseDto<T>(schema: ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value)
  if (!result.success) {
    throw new BffError('malformed-response', '服务返回的管理数据格式异常。', {
      originalError: result.error,
    })
  }
  return result.data
}

function encodeId(id: string): string {
  return encodeURIComponent(id)
}

/**
 * Port for the admin backend.
 *
 * Implemented today by `HttpAdminGateway` (direct `/api/v1/admin/*` calls). A future server-side BFF
 * can implement the same interface without touching the service or the pages.
 */
export interface AdminGateway {
  listUsers(token: string, filter?: AdminUserFilter): Promise<AdminUserListDto>
  listRoles(token: string): Promise<AdminRoleListDto>
  updateUser(token: string, id: string, input: UpdateAdminUserInput): Promise<AdminUserDto>
  listRedeemCodes(token: string, filter?: AdminRedeemCodeFilter): Promise<AdminRedeemCodeListDto>
  createRedeemCodes(
    token: string,
    input: CreateRedeemCodeInput,
  ): Promise<CreateRedeemCodeResponseDto>
  updateRedeemCode(
    token: string,
    id: string,
    status: Extract<AdminRedeemCodeStatus, 'active' | 'disabled'>,
  ): Promise<AdminRedeemCodeDto>
  getSettings(token: string): Promise<AdminSettingsDto>
  updateSettings(token: string, values: Record<string, string>): Promise<AdminSettingsDto>
}

export class HttpAdminGateway implements AdminGateway {
  async listUsers(token: string, filter?: AdminUserFilter): Promise<AdminUserListDto> {
    const query = new URLSearchParams()
    const keyword = filter?.q?.trim()
    if (keyword) query.set('q', keyword)
    if (filter?.role) query.set('role', filter.role)
    query.set('page', String(filter?.page ?? 1))
    query.set('page_size', String(filter?.pageSize ?? DEFAULT_PAGE_SIZE))

    const raw = await request<unknown>(`/admin/users?${query.toString()}`, { token })
    return parseDto(adminUserListDtoSchema, raw)
  }

  async listRoles(token: string): Promise<AdminRoleListDto> {
    const raw = await request<unknown>('/admin/roles', { token })
    return parseDto(adminRoleListDtoSchema, raw)
  }

  async updateUser(token: string, id: string, input: UpdateAdminUserInput): Promise<AdminUserDto> {
    const body: Record<string, unknown> = {}
    if (input.isActive !== undefined) body.is_active = input.isActive
    if (input.roles !== undefined) body.roles = input.roles

    const raw = await request<unknown>(`/admin/users/${encodeId(id)}`, {
      method: 'PATCH',
      token,
      body,
    })
    return parseDto(adminUserDtoSchema, raw)
  }

  async listRedeemCodes(
    token: string,
    filter?: AdminRedeemCodeFilter,
  ): Promise<AdminRedeemCodeListDto> {
    const query = new URLSearchParams()
    if (filter?.status && filter.status !== 'all') query.set('status', filter.status)
    const keyword = filter?.q?.trim()
    if (keyword) query.set('q', keyword)
    query.set('page', String(filter?.page ?? 1))
    query.set('page_size', String(filter?.pageSize ?? DEFAULT_PAGE_SIZE))

    const raw = await request<unknown>(`/admin/redeem-codes?${query.toString()}`, { token })
    return parseDto(adminRedeemCodeListDtoSchema, raw)
  }

  async createRedeemCodes(
    token: string,
    input: CreateRedeemCodeInput,
  ): Promise<CreateRedeemCodeResponseDto> {
    const raw = await request<unknown>('/admin/redeem-codes', {
      method: 'POST',
      token,
      body: {
        amount_cents: input.amountCents,
        quantity: input.quantity,
        expires_in_days: input.expiresInDays,
        note: input.note,
      },
    })
    return parseDto(createRedeemCodeResponseDtoSchema, raw)
  }

  async updateRedeemCode(
    token: string,
    id: string,
    status: 'active' | 'disabled',
  ): Promise<AdminRedeemCodeDto> {
    const raw = await request<unknown>(`/admin/redeem-codes/${encodeId(id)}`, {
      method: 'PATCH',
      token,
      body: { status },
    })
    return parseDto(adminRedeemCodeDtoSchema, raw)
  }

  async getSettings(token: string): Promise<AdminSettingsDto> {
    const raw = await request<unknown>('/admin/settings', { token })
    return parseDto(adminSettingsDtoSchema, raw)
  }

  async updateSettings(token: string, values: Record<string, string>): Promise<AdminSettingsDto> {
    const raw = await request<unknown>('/admin/settings', {
      method: 'PATCH',
      token,
      body: { values },
    })
    return parseDto(adminSettingsDtoSchema, raw)
  }
}
