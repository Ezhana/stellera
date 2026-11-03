import { describe, expect, it } from 'vitest'

import {
  formatRedeemCodeStatus,
  toAdminRedeemCodeBatch,
  toAdminRedeemCodeListModel,
  toAdminRedeemCodeView,
  toAdminRoleOption,
  toAdminSettingsModel,
  toAdminUserListModel,
  toAdminUserView,
} from '../mapper'
import {
  buildAdminRoleDto,
  buildAdminSettingsDto,
  buildAdminSettingDto,
  buildAdminUserDto,
  buildAdminUserListDto,
  buildCreateRedeemCodeResponseDto,
  buildRedeemCodeDto,
  buildRedeemCodeListDto,
} from './fixtures'

describe('admin mapper users', () => {
  it('maps a full user row into the stable view', () => {
    const view = toAdminUserView(
      buildAdminUserDto({
        id: 'u-1',
        full_name: 'Luna Chen',
        roles: ['enterprise', 'engineer'],
        balance_cents: 1_234_500,
        is_active: true,
      }),
    )

    expect(view).toMatchObject({
      id: 'u-1',
      username: 'luna',
      displayName: 'Luna Chen',
      fullName: 'Luna Chen',
      initials: 'LC',
      email: 'luna@example.com',
      certification: 'enterprise',
      isActive: true,
      statusLabel: '已启用',
      roleKeys: ['enterprise', 'engineer'],
      balanceCents: 1_234_500,
      balanceLabel: '¥12,345',
      createdAtLabel: expect.any(String),
    })
    expect(view.roles).toEqual([
      { key: 'enterprise', label: '企业', tone: 'accent' },
      { key: 'engineer', label: '工程师', tone: 'success' },
    ])
  })

  it('degrades sparse and unknown data safely', () => {
    const view = toAdminUserView(
      buildAdminUserDto({
        username: 'ghost',
        full_name: '   ',
        email: null,
        is_active: false,
        roles: ['admin', 'mystery_role', 'admin'],
        certification: 'vip',
      }),
    )

    expect(view.displayName).toBe('ghost')
    expect(view.fullName).toBeNull()
    expect(view.initials).toBe('GH')
    expect(view.email).toBeNull()
    expect(view.certification).toBeNull()
    expect(view.statusLabel).toBe('已停用')
    expect(view.roleKeys).toEqual(['admin', 'mystery_role'])
    expect(view.roles[1]).toEqual({ key: 'mystery_role', label: 'mystery_role', tone: 'default' })
  })

  it('derives the certification from roles when the backend omits it', () => {
    const view = toAdminUserView(buildAdminUserDto({ roles: ['engineer'], certification: null }))

    expect(view.certification).toBe('engineer')
  })

  it('maps a user list and falls back to the loaded length for total', () => {
    const model = toAdminUserListModel(
      buildAdminUserListDto([buildAdminUserDto(), buildAdminUserDto({ id: 8 })], { total: 0 }),
    )

    expect(model.users).toHaveLength(2)
    expect(model.total).toBe(2)
    expect(model.page).toBe(1)
    expect(model.pageSize).toBe(20)
  })

  it('labels role options through the shared role metadata', () => {
    expect(toAdminRoleOption(buildAdminRoleDto())).toEqual({
      key: 'admin',
      label: '管理员',
      tone: 'accent',
    })
    expect(toAdminRoleOption(buildAdminRoleDto({ name: 'custom_role' }))).toEqual({
      key: 'custom_role',
      label: 'custom_role',
      tone: 'default',
    })
  })
})

describe('admin mapper redeem codes', () => {
  it('maps an available code', () => {
    const view = toAdminRedeemCodeView(buildRedeemCodeDto())

    expect(view).toMatchObject({
      id: '3',
      code: 'RDM-AAAA-BBBB-CCCC',
      amountCents: 10_000,
      amountLabel: '¥100',
      status: 'active',
      statusLabel: '可用',
      statusTone: 'success',
      isExpired: false,
      batchNo: 'B-20261101-01',
      note: '双十一活动',
      usedByName: null,
      usedAtLabel: null,
      expiresAtLabel: expect.any(String),
      createdAtLabel: expect.any(String),
    })
  })

  it('shows an expired active code as 已过期 while keeping its status', () => {
    expect(formatRedeemCodeStatus('active', true)).toEqual({
      status: 'active',
      label: '已过期',
      tone: 'warning',
    })
    expect(formatRedeemCodeStatus('used', true)).toEqual({
      status: 'used',
      label: '已使用',
      tone: 'default',
    })
    expect(formatRedeemCodeStatus('disabled', false)).toEqual({
      status: 'disabled',
      label: '已停用',
      tone: 'warning',
    })
    expect(formatRedeemCodeStatus('mystery', false)).toEqual({
      status: 'disabled',
      label: 'mystery',
      tone: 'default',
    })
  })

  it('maps the used-by party and timestamps', () => {
    const view = toAdminRedeemCodeView(
      buildRedeemCodeDto({
        status: 'used',
        used_by: { id: 7, display_name: 'Luna Chen' },
        used_at: '2026-11-02T03:00:00.000Z',
      }),
    )

    expect(view.statusLabel).toBe('已使用')
    expect(view.usedByName).toBe('Luna Chen')
    expect(view.usedAtLabel).toEqual(expect.any(String))
  })

  it('maps a code list and a generated batch', () => {
    const list = toAdminRedeemCodeListModel(buildRedeemCodeListDto())
    const batch = toAdminRedeemCodeBatch(buildCreateRedeemCodeResponseDto())

    expect(list.codes).toHaveLength(1)
    expect(list.total).toBe(1)
    expect(batch.batchNo).toBe('B-20261101-01')
    expect(batch.codes).toHaveLength(1)
  })
})

describe('admin mapper settings', () => {
  it('applies frontend labels, descriptions and multiline flags in whitelist order', () => {
    const model = toAdminSettingsModel(
      buildAdminSettingsDto([
        buildAdminSettingDto({ key: 'wallet_recharge_note', value: '线下充值说明' }),
        buildAdminSettingDto({ key: 'platform_name', value: 'STELLERA' }),
        buildAdminSettingDto({ key: 'support_contact', value: '客服微信' }),
      ]),
    )

    expect(model.settings.map((setting) => setting.key)).toEqual([
      'platform_name',
      'support_contact',
      'wallet_recharge_note',
    ])
    expect(model.settings[0]).toMatchObject({
      label: '平台名称',
      value: 'STELLERA',
      multiline: false,
      updatedAtLabel: expect.any(String),
    })
    expect(model.settings[2]).toMatchObject({
      label: '充值说明',
      multiline: true,
      description: expect.stringContaining('充值'),
    })
  })

  it('degrades unknown setting keys to the raw key', () => {
    const model = toAdminSettingsModel(buildAdminSettingsDto([buildAdminSettingDto({ key: 'x' })]))

    expect(model.settings[0]).toMatchObject({
      key: 'x',
      label: 'x',
      description: '',
      multiline: false,
    })
  })

  it('returns a null updated label when the backend omits the timestamp', () => {
    const model = toAdminSettingsModel(
      buildAdminSettingsDto([buildAdminSettingDto({ updated_at: null })]),
    )

    expect(model.settings[0]?.updatedAtLabel).toBeNull()
  })
})
