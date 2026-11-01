import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/http'

import type { OrderGateway } from '../gateway'
import type { OrderRealtimeGateway, OrderRealtimeHandlers } from '../realtime'
import { OrdersBff, type OrderTokenProvider } from '../service'
import { buildOrderDetailDto, buildOrderDto, buildOrderListDto, buildWorkLogDto } from './fixtures'

function createGateway(): OrderGateway {
  return {
    listOrders: vi.fn(async () => buildOrderListDto()),
    listMyOrders: vi.fn(async () =>
      buildOrderListDto([buildOrderDto({ id: 5, status: 'in_progress' })]),
    ),
    getOrder: vi.fn(async () => buildOrderDetailDto()),
    createOrder: vi.fn(async () => buildOrderDto({ id: 8 })),
    claimOrder: vi.fn(async () => buildOrderDto({ id: 9, status: 'in_progress' })),
    addWorkLog: vi.fn(async () => buildWorkLogDto()),
    completeOrder: vi.fn(async () => buildOrderDto({ id: 9, status: 'completed' })),
  }
}

function createRealtime(): OrderRealtimeGateway {
  return {
    connect: vi.fn(() => ({ close: vi.fn() })),
  }
}

describe('OrdersBff', () => {
  let gateway: OrderGateway
  let realtime: OrderRealtimeGateway
  let tokenProvider: OrderTokenProvider
  let bff: OrdersBff

  beforeEach(() => {
    gateway = createGateway()
    realtime = createRealtime()
    tokenProvider = { accessToken: vi.fn(() => 'token-1') }
    bff = new OrdersBff(gateway, realtime, tokenProvider)
  })

  it('builds a list page model with mapped orders, stats and a fetch timestamp', async () => {
    const model = await bff.listOrders({ status: 'open' })

    expect(gateway.listOrders).toHaveBeenCalledWith('token-1', { status: 'open' })
    expect(model.orders).toHaveLength(1)
    expect(model.orders[0]?.statusLabel).toBe('待接单')
    expect(model.total).toBe(1)
    expect(model.stats).toMatchObject({ total: 1, openCount: 1, escrowHeldLabel: '¥86,000' })
    expect(model.fetchedAt).toEqual(expect.any(String))
    expect(Number.isNaN(Date.parse(model.fetchedAt))).toBe(false)
  })

  it('lists my orders', async () => {
    const model = await bff.listMyOrders({ status: 'in_progress' })

    expect(gateway.listMyOrders).toHaveBeenCalledWith('token-1', { status: 'in_progress' })
    expect(model.stats.inProgressCount).toBe(1)
  })

  it('maps an order detail with its logs', async () => {
    const detail = await bff.getOrder('42')

    expect(gateway.getOrder).toHaveBeenCalledWith('token-1', '42')
    expect(detail.logs).toHaveLength(1)
    expect(detail.logs[0]?.authorName).toBe('工程师阿远')
  })

  it('passes create input through and maps the created order', async () => {
    const input = {
      title: '医疗影像数据标注',
      industry: '医疗健康',
      description: '完成 500 例标注。',
      deliveryDays: 7,
      priceCents: 8_600_000,
    }

    const order = await bff.createOrder(input)

    expect(gateway.createOrder).toHaveBeenCalledWith('token-1', input)
    expect(order.id).toBe('8')
    expect(order.priceLabel).toBe('¥86,000')
  })

  it('claims, logs and completes an order', async () => {
    const claimed = await bff.claimOrder('9')
    const log = await bff.addWorkLog('9', { content: '完成首批标注', workedHours: 6 })
    const completed = await bff.completeOrder('9')

    expect(gateway.claimOrder).toHaveBeenCalledWith('token-1', '9')
    expect(claimed.status).toBe('in_progress')
    expect(gateway.addWorkLog).toHaveBeenCalledWith('token-1', '9', {
      content: '完成首批标注',
      workedHours: 6,
    })
    expect(log.workedHours).toBe(6)
    expect(gateway.completeOrder).toHaveBeenCalledWith('token-1', '9')
    expect(completed.statusLabel).toBe('已完成')
  })

  it('connects the realtime feed with the current token and handlers', () => {
    const handlers: OrderRealtimeHandlers = {
      onEvent: vi.fn(),
      onStateChange: vi.fn(),
    }

    const connection = bff.connectRealtime(handlers)

    expect(realtime.connect).toHaveBeenCalledWith('token-1', handlers)
    expect(connection.close).toEqual(expect.any(Function))
  })

  it('fails with session-expired and never touches the gateway without a token', async () => {
    tokenProvider = { accessToken: vi.fn(() => null) }
    bff = new OrdersBff(gateway, realtime, tokenProvider)

    await expect(bff.listOrders()).rejects.toMatchObject({
      name: 'BffError',
      code: 'session-expired',
    })
    expect(gateway.listOrders).not.toHaveBeenCalled()
    expect(() => bff.connectRealtime({ onEvent: vi.fn(), onStateChange: vi.fn() })).toThrowError(
      expect.objectContaining({ code: 'session-expired' }),
    )
    expect(realtime.connect).not.toHaveBeenCalled()
  })

  it('normalizes transport errors into stable BffError codes', async () => {
    vi.mocked(gateway.listOrders).mockRejectedValueOnce(new ApiError(403, 'forbidden'))
    vi.mocked(gateway.createOrder).mockRejectedValueOnce(new ApiError(422, 'invalid input'))

    await expect(bff.listOrders()).rejects.toMatchObject({ name: 'BffError', code: 'forbidden' })
    await expect(
      bff.createOrder({
        title: 't',
        industry: '其他',
        description: 'd',
        deliveryDays: 1,
        priceCents: 100,
      }),
    ).rejects.toMatchObject({ name: 'BffError', code: 'invalid-input' })
  })
})
