import type {
  BadgeTone,
  CertificationApplicationListModel,
  CertificationApplicationStatus,
  CertificationApplicationType,
  CertificationApplicationView,
  CooperationStatsView,
  ProfilePartyView,
  PublicProfileView,
  UserProfileView,
} from '@/models'
import { CERTIFICATION_APPLICATION_STATUSES, CERTIFICATION_APPLICATION_TYPES } from '@/models'
import { formatCents, formatDateTimeLabel } from '@/lib/money'

import { describeRole } from '../auth/mapper'
import { normalizeCertifications } from '../certification'
import type {
  CertificationApplicationDto,
  CertificationApplicationListDto,
  CooperationDto,
  ProfilePartyDto,
  PublicProfileDto,
  UserProfileDto,
} from './dto'

/** Label + tone pair rendered by a chip; unknown backend values keep the raw key. */
export interface ApplicationPresentation {
  label: string
  tone: BadgeTone
}

const TYPE_META: ReadonlyMap<string, ApplicationPresentation> = new Map(
  CERTIFICATION_APPLICATION_TYPES.map((meta) => [meta.key, { label: meta.label, tone: meta.tone }]),
)

const STATUS_META: ReadonlyMap<string, ApplicationPresentation> = new Map(
  CERTIFICATION_APPLICATION_STATUSES.map((meta) => [
    meta.key,
    { label: meta.label, tone: meta.tone },
  ]),
)

export function formatApplicationType(type: string): ApplicationPresentation {
  return TYPE_META.get(type) ?? { label: type || '未知认证类型', tone: 'default' }
}

export function formatApplicationStatus(status: string): ApplicationPresentation {
  return STATUS_META.get(status) ?? { label: status || '未知审核状态', tone: 'default' }
}

/** Split the wire skill string into tag-sized tokens (round-trips through `joinSkills`). */
export function splitSkills(value: string): string[] {
  return value
    .split(/[,，、;；]/)
    .map((token) => token.trim())
    .filter(Boolean)
}

/** Join tag tokens back into the comma-separated wire format. */
export function joinSkills(skills: readonly string[]): string {
  return skills.join(',')
}

function normalizeOptional(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

export function toProfilePartyView(dto: ProfilePartyDto): ProfilePartyView {
  return {
    id: String(dto.id),
    displayName: dto.display_name,
    certifications: normalizeCertifications(dto.certifications),
  }
}

export function toCooperationStatsView(dto: CooperationDto): CooperationStatsView {
  return {
    completedCount: dto.completed_count,
    partnerCount: dto.partner_count,
    totalAmountCents: dto.total_amount_cents,
    totalAmountLabel: formatCents(dto.total_amount_cents),
    records: dto.records.map((record) => {
      const role = record.role === 'engineer' ? 'engineer' : 'publisher'
      return {
        orderId: String(record.order_id),
        code: record.code,
        title: record.title,
        priceCents: record.price_cents,
        priceLabel: formatCents(record.price_cents),
        completedAtLabel: record.completed_at ? formatDateTimeLabel(record.completed_at) : '—',
        role,
        roleLabel: role === 'engineer' ? '接单工程师' : '发布方',
        counterpart: record.counterpart ? toProfilePartyView(record.counterpart) : null,
      }
    }),
  }
}

export function toUserProfileView(dto: UserProfileDto): UserProfileView {
  const nickname = normalizeOptional(dto.nickname) ?? dto.username
  return {
    id: String(dto.id),
    username: dto.username,
    nickname,
    email: normalizeOptional(dto.email),
    realName: normalizeOptional(dto.real_name),
    bio: dto.bio,
    skills: splitSkills(dto.skills),
    city: dto.city,
    contactPhone: dto.contact_phone,
    contactWechat: dto.contact_wechat,
    roles: [...new Set(dto.roles)].map(describeRole),
    certifications: normalizeCertifications(dto.certifications),
    createdAtLabel: formatDateTimeLabel(dto.created_at),
    cooperation: toCooperationStatsView(dto.cooperation),
  }
}

export function toPublicProfileView(dto: PublicProfileDto): PublicProfileView {
  return {
    id: String(dto.id),
    nickname: dto.nickname,
    bio: dto.bio,
    skills: splitSkills(dto.skills),
    city: dto.city,
    certifications: normalizeCertifications(dto.certifications),
    memberSinceLabel: formatDateTimeLabel(dto.member_since),
    cooperation: toCooperationStatsView(dto.cooperation),
  }
}

export function toCertificationApplicationView(
  dto: CertificationApplicationDto,
): CertificationApplicationView {
  const type = formatApplicationType(dto.type)
  const status = formatApplicationStatus(dto.status)

  return {
    id: String(dto.id),
    type: dto.type as CertificationApplicationType,
    typeLabel: type.label,
    typeTone: type.tone,
    status: dto.status as CertificationApplicationStatus,
    statusLabel: status.label,
    statusTone: status.tone,
    realName: dto.real_name,
    idNumber: dto.id_number,
    contactPhone: dto.contact_phone,
    companyName: dto.company_name,
    creditCode: dto.credit_code,
    contactName: dto.contact_name,
    skills: dto.skills,
    workYears: dto.work_years,
    projectExperience: dto.project_experience,
    description: dto.description,
    reviewNote: dto.review_note,
    reviewer: dto.reviewer ? toProfilePartyView(dto.reviewer) : null,
    reviewedAtLabel: dto.reviewed_at ? formatDateTimeLabel(dto.reviewed_at) : null,
    createdAtLabel: formatDateTimeLabel(dto.created_at),
  }
}

export function toCertificationApplicationListModel(
  dto: CertificationApplicationListDto,
): CertificationApplicationListModel {
  return { applications: dto.items.map(toCertificationApplicationView) }
}
