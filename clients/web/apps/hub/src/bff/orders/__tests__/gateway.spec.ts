import { beforeEach, describe, expect, it, vi } from 'vitest'

import { request } from '@/lib/http'

import { BffError } from '../../errors'
import { HttpOrderGateway } from '../gateway'
import { buildOrderDetailDto, buildOrderDto, buildOrderListDto, buildWorkLogDto } from './fixtures'

vi.mock('@/lib/http', () => ({ request: vi.fn() }))

function queryOf(path: string): URLSearchParams {
  const index = path.indexOf('?')
  return new URLSearchParams(index === -1 ? '' : path.slice(index + 1))
}

describe('HttpOrderGateway', () => {
  const gateway = new HttpOrderGateway()
  const mockedRequest = vi.mocked(request)

  beforeEach(() => {
    mockedRequest.mockReset()
  })

  it('lists the hall with one full page of orders by default', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderListDto())

    const result = await gateway.listOrders('token-1')

    expect(mockedRequest).toHaveBeenCalledWith('/fde/orders?page=1&page_size=100', {
      token: 'token-1',
    })
    expect(result.items).toHaveLength(1)
    expect(result.total).toBe(1)
  })

  it('maps client filters into status/industry/q query params', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderListDto())

    await gateway.listOrders('token-1', {
      status: 'open',
      industry: ' 医疗健康 ',
      keyword: ' 数据 ',
    })

    const path = mockedRequest.mock.calls[0]?.[0] ?? ''
    expect(path.startsWith('/fde/orders?')).toBe(true)
    const query = queryOf(path)
    expect(query.get('status')).toBe('open')
    expect(query.get('industry')).toBe('医疗健康')
    expect(query.get('q')).toBe('数据')
    expect(query.get('page')).toBe('1')
    expect(query.get('page_size')).toBe('100')
  })

  it('omits the status param for the "all" filter and empty keyword', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderListDto())

    await gateway.listOrders('token-1', { status: 'all', keyword: '   ' })

    const query = queryOf(mockedRequest.mock.calls[0]?.[0] ?? '')
    expect(query.has('status')).toBe(false)
    expect(query.has('q')).toBe(false)
  })

  it('lists my orders with only the status filter', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderListDto())

    await gateway.listMyOrders('token-1', { status: 'in_progress', keyword: 'ignored' })

    expect(mockedRequest).toHaveBeenCalledWith('/fde/orders/mine?status=in_progress', {
      token: 'token-1',
    })
  })

  it('lists my orders without a query string when unfiltered', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderListDto())

    await gateway.listMyOrders('token-1', { status: 'all' })

    expect(mockedRequest).toHaveBeenCalledWith('/fde/orders/mine', { token: 'token-1' })
  })

  it('gets one order detail including logs', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderDetailDto())

    const result = await gateway.getOrder('token-1', '42')

    expect(mockedRequest).toHaveBeenCalledWith('/fde/orders/42', { token: 'token-1' })
    expect(result.logs).toHaveLength(1)
  })

  it('creates an order with the snake_case body', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderDto())

    await gateway.createOrder('token-1', {
      title: '医疗影像数据标注',
      industry: '医疗健康',
      description: '完成 500 例标注。',
      deliveryDays: 7,
      priceCents: 8_600_000,
    })

    expect(mockedRequest).toHaveBeenCalledWith('/fde/orders', {
      method: 'POST',
      token: 'token-1',
      body: {
        title: '医疗影像数据标注',
        industry: '医疗健康',
        description: '完成 500 例标注。',
        delivery_days: 7,
        price_cents: 8_600_000,
      },
    })
  })

  it('claims and completes orders through their action endpoints', async () => {
    mockedRequest
      .mockResolvedValueOnce(buildOrderDto())
      .mockResolvedValueOnce(buildOrderDto({ status: 'completed' }))

    await gateway.claimOrder('token-1', '5')
    await gateway.completeOrder('token-1', '5')

    expect(mockedRequest).toHaveBeenNthCalledWith(1, '/fde/orders/5/claim', {
      method: 'POST',
      token: 'token-1',
    })
    expect(mockedRequest).toHaveBeenNthCalledWith(2, '/fde/orders/5/complete', {
      method: 'POST',
      token: 'token-1',
    })
  })

  it('appends a work log with the snake_case body', async () => {
    mockedRequest.mockResolvedValueOnce(buildWorkLogDto())

    await gateway.addWorkLog('token-1', '5', { content: '完成首批标注', workedHours: 6 })

    expect(mockedRequest).toHaveBeenCalledWith('/fde/orders/5/logs', {
      method: 'POST',
      token: 'token-1',
      body: { content: '完成首批标注', worked_hours: 6 },
    })
  })

  it('throws malformed-response when the payload does not match the schema', async () => {
    mockedRequest.mockResolvedValue({ items: 'nope' })

    await expect(gateway.listOrders('token-1')).rejects.toMatchObject({
      name: 'BffError',
      code: 'malformed-response',
    })
    await expect(gateway.listOrders('token-1')).rejects.toBeInstanceOf(BffError)
  })
})
