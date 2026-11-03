import type {
  AdminRedeemCodeBatch,
  AdminRedeemCodeListModel,
  AdminRedeemCodeStatus,
  AdminRedeemCodeView,
  AdminRoleOption,
  AdminSettingView,
  AdminSettingsModel,
  AdminUserListModel,
  AdminUserView,
  BadgeTone,
} from '@/models'
import { formatCents, formatDateTimeLabel } from '@/lib/money'

import { deriveInitials, describeRole } from '../auth/mapper'
import type {
  AdminRedeemCodeDto,
  AdminRedeemCodeListDto,
  AdminRoleDto,
  AdminSettingsDto,
  AdminSettingDto,
  AdminUserDto,
  AdminUserListDto,
  CreateRedeemCodeResponseDto,
} from './dto'

interface SettingMeta {
  label: string
  description: string
  multiline: boolean
  order: number
}

/** Labels and help copy are frontend-owned; the backend may only know the three whitelisted keys. */
const SETTING_META: Readonly<Record<string, SettingMeta>> = {
  platform_name: {
    label: '平台名称',
    description: '展示在控制台与对外页面上的平台名称。',
    multiline: false,
    order: 0,
  },
  support_contact: {
    label: '客服联系方式',
    description: '钱包页与错误提示中展示的客服联系方式。',
    multiline: false,
    order: 1,
  },
  wallet_recharge_note: {
    label: '充值说明',
    description: '钱包页充值档位下方的说明文案，支持多行。',
    multiline: true,
    order: 2,
  },
}

interface StatusPresentation {
  status: AdminRedeemCodeStatus
  label: string
  tone: BadgeTone
}

const REDEEM_STATUS_META: ReadonlyMap<string, Omit<StatusPresentation, 'status'>> = new Map([
  ['active', { label: '可用', tone: 'success' }],
  ['used', { label: '已使用', tone: 'default' }],
  ['disabled', { label: '已停用', tone: 'warning' }],
])

/** Known status labels/tones; expired active codes read as 「已过期」, unknown keys stay raw. */
export function formatRedeemCodeStatus(status: string, isExpired: boolean): StatusPresentation {
  const meta = REDEEM_STATUS_META.get(status)
  if (!meta) {
    return { status: 'disabled', label: status || '未知状态', tone: 'default' }
  }
  if (status === 'active' && isExpired) {
    return { status: 'active', label: '已过期', tone: 'warning' }
  }
  return { status: status as AdminRedeemCodeStatus, label: meta.label, tone: meta.tone }
}

function normalizeOptional(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

export function toAdminUserView(dto: AdminUserDto): AdminUserView {
  const username = dto.username
  const displayName = normalizeOptional(dto.full_name) ?? username
  const roleKeys = [...new Set(dto.roles)]
  const isActive = dto.is_active !== false

  return {
    id: String(dto.id),
    username,
    displayName,
    initials: deriveInitials(displayName),
    email: normalizeOptional(dto.email),
    isActive,
    statusLabel: isActive ? '已启用' : '已停用',
    roleKeys,
    roles: roleKeys.map(describeRole),
    balanceCents: dto.balance_cents,
    balanceLabel: formatCents(dto.balance_cents),
    createdAtLabel: formatDateTimeLabel(dto.created_at),
  }
}

export function toAdminUserListModel(dto: AdminUserListDto): AdminUserListModel {
  const users = dto.items.map(toAdminUserView)
  return {
    users,
    total: dto.total > 0 ? dto.total : users.length,
    page: dto.page,
    pageSize: dto.page_size,
  }
}

export function toAdminRoleOption(dto: AdminRoleDto): AdminRoleOption {
  const role = describeRole(dto.name)
  return { key: role.key, label: role.label, tone: role.tone }
}

export function toAdminRedeemCodeView(dto: AdminRedeemCodeDto): AdminRedeemCodeView {
  const status = formatRedeemCodeStatus(dto.status, dto.is_expired)
  const usedByName = normalizeOptional(dto.used_by?.display_name)

  return {
    id: String(dto.id),
    code: dto.code,
    amountCents: dto.amount_cents,
    amountLabel: formatCents(dto.amount_cents),
    status: status.status,
    statusLabel: status.label,
    statusTone: status.tone,
    isExpired: dto.is_expired,
    batchNo: dto.batch_no,
    note: dto.note,
    usedByName,
    usedAtLabel: dto.used_at ? formatDateTimeLabel(dto.used_at) : null,
    expiresAtLabel: dto.expires_at ? formatDateTimeLabel(dto.expires_at) : null,
    createdAtLabel: formatDateTimeLabel(dto.created_at),
  }
}

export function toAdminRedeemCodeListModel(dto: AdminRedeemCodeListDto): AdminRedeemCodeListModel {
  const codes = dto.items.map(toAdminRedeemCodeView)
  return {
    codes,
    total: dto.total > 0 ? dto.total : codes.length,
    page: dto.page,
    pageSize: dto.page_size,
  }
}

export function toAdminRedeemCodeBatch(dto: CreateRedeemCodeResponseDto): AdminRedeemCodeBatch {
  return { batchNo: dto.batch_no, codes: dto.items.map(toAdminRedeemCodeView) }
}

export function toAdminSettingView(dto: AdminSettingDto): AdminSettingView {
  const meta = SETTING_META[dto.key]
  return {
    key: dto.key,
    label: meta?.label ?? dto.key,
    description: meta?.description ?? '',
    value: dto.value,
    multiline: meta?.multiline ?? false,
    updatedAtLabel: dto.updated_at ? formatDateTimeLabel(dto.updated_at) : null,
  }
}

export function toAdminSettingsModel(dto: AdminSettingsDto): AdminSettingsModel {
  const settings = dto.items
    .map(toAdminSettingView)
    .sort((left, right) => settingOrder(left.key) - settingOrder(right.key))
  return { settings }
}

function settingOrder(key: string): number {
  return SETTING_META[key]?.order ?? 99
}
