import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/http'

import type { TokenProvider } from '../../token-provider'
import type { AdminGateway } from '../gateway'
import { AdminBff } from '../service'
import {
  buildAdminCertificationApplicationDto,
  buildAdminCertificationApplicationListDto,
  buildAdminRoleListDto,
  buildAdminSettingsDto,
  buildAdminUserDto,
  buildAdminUserListDto,
  buildCreateRedeemCodeResponseDto,
  buildRedeemCodeDto,
  buildRedeemCodeListDto,
} from './fixtures'

function createGateway(): AdminGateway {
  return {
    listUsers: vi.fn(async () => buildAdminUserListDto()),
    listRoles: vi.fn(async () => buildAdminRoleListDto()),
    updateUser: vi.fn(async () => buildAdminUserDto()),
    walletAdjustment: vi.fn(async () => buildAdminUserDto({ balance_cents: 1_050_000 })),
    listRedeemCodes: vi.fn(async () => buildRedeemCodeListDto()),
    createRedeemCodes: vi.fn(async () => buildCreateRedeemCodeResponseDto()),
    updateRedeemCode: vi.fn(async () => buildRedeemCodeDto({ status: 'disabled' })),
    getSettings: vi.fn(async () => buildAdminSettingsDto()),
    updateSettings: vi.fn(async () => buildAdminSettingsDto()),
    listCertificationApplications: vi.fn(async () => buildAdminCertificationApplicationListDto()),
    approveCertificationApplication: vi.fn(async () =>
      buildAdminCertificationApplicationDto({ status: 'approved' }),
    ),
    rejectCertificationApplication: vi.fn(async () =>
      buildAdminCertificationApplicationDto({ status: 'rejected', review_note: '材料不完整' }),
    ),
  }
}

