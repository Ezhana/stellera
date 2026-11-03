import { beforeEach, describe, expect, it, vi } from 'vitest'

import { request } from '@/lib/http'

import { BffError } from '../../errors'
import { HttpOrderGateway } from '../gateway'
import {
  buildApplicationDto,
  buildApplicationListDto,
  buildOrderDetailDto,
  buildOrderDto,
  buildOrderListDto,
  buildWorkLogDto,
} from './fixtures'

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

  it('lists assigned orders through the dedicated endpoint', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderListDto())

    await gateway.listAssignedOrders('token-1', { status: 'in_progress' })

    const query = queryOf(mockedRequest.mock.calls[0]?.[0] ?? '')
    expect((mockedRequest.mock.calls[0]?.[0] ?? '').startsWith('/fde/orders/assigned?')).toBe(true)
    expect(query.get('status')).toBe('in_progress')
    expect(query.get('page')).toBe('1')
    expect(query.get('page_size')).toBe('100')
  })

  it('gets one order detail including logs', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderDetailDto())

    const result = await gateway.getOrder('token-1', '42')

    expect(mockedRequest).toHaveBeenCalledWith('/fde/orders/42', { token: 'token-1' })
    expect(result.logs).toHaveLength(1)
    expect(result.applications).toHaveLength(1)
    expect(result.applications[0]?.type).toBe('accept')
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

  it('cancels an order through its action endpoint', async () => {
    mockedRequest.mockResolvedValueOnce(buildOrderDto({ status: 'cancelled' }))

    await gateway.cancelOrder('token-1', '5')

    expect(mockedRequest).toHaveBeenCalledWith('/fde/orders/5/cancel', {
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

  it('applies for an order with type and optional message', async () => {
    mockedRequest.mockResolvedValueOnce(buildApplicationDto())

    const application = await gateway.applyForOrder('token-1', '5', {
      type: 'accept',
      message: '有相关行业经验',
    })

    expect(mockedRequest).toHaveBeenCalledWith('/fde/orders/5/applications', {
      method: 'POST',
      token: 'token-1',
      body: { type: 'accept', message: '有相关行业经验' },
    })
    expect(application.id).toBe(1)
  })

  it('lists my applications with type/status/page params', async () => {
    mockedRequest.mockResolvedValueOnce(buildApplicationListDto())

    await gateway.listMyApplications('token-1', {
      type: 'accept',
      status: 'pending',
      page: 2,
      pageSize: 50,
    })

    const path = mockedRequest.mock.calls[0]?.[0] ?? ''
    expect(path.startsWith('/fde/applications/mine?')).toBe(true)
    const query = queryOf(path)
    expect(query.get('type')).toBe('accept')
    expect(query.get('status')).toBe('pending')
    expect(query.get('page')).toBe('2')
    expect(query.get('page_size')).toBe('50')
  })

  it('lists received applications with default pagination', async () => {
    mockedRequest.mockResolvedValueOnce(buildApplicationListDto())

    await gateway.listReceivedApplications('token-1', { status: 'all' })

    const path = mockedRequest.mock.calls[0]?.[0] ?? ''
    expect(path.startsWith('/fde/applications/received?')).toBe(true)
    const query = queryOf(path)
    expect(query.has('type')).toBe(false)
    expect(query.has('status')).toBe(false)
    expect(query.get('page')).toBe('1')
    expect(query.get('page_size')).toBe('20')
  })

  it('approves, rejects and withdraws applications', async () => {
    mockedRequest
      .mockResolvedValueOnce(buildApplicationDto({ status: 'approved' }))
      .mockResolvedValueOnce(buildApplicationDto({ status: 'rejected' }))
      .mockResolvedValueOnce(buildApplicationDto({ status: 'withdrawn' }))

    await gateway.approveApplication('token-1', '3', '请按说明交付')
    await gateway.rejectApplication('token-1', '3')
    await gateway.withdrawApplication('token-1', '3')

    expect(mockedRequest).toHaveBeenNthCalledWith(1, '/fde/applications/3/approve', {
      method: 'POST',
      token: 'token-1',
      body: { note: '请按说明交付' },
    })
    expect(mockedRequest).toHaveBeenNthCalledWith(2, '/fde/applications/3/reject', {
      method: 'POST',
      token: 'token-1',
      body: {},
    })
    expect(mockedRequest).toHaveBeenNthCalledWith(3, '/fde/applications/3/withdraw', {
      method: 'POST',
      token: 'token-1',
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
