import type {
  AdminCertificationApplicationListModel,
  AdminCertificationApplicationView,
  AdminRedeemCodeBatch,
  AdminRedeemCodeListModel,
  AdminRedeemCodeView,
  AdminSettingsModel,
  AdminSettingView,
  AdminUserListModel,
  AdminUserView,
} from '@/models'

import type {
  AdminCertificationApplicationDto,
  AdminCertificationApplicationListDto,
  AdminRedeemCodeDto,
  AdminRedeemCodeListDto,
  AdminRoleDto,
  AdminRoleListDto,
  AdminSettingDto,
  AdminSettingsDto,
  AdminUserDto,
  AdminUserListDto,
  CreateRedeemCodeResponseDto,
} from '../dto'
import { buildCertificationApplicationDto } from '../../profile/__tests__/fixtures'
import {
  toAdminCertificationApplicationView,
  toAdminRedeemCodeView,
  toAdminSettingsModel,
  toAdminUserView,
} from '../mapper'

/** Deterministic DTO/view fixtures shared by the admin BFF and page tests. */
export function buildAdminUserDto(overrides: Partial<AdminUserDto> = {}): AdminUserDto {
  return {
    id: 7,
    username: 'luna',
    nickname: 'Luna Chen',
    email: 'luna@example.com',
    full_name: 'Luna Chen',
    is_active: true,
    roles: ['realname', 'enterprise'],
    certifications: ['realname', 'enterprise'],
    balance_cents: 1_000_000,
    created_at: '2026-10-01T02:30:00.000Z',
    ...overrides,
  }
}

export function buildAdminUserView(overrides: Partial<AdminUserView> = {}): AdminUserView {
  return { ...toAdminUserView(buildAdminUserDto()), ...overrides }
}

export function buildAdminUserListDto(
  items: AdminUserDto[] = [buildAdminUserDto()],
  overrides: Partial<AdminUserListDto> = {},
): AdminUserListDto {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    ...overrides,
  }
}

export function buildAdminCertificationApplicationDto(
  overrides: Partial<AdminCertificationApplicationDto> = {},
): AdminCertificationApplicationDto {
  return {
    ...buildCertificationApplicationDto(),
    user: {
      id: 6,
      username: 'member',
      nickname: '会员（演示）',
      email: 'member@example.com',
      roles: ['member', 'realname'],
      certifications: ['realname'],
    },
    ...overrides,
  }
}

export function buildAdminCertificationApplicationView(
  overrides: Partial<AdminCertificationApplicationView> = {},
): AdminCertificationApplicationView {
  return {
    ...toAdminCertificationApplicationView(buildAdminCertificationApplicationDto()),
    ...overrides,
  }
}

export function buildAdminCertificationApplicationListDto(
  items: AdminCertificationApplicationDto[] = [buildAdminCertificationApplicationDto()],
  overrides: Partial<AdminCertificationApplicationListDto> = {},
): AdminCertificationApplicationListDto {
  return { items, total: items.length, page: 1, page_size: 20, ...overrides }
}

export function buildAdminCertificationApplicationListModel(
  applications: AdminCertificationApplicationView[] = [buildAdminCertificationApplicationView()],
  overrides: Partial<AdminCertificationApplicationListModel> = {},
): AdminCertificationApplicationListModel {
  return { applications, total: applications.length, page: 1, pageSize: 20, ...overrides }
}

export function buildAdminRoleDto(overrides: Partial<AdminRoleDto> = {}): AdminRoleDto {
  return { name: 'admin', description: '超级管理员', ...overrides }
}

export function buildAdminRoleListDto(
  items: AdminRoleDto[] = [buildAdminRoleDto()],
): AdminRoleListDto {
  return { items }
}

export function buildRedeemCodeDto(
  overrides: Partial<AdminRedeemCodeDto> = {},
): AdminRedeemCodeDto {
  return {
    id: 3,
    code: 'RDM-AAAA-BBBB-CCCC',
    amount_cents: 10_000,
    status: 'active',
    batch_no: 'B-20261101-01',
    note: '双十一活动',
    is_expired: false,
    used_by: null,
    used_at: null,
    expires_at: '2026-12-01T00:00:00.000Z',
    created_at: '2026-11-01T00:00:00.000Z',
    ...overrides,
  }
}

export function buildRedeemCodeView(
  overrides: Partial<AdminRedeemCodeView> = {},
): AdminRedeemCodeView {
  return { ...toAdminRedeemCodeView(buildRedeemCodeDto()), ...overrides }
}

export function buildRedeemCodeListDto(
  items: AdminRedeemCodeDto[] = [buildRedeemCodeDto()],
  overrides: Partial<AdminRedeemCodeListDto> = {},
): AdminRedeemCodeListDto {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    ...overrides,
  }
}

export function buildCreateRedeemCodeResponseDto(
  items: AdminRedeemCodeDto[] = [buildRedeemCodeDto()],
  overrides: Partial<CreateRedeemCodeResponseDto> = {},
): CreateRedeemCodeResponseDto {
  return { batch_no: 'B-20261101-01', items, ...overrides }
}

export function buildAdminSettingDto(overrides: Partial<AdminSettingDto> = {}): AdminSettingDto {
  return {
    key: 'platform_name',
    value: 'STELLERA',
    updated_at: '2026-11-01T00:00:00.000Z',
    ...overrides,
  }
}

export function buildAdminSettingsDto(
  items: AdminSettingDto[] = [
    buildAdminSettingDto(),
    buildAdminSettingDto({
      key: 'support_contact',
      value: '客服微信：stellera-support',
    }),
    buildAdminSettingDto({
      key: 'wallet_recharge_note',
      value: '在线充值暂未开放。',
    }),
  ],
): AdminSettingsDto {
  return { items }
}

export function buildAdminSettingView(overrides: Partial<AdminSettingView> = {}): AdminSettingView {
  return { ...toAdminSettingsModel(buildAdminSettingsDto()).settings[0]!, ...overrides }
}

export function buildAdminUserListModel(
  users: AdminUserView[] = [buildAdminUserView()],
  overrides: Partial<AdminUserListModel> = {},
): AdminUserListModel {
  return { users, total: users.length, page: 1, pageSize: 20, ...overrides }
}

export function buildRedeemCodeListModel(
  codes: AdminRedeemCodeView[] = [buildRedeemCodeView()],
  overrides: Partial<AdminRedeemCodeListModel> = {},
): AdminRedeemCodeListModel {
  return { codes, total: codes.length, page: 1, pageSize: 20, ...overrides }
}

export function buildRedeemCodeBatch(
  codes: AdminRedeemCodeView[] = [buildRedeemCodeView()],
  batchNo = 'B-20261101-01',
): AdminRedeemCodeBatch {
  return { batchNo, codes }
}

export function buildAdminSettingsModel(
  settings: AdminSettingView[] = toAdminSettingsModel(buildAdminSettingsDto()).settings,
): AdminSettingsModel {
  return { settings }
}