describe('AdminBff', () => {
  let gateway: AdminGateway
  let tokenProvider: TokenProvider
  let bff: AdminBff

  beforeEach(() => {
    gateway = createGateway()
    tokenProvider = { accessToken: vi.fn(() => 'token-1') }
    bff = new AdminBff(gateway, tokenProvider)
  })

  it('lists users with the filter and maps their roles', async () => {
    const model = await bff.listUsers({ q: 'luna', role: 'enterprise', page: 2, pageSize: 20 })

    expect(gateway.listUsers).toHaveBeenCalledWith('token-1', {
      q: 'luna',
      role: 'enterprise',
      page: 2,
      pageSize: 20,
    })
    expect(model.users[0]?.roles).toEqual([
      { key: 'realname', label: '实名认证', tone: 'info' },
      { key: 'enterprise', label: '企业', tone: 'accent' },
    ])
    expect(model.total).toBe(1)
  })

  it('lists role options labelled by the frontend', async () => {
    const roles = await bff.listRoles()

    expect(gateway.listRoles).toHaveBeenCalledWith('token-1')
    expect(roles).toEqual([{ key: 'admin', label: '管理员', tone: 'accent' }])
  })

  it('updates a user nickname, email and status', async () => {
    await bff.updateUser('7', { isActive: false })
    await bff.updateUser('7', {
      nickname: 'Luna Chen',
      email: 'luna@example.com',
    })

    expect(gateway.updateUser).toHaveBeenNthCalledWith(1, 'token-1', '7', { isActive: false })
    expect(gateway.updateUser).toHaveBeenNthCalledWith(2, 'token-1', '7', {
      nickname: 'Luna Chen',
      email: 'luna@example.com',
    })
  })

  it('adjusts a user balance and maps the refreshed view', async () => {
    const user = await bff.walletAdjustment('7', {
      direction: 'debit',
      amountCents: 20_000,
      note: '扣减测试',
    })

    expect(gateway.walletAdjustment).toHaveBeenCalledWith('token-1', '7', {
      direction: 'debit',
      amountCents: 20_000,
      note: '扣减测试',
    })
    expect(user.balanceLabel).toBe('¥10,500')
  })

  it('lists redeem codes with the filter', async () => {
    const model = await bff.listRedeemCodes({ status: 'active', q: 'RDM', page: 1, pageSize: 20 })

    expect(gateway.listRedeemCodes).toHaveBeenCalledWith('token-1', {
      status: 'active',
      q: 'RDM',
      page: 1,
      pageSize: 20,
    })
    expect(model.codes[0]?.statusLabel).toBe('可用')
  })

  it('creates a redeem-code batch and maps the batch number', async () => {
    const batch = await bff.createRedeemCodes({
      amountCents: 10_000,
      quantity: 5,
      expiresInDays: 30,
      note: '活动',
    })

    expect(gateway.createRedeemCodes).toHaveBeenCalledWith('token-1', {
      amountCents: 10_000,
      quantity: 5,
      expiresInDays: 30,
      note: '活动',
    })
    expect(batch.batchNo).toBe('B-20261101-01')
    expect(batch.codes).toHaveLength(1)
  })

  it('toggles a redeem-code status', async () => {
    const code = await bff.updateRedeemCodeStatus('3', 'disabled')

    expect(gateway.updateRedeemCode).toHaveBeenCalledWith('token-1', '3', 'disabled')
    expect(code.status).toBe('disabled')
    expect(code.statusLabel).toBe('已停用')
  })

  it('loads and saves settings', async () => {
    const loaded = await bff.getSettings()
    const saved = await bff.updateSettings({ platform_name: 'STELLERA HUB' })

    expect(gateway.getSettings).toHaveBeenCalledWith('token-1')
    expect(gateway.updateSettings).toHaveBeenCalledWith('token-1', {
      platform_name: 'STELLERA HUB',
    })
    expect(loaded.settings.map((setting) => setting.key)).toEqual([
      'platform_name',
      'support_contact',
      'wallet_recharge_note',
    ])
    expect(saved.settings).toHaveLength(3)
  })

  it('lists certification applications with the filter', async () => {
    const model = await bff.listCertificationApplications({
      status: 'pending',
      type: 'engineer',
      q: '阿远',
      page: 1,
      pageSize: 20,
    })

    expect(gateway.listCertificationApplications).toHaveBeenCalledWith('token-1', {
      status: 'pending',
      type: 'engineer',
      q: '阿远',
      page: 1,
      pageSize: 20,
    })
    expect(model.applications[0]?.statusLabel).toBe('待审核')
    expect(model.applications[0]?.applicant?.displayName).toBe('会员（演示）')
  })

  it('approves and rejects certification applications', async () => {
    const approved = await bff.approveCertificationApplication('11', '材料齐全')
    const rejected = await bff.rejectCertificationApplication('11')

    expect(gateway.approveCertificationApplication).toHaveBeenCalledWith(
      'token-1',
      '11',
      '材料齐全',
    )
    expect(approved.statusLabel).toBe('已通过')
    expect(gateway.rejectCertificationApplication).toHaveBeenCalledWith('token-1', '11', undefined)
    expect(rejected.statusLabel).toBe('已驳回')
    expect(rejected.reviewNote).toBe('材料不完整')
  })

  it('fails with session-expired and never touches the gateway without a token', async () => {
    tokenProvider = { accessToken: vi.fn(() => null) }
    bff = new AdminBff(gateway, tokenProvider)

    await expect(bff.listUsers()).rejects.toMatchObject({
      name: 'BffError',
      code: 'session-expired',
    })
    await expect(bff.getSettings()).rejects.toMatchObject({ code: 'session-expired' })
    await expect(
      bff.walletAdjustment('7', { direction: 'credit', amountCents: 100, note: 'x' }),
    ).rejects.toMatchObject({ code: 'session-expired' })
    expect(gateway.listUsers).not.toHaveBeenCalled()
    expect(gateway.getSettings).not.toHaveBeenCalled()
    expect(gateway.walletAdjustment).not.toHaveBeenCalled()
  })

  it('normalizes forbidden and conflict transport errors', async () => {
    vi.mocked(gateway.listUsers).mockRejectedValueOnce(new ApiError(403, 'forbidden'))
    vi.mocked(gateway.updateUser).mockRejectedValueOnce(
      new ApiError(409, '不能停用自己', '不能停用自己'),
    )

    await expect(bff.listUsers()).rejects.toMatchObject({
      name: 'BffError',
      code: 'forbidden',
    })
    await expect(bff.updateUser('7', { isActive: false })).rejects.toMatchObject({
      name: 'BffError',
      code: 'conflict',
      message: '不能停用自己',
    })
  })
})
