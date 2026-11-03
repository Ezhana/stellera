import { beforeEach, describe, expect, it, vi } from 'vitest'

import { request } from '@/lib/http'

import { BffError } from '../../errors'
import { HttpWalletGateway } from '../gateway'
import {
  buildRedeemResultDto,
  buildWalletSummaryDto,
  buildWalletTransactionListDto,
} from './fixtures'

vi.mock('@/lib/http', () => ({ request: vi.fn() }))

function queryOf(path: string): URLSearchParams {
  const index = path.indexOf('?')
  return new URLSearchParams(index === -1 ? '' : path.slice(index + 1))
}

describe('HttpWalletGateway', () => {
  const gateway = new HttpWalletGateway()
  const mockedRequest = vi.mocked(request)

  beforeEach(() => {
    mockedRequest.mockReset()
  })

  it('loads the summary from /wallet', async () => {
    mockedRequest.mockResolvedValueOnce(buildWalletSummaryDto())

    const summary = await gateway.getSummary('token-1')

    expect(mockedRequest).toHaveBeenCalledWith('/wallet', { token: 'token-1' })
    expect(summary.balance_cents).toBe(1_000_000)
  })

  it('lists transactions with the default first page', async () => {
    mockedRequest.mockResolvedValueOnce(buildWalletTransactionListDto())

    await gateway.listTransactions('token-1')

    expect(mockedRequest).toHaveBeenCalledWith('/wallet/transactions?page=1&page_size=20', {
      token: 'token-1',
    })
  })

  it('encodes the type filter and pagination', async () => {
    mockedRequest.mockResolvedValueOnce(buildWalletTransactionListDto())

    await gateway.listTransactions('token-1', { type: 'recharge', page: 3, pageSize: 50 })

    const query = queryOf(mockedRequest.mock.calls[0]?.[0] ?? '')
    expect(query.get('type')).toBe('recharge')
    expect(query.get('page')).toBe('3')
    expect(query.get('page_size')).toBe('50')
  })

  it('omits the type param for the "all" filter', async () => {
    mockedRequest.mockResolvedValueOnce(buildWalletTransactionListDto())

    await gateway.listTransactions('token-1', { type: 'all' })

    const query = queryOf(mockedRequest.mock.calls[0]?.[0] ?? '')
    expect(query.has('type')).toBe(false)
  })

  it('redeems a code with the camelCase body', async () => {
    mockedRequest.mockResolvedValueOnce(buildRedeemResultDto())

    const result = await gateway.redeem('token-1', 'RDM-AAAA-BBBB-CCCC')

    expect(mockedRequest).toHaveBeenCalledWith('/wallet/redeem', {
      method: 'POST',
      token: 'token-1',
      body: { code: 'RDM-AAAA-BBBB-CCCC' },
    })
    expect(result.amount_cents).toBe(10_000)
  })

  it('throws malformed-response when the payload does not match the schema', async () => {
    mockedRequest.mockResolvedValue({ balance_cents: 'nope' })

    await expect(gateway.getSummary('token-1')).rejects.toMatchObject({
      name: 'BffError',
      code: 'malformed-response',
    })
    await expect(gateway.getSummary('token-1')).rejects.toBeInstanceOf(BffError)
  })
})
