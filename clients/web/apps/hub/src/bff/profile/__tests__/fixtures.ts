import type {
  CertificationApplicationListModel,
  CertificationApplicationView,
  PublicProfileView,
  UserProfileView,
} from '@/models'

import type {
  CertificationApplicationDto,
  CertificationApplicationListDto,
  CooperationDto,
  CooperationRecordDto,
  ProfilePartyDto,
  PublicProfileDto,
  UserProfileDto,
} from '../dto'
import { toCertificationApplicationView, toPublicProfileView, toUserProfileView } from '../mapper'

/** Deterministic DTO/view fixtures shared by the profile BFF and page tests. */
export function buildProfilePartyDto(overrides: Partial<ProfilePartyDto> = {}): ProfilePartyDto {
  return {
    id: 5,
    display_name: '工程师阿远',
    certifications: ['realname', 'engineer'],
    ...overrides,
  }
}

export function buildCooperationRecordDto(
  overrides: Partial<CooperationRecordDto> = {},
): CooperationRecordDto {
  return {
    order_id: 42,
    code: 'FDE-20261101-0001',
    title: '医疗影像数据标注与质检',
    price_cents: 8_600_000,
    completed_at: '2026-11-03T06:20:00.000Z',
    role: 'publisher',
    counterpart: buildProfilePartyDto(),
    ...overrides,
  }
}

export function buildCooperationDto(overrides: Partial<CooperationDto> = {}): CooperationDto {
  return {
    completed_count: 2,
    partner_count: 1,
    total_amount_cents: 8_700_000,
    records: [buildCooperationRecordDto()],
    ...overrides,
  }
}

export function buildUserProfileDto(overrides: Partial<UserProfileDto> = {}): UserProfileDto {
  return {
    id: 2,
    username: 'member',
    nickname: '会员（演示）',
    email: 'member@example.com',
    real_name: '张三',
    bio: '专注医疗数据标注与质检。',
    skills: 'Python,数据标注',
    city: '上海',
    contact_phone: '13800000000',
    contact_wechat: 'stellera-member',
    roles: ['member', 'realname'],
    certifications: ['realname'],
    created_at: '2026-10-01T02:30:00.000Z',
    cooperation: buildCooperationDto(),
    ...overrides,
  }
}

export function buildUserProfileView(overrides: Partial<UserProfileView> = {}): UserProfileView {
  return { ...toUserProfileView(buildUserProfileDto()), ...overrides }
}

export function buildPublicProfileDto(overrides: Partial<PublicProfileDto> = {}): PublicProfileDto {
  return {
    id: 5,
    nickname: '工程师阿远',
    bio: '曾交付多个医疗影像项目。',
    skills: 'Python,数据标注',
    city: '杭州',
    certifications: ['realname', 'engineer'],
    member_since: '2026-09-01T02:30:00.000Z',
    cooperation: buildCooperationDto({
      records: [buildCooperationRecordDto({ role: 'engineer' })],
    }),
    ...overrides,
  }
}

export function buildPublicProfileView(
  overrides: Partial<PublicProfileView> = {},
): PublicProfileView {
  return { ...toPublicProfileView(buildPublicProfileDto()), ...overrides }
}

export function buildCertificationApplicationDto(
  overrides: Partial<CertificationApplicationDto> = {},
): CertificationApplicationDto {
  return {
    id: 11,
    type: 'realname',
    status: 'pending',
    real_name: '张三',
    id_number: '310101199001011234',
    contact_phone: '13800000000',
    company_name: '',
    credit_code: '',
    contact_name: '',
    skills: '',
    work_years: null,
    project_experience: '',
    description: '已实名认证，请审核。',
    review_note: null,
    reviewer: null,
    reviewed_at: null,
    created_at: '2026-11-02T06:20:00.000Z',
    ...overrides,
  }
}

export function buildCertificationApplicationView(
  overrides: Partial<CertificationApplicationView> = {},
): CertificationApplicationView {
  return { ...toCertificationApplicationView(buildCertificationApplicationDto()), ...overrides }
}

export function buildCertificationApplicationListDto(
  items: CertificationApplicationDto[] = [buildCertificationApplicationDto()],
): CertificationApplicationListDto {
  return { items }
}

export function buildCertificationApplicationListModel(
  applications: CertificationApplicationView[] = [buildCertificationApplicationView()],
): CertificationApplicationListModel {
  return { applications }
}
