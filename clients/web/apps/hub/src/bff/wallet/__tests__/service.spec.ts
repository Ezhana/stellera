import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/http'

import type { TokenProvider } from '../../token-provider'
import type { WalletGateway } from '../gateway'
import { WalletBff } from '../service'
import {
  buildRedeemResultDto,
  buildWalletSummaryDto,
  buildWalletTransactionDto,
  buildWalletTransactionListDto,
} from './fixtures'

function createGateway(): WalletGateway {
  return {
    getSummary: vi.fn(async () => buildWalletSummaryDto()),
    listTransactions: vi.fn(async () => buildWalletTransactionListDto()),
    redeem: vi.fn(async () => buildRedeemResultDto()),
  }
}

describe('WalletBff', () => {
  let gateway: WalletGateway
  let tokenProvider: TokenProvider
  let bff: WalletBff

  beforeEach(() => {
    gateway = createGateway()
    tokenProvider = { accessToken: vi.fn(() => 'token-1') }
    bff = new WalletBff(gateway, tokenProvider)
  })

  it('maps the summary with the current token', async () => {
    const summary = await bff.getSummary()

    expect(gateway.getSummary).toHaveBeenCalledWith('token-1')
    expect(summary.balanceLabel).toBe('¥10,000')
    expect(summary.rechargeEnabled).toBe(false)
  })

  it('maps a filtered transaction page', async () => {
    const model = await bff.listTransactions({ type: 'recharge', page: 2, pageSize: 20 })

    expect(gateway.listTransactions).toHaveBeenCalledWith('token-1', {
      type: 'recharge',
      page: 2,
      pageSize: 20,
    })
    expect(model.transactions[0]?.typeLabel).toBe('消费')
  })

  it('loads the whole page model in one call', async () => {
    vi.mocked(gateway.listTransactions).mockImplementation(async (_token, filter) => {
      if (filter?.type === 'recharge') {
        return buildWalletTransactionListDto([
          buildWalletTransactionDto({ id: 9, type: 'recharge', direction: 'credit' }),
        ])
      }
      return buildWalletTransactionListDto()
    })

    const page = await bff.loadPage()

    expect(gateway.getSummary).toHaveBeenCalledTimes(1)
    expect(gateway.listTransactions).toHaveBeenCalledWith('token-1', { pageSize: 50 })
    expect(gateway.listTransactions).toHaveBeenCalledWith('token-1', {
      type: 'recharge',
      pageSize: 20,
    })
    expect(page.summary.balanceLabel).toBe('¥10,000')
    expect(page.transactions.transactions).toHaveLength(1)
    expect(page.rechargeRecords).toHaveLength(1)
    expect(page.rechargeRecords[0]?.typeLabel).toBe('充值')
  })

  it('redeems a code and maps the credited amount', async () => {
    const result = await bff.redeem('RDM-AAAA-BBBB-CCCC')

    expect(gateway.redeem).toHaveBeenCalledWith('token-1', 'RDM-AAAA-BBBB-CCCC')
    expect(result.amountLabel).toBe('¥100')
    expect(result.balanceLabel).toBe('¥10,100')
  })

  it('fails with session-expired and never touches the gateway without a token', async () => {
    tokenProvider = { accessToken: vi.fn(() => null) }
    bff = new WalletBff(gateway, tokenProvider)

    await expect(bff.getSummary()).rejects.toMatchObject({
      name: 'BffError',
      code: 'session-expired',
    })
    await expect(bff.listTransactions()).rejects.toMatchObject({ code: 'session-expired' })
    await expect(bff.redeem('code')).rejects.toMatchObject({ code: 'session-expired' })
    expect(gateway.getSummary).not.toHaveBeenCalled()
    expect(gateway.listTransactions).not.toHaveBeenCalled()
    expect(gateway.redeem).not.toHaveBeenCalled()
  })

  it('normalizes transport errors into stable BffError codes', async () => {
    vi.mocked(gateway.redeem).mockRejectedValueOnce(
      new ApiError(409, '兑换码已被使用', '兑换码已被使用'),
    )
    vi.mocked(gateway.listTransactions).mockRejectedValueOnce(new ApiError(403, 'forbidden'))

    await expect(bff.redeem('code')).rejects.toMatchObject({
      name: 'BffError',
      code: 'conflict',
      message: '兑换码已被使用',
    })
    await expect(bff.listTransactions()).rejects.toMatchObject({
      name: 'BffError',
      code: 'forbidden',
    })
  })
})
