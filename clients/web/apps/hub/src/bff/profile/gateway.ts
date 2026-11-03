import type { ZodType } from 'zod'

import { request } from '@/lib/http'

import { BffError } from '../errors'
import {
  certificationApplicationDtoSchema,
  certificationApplicationListDtoSchema,
  publicProfileDtoSchema,
  userProfileDtoSchema,
  type CertificationApplicationDto,
  type CertificationApplicationListDto,
  type PublicProfileDto,
  type UserProfileDto,
} from './dto'
import type { CertificationApplicationInput, UpdateMyProfileInput } from './types'

function parseDto<T>(schema: ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value)
  if (!result.success) {
    throw new BffError('malformed-response', '服务返回的个人资料数据格式异常。', {
      originalError: result.error,
    })
  }
  return result.data
}

function encodeId(id: string): string {
  return encodeURIComponent(id)
}

/**
 * Port for the profile backend.
 *
 * Implemented today by `HttpProfileGateway`; a future server-side BFF can implement the same
 * interface without touching the service or the pages.
 */
export interface ProfileGateway {
  getMyProfile(token: string): Promise<UserProfileDto>
  updateMyProfile(token: string, input: UpdateMyProfileInput): Promise<UserProfileDto>
  getPublicProfile(token: string, userId: string): Promise<PublicProfileDto>
  listMyCertificationApplications(token: string): Promise<CertificationApplicationListDto>
  applyCertification(
    token: string,
    input: CertificationApplicationInput,
  ): Promise<CertificationApplicationDto>
}

export class HttpProfileGateway implements ProfileGateway {
  async getMyProfile(token: string): Promise<UserProfileDto> {
    const raw = await request<unknown>('/profile', { token })
    return parseDto(userProfileDtoSchema, raw)
  }

  async updateMyProfile(token: string, input: UpdateMyProfileInput): Promise<UserProfileDto> {
    const body: Record<string, unknown> = {}
    if (input.nickname !== undefined) body.nickname = input.nickname
    if (input.email !== undefined) body.email = input.email
    if (input.bio !== undefined) body.bio = input.bio
    if (input.skills !== undefined) body.skills = input.skills
    if (input.city !== undefined) body.city = input.city
    if (input.contactPhone !== undefined) body.contact_phone = input.contactPhone
    if (input.contactWechat !== undefined) body.contact_wechat = input.contactWechat

    const raw = await request<unknown>('/profile', {
      method: 'PATCH',
      token,
      body,
    })
    return parseDto(userProfileDtoSchema, raw)
  }

  async getPublicProfile(token: string, userId: string): Promise<PublicProfileDto> {
    const raw = await request<unknown>(`/profiles/${encodeId(userId)}`, { token })
    return parseDto(publicProfileDtoSchema, raw)
  }

  async listMyCertificationApplications(token: string): Promise<CertificationApplicationListDto> {
    const raw = await request<unknown>('/profile/certification-applications', { token })
    return parseDto(certificationApplicationListDtoSchema, raw)
  }

  async applyCertification(
    token: string,
    input: CertificationApplicationInput,
  ): Promise<CertificationApplicationDto> {
    const raw = await request<unknown>('/profile/certification-applications', {
      method: 'POST',
      token,
      body: {
        type: input.type,
        real_name: input.realName,
        id_number: input.idNumber,
        contact_phone: input.contactPhone,
        company_name: input.companyName,
        credit_code: input.creditCode,
        contact_name: input.contactName,
        skills: input.skills,
        work_years: input.workYears ?? undefined,
        project_experience: input.projectExperience,
        description: input.description,
      },
    })
    return parseDto(certificationApplicationDtoSchema, raw)
  }
}
