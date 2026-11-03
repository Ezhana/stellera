import { beforeEach, describe, expect, it, vi } from 'vitest'

import { request } from '@/lib/http'

import { BffError } from '../../errors'
import { HttpAdminGateway } from '../gateway'
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

vi.mock('@/lib/http', () => ({ request: vi.fn() }))

function queryOf(path: string): URLSearchParams {
  const index = path.indexOf('?')
  return new URLSearchParams(index === -1 ? '' : path.slice(index + 1))
}

describe('HttpAdminGateway', () => {
  const gateway = new HttpAdminGateway()
  const mockedRequest = vi.mocked(request)

  beforeEach(() => {
    mockedRequest.mockReset()
  })

  it('lists users with search, role and pagination params', async () => {
    mockedRequest.mockResolvedValueOnce(buildAdminUserListDto())

    await gateway.listUsers('token-1', { q: '  luna  ', role: 'admin', page: 2, pageSize: 20 })

    const path = mockedRequest.mock.calls[0]?.[0] ?? ''
    const query = queryOf(path)
    expect(path.startsWith('/admin/users?')).toBe(true)
    expect(query.get('q')).toBe('luna')
    expect(query.get('role')).toBe('admin')
    expect(query.get('page')).toBe('2')
    expect(query.get('page_size')).toBe('20')
    expect(mockedRequest.mock.calls[0]?.[1]).toEqual({ token: 'token-1' })
  })

  it('lists users with the default first page', async () => {
    mockedRequest.mockResolvedValueOnce(buildAdminUserListDto())

    await gateway.listUsers('token-1')

    expect(mockedRequest).toHaveBeenCalledWith('/admin/users?page=1&page_size=20', {
      token: 'token-1',
    })
  })

  it('loads roles and settings', async () => {
    mockedRequest
      .mockResolvedValueOnce(buildAdminRoleListDto())
      .mockResolvedValueOnce(buildAdminSettingsDto())

    await gateway.listRoles('token-1')
    await gateway.getSettings('token-1')

    expect(mockedRequest).toHaveBeenNthCalledWith(1, '/admin/roles', { token: 'token-1' })
    expect(mockedRequest).toHaveBeenNthCalledWith(2, '/admin/settings', { token: 'token-1' })
  })

  it('patches a user with the snake_case body (no role editing)', async () => {
    mockedRequest.mockResolvedValueOnce(buildAdminUserDto({ is_active: false }))

    await gateway.updateUser('token-1', '7', {
      nickname: 'Luna Chen',
      email: 'luna@example.com',
      isActive: false,
    })

    expect(mockedRequest).toHaveBeenCalledWith('/admin/users/7', {
      method: 'PATCH',
      token: 'token-1',
      body: {
        nickname: 'Luna Chen',
        email: 'luna@example.com',
        is_active: false,
      },
    })
  })

  it('only sends the provided patch fields', async () => {
    mockedRequest.mockResolvedValueOnce(buildAdminUserDto())

    await gateway.updateUser('token-1', '7', { isActive: true })

    expect(mockedRequest).toHaveBeenCalledWith('/admin/users/7', {
      method: 'PATCH',
      token: 'token-1',
      body: { is_active: true },
    })
  })

  it('posts a wallet adjustment with the snake_case body', async () => {
    mockedRequest.mockResolvedValueOnce(buildAdminUserDto({ balance_cents: 1_050_000 }))

    const user = await gateway.walletAdjustment('token-1', '7', {
      direction: 'credit',
      amountCents: 50_000,
      note: '活动奖励',
    })

    expect(mockedRequest).toHaveBeenCalledWith('/admin/users/7/wallet-adjustments', {
      method: 'POST',
      token: 'token-1',
      body: { direction: 'credit', amount_cents: 50_000, note: '活动奖励' },
    })
    expect(user.balance_cents).toBe(1_050_000)
  })

  it('lists redeem codes with status, keyword and pagination', async () => {
    mockedRequest.mockResolvedValueOnce(buildRedeemCodeListDto())

    await gateway.listRedeemCodes('token-1', {
      status: 'disabled',
      q: 'RDM',
      page: 2,
      pageSize: 20,
    })

    const query = queryOf(mockedRequest.mock.calls[0]?.[0] ?? '')
    expect(query.get('status')).toBe('disabled')
    expect(query.get('q')).toBe('RDM')
    expect(query.get('page')).toBe('2')
    expect(query.get('page_size')).toBe('20')
  })

  it('omits the status param for the "all" filter', async () => {
    mockedRequest.mockResolvedValueOnce(buildRedeemCodeListDto())

    await gateway.listRedeemCodes('token-1', { status: 'all' })

    const query = queryOf(mockedRequest.mock.calls[0]?.[0] ?? '')
    expect(query.has('status')).toBe(false)
  })

  it('creates a redeem-code batch with the snake_case body', async () => {
    mockedRequest.mockResolvedValueOnce(buildCreateRedeemCodeResponseDto())

    const batch = await gateway.createRedeemCodes('token-1', {
      amountCents: 10_000,
      quantity: 5,
      expiresInDays: 30,
      note: '活动',
    })

    expect(mockedRequest).toHaveBeenCalledWith('/admin/redeem-codes', {
      method: 'POST',
      token: 'token-1',
      body: { amount_cents: 10_000, quantity: 5, expires_in_days: 30, note: '活动' },
    })
    expect(batch.batch_no).toBe('B-20261101-01')
  })

  it('patches a redeem-code status', async () => {
    mockedRequest.mockResolvedValueOnce(buildRedeemCodeDto({ status: 'disabled' }))

    await gateway.updateRedeemCode('token-1', '3', 'disabled')

    expect(mockedRequest).toHaveBeenCalledWith('/admin/redeem-codes/3', {
      method: 'PATCH',
      token: 'token-1',
      body: { status: 'disabled' },
    })
  })

  it('lists certification applications with status/type/keyword pagination', async () => {
    mockedRequest.mockResolvedValueOnce(buildAdminCertificationApplicationListDto())

    await gateway.listCertificationApplications('token-1', {
      status: 'pending',
      type: 'enterprise',
      q: ' 远山 ',
      page: 2,
      pageSize: 20,
    })

    const path = mockedRequest.mock.calls[0]?.[0] ?? ''
    const query = queryOf(path)
    expect(path.startsWith('/admin/certification-applications?')).toBe(true)
    expect(query.get('status')).toBe('pending')
    expect(query.get('type')).toBe('enterprise')
    expect(query.get('q')).toBe('远山')
    expect(query.get('page')).toBe('2')
    expect(query.get('page_size')).toBe('20')
  })

  it('omits the status/type filters for the "all" values', async () => {
    mockedRequest.mockResolvedValueOnce(buildAdminCertificationApplicationListDto())

    await gateway.listCertificationApplications('token-1', { status: 'all', type: 'all' })

    const query = queryOf(mockedRequest.mock.calls[0]?.[0] ?? '')
    expect(query.has('status')).toBe(false)
    expect(query.has('type')).toBe(false)
  })

  it('approves and rejects certification applications with an optional note', async () => {
    mockedRequest
      .mockResolvedValueOnce(
        buildAdminCertificationApplicationDto({ status: 'approved', review_note: '材料齐全' }),
      )
      .mockResolvedValueOnce(buildAdminCertificationApplicationDto({ status: 'rejected' }))

    await gateway.approveCertificationApplication('token-1', '11', '材料齐全')
    await gateway.rejectCertificationApplication('token-1', '11')

    expect(mockedRequest).toHaveBeenNthCalledWith(
      1,
      '/admin/certification-applications/11/approve',
      { method: 'POST', token: 'token-1', body: { note: '材料齐全' } },
    )
    expect(mockedRequest).toHaveBeenNthCalledWith(
      2,
      '/admin/certification-applications/11/reject',
      { method: 'POST', token: 'token-1', body: {} },
    )
  })

  it('patches settings with the key/value map', async () => {
    mockedRequest.mockResolvedValueOnce(buildAdminSettingsDto())

    await gateway.updateSettings('token-1', { platform_name: 'STELLERA HUB' })

    expect(mockedRequest).toHaveBeenCalledWith('/admin/settings', {
      method: 'PATCH',
      token: 'token-1',
      body: { values: { platform_name: 'STELLERA HUB' } },
    })
  })

  it('throws malformed-response when the payload does not match the schema', async () => {
    mockedRequest.mockResolvedValue({ items: 'nope' })

    await expect(gateway.listUsers('token-1')).rejects.toMatchObject({
      name: 'BffError',
      code: 'malformed-response',
    })
    await expect(gateway.listUsers('token-1')).rejects.toBeInstanceOf(BffError)
  })
})
