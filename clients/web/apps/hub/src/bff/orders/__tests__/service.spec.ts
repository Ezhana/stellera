import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/http'

import type { OrderGateway } from '../gateway'
import type { OrderRealtimeGateway, OrderRealtimeHandlers } from '../realtime'
import { OrdersBff, type OrderTokenProvider } from '../service'
import {
  buildApplicationDto,
  buildApplicationListDto,
  buildOrderDetailDto,
  buildOrderDto,
  buildOrderListDto,
  buildWorkLogDto,
} from './fixtures'

function createGateway(): OrderGateway {
  return {
    listOrders: vi.fn(async () => buildOrderListDto()),
    listMyOrders: vi.fn(async () =>
      buildOrderListDto([buildOrderDto({ id: 5, status: 'in_progress' })]),
    ),
    listAssignedOrders: vi.fn(async () =>
      buildOrderListDto([buildOrderDto({ id: 6, status: 'in_progress' })]),
    ),
    getOrder: vi.fn(async () => buildOrderDetailDto()),
    createOrder: vi.fn(async () => buildOrderDto({ id: 8 })),
    cancelOrder: vi.fn(async () => buildOrderDto({ id: 8, status: 'cancelled' })),
    addWorkLog: vi.fn(async () => buildWorkLogDto()),
    applyForOrder: vi.fn(async () => buildApplicationDto()),
    listMyApplications: vi.fn(async () => buildApplicationListDto()),
    listReceivedApplications: vi.fn(async () =>
      buildApplicationListDto([buildApplicationDto({ id: 2, type: 'delivery' })]),
    ),
    approveApplication: vi.fn(async () => buildApplicationDto({ status: 'approved' })),
    rejectApplication: vi.fn(async () => buildApplicationDto({ status: 'rejected' })),
    withdrawApplication: vi.fn(async () => buildApplicationDto({ status: 'withdrawn' })),
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

  it('lists my orders and my assigned orders', async () => {
    const mine = await bff.listMyOrders({ status: 'in_progress' })
    const assigned = await bff.listAssignedOrders({ status: 'in_progress' })

    expect(gateway.listMyOrders).toHaveBeenCalledWith('token-1', { status: 'in_progress' })
    expect(mine.stats.inProgressCount).toBe(1)
    expect(gateway.listAssignedOrders).toHaveBeenCalledWith('token-1', { status: 'in_progress' })
    expect(assigned.orders[0]?.id).toBe('6')
  })

  it('maps an order detail with its logs', async () => {
    const detail = await bff.getOrder('42')

    expect(gateway.getOrder).toHaveBeenCalledWith('token-1', '42')
    expect(detail.logs).toHaveLength(1)
    expect(detail.logs[0]?.authorName).toBe('工程师阿远')
    expect(detail.applications).toHaveLength(1)
    expect(detail.applications[0]?.applicantName).toBe('会员（演示）')
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

  it('cancels an open order and maps the cancelled status', async () => {
    const order = await bff.cancelOrder('8')

    expect(gateway.cancelOrder).toHaveBeenCalledWith('token-1', '8')
    expect(order.status).toBe('cancelled')
    expect(order.statusLabel).toBe('已取消')
  })

  it('adds a work log for an in-progress order', async () => {
    const log = await bff.addWorkLog('9', { content: '完成首批标注', workedHours: 6 })

    expect(gateway.addWorkLog).toHaveBeenCalledWith('token-1', '9', {
      content: '完成首批标注',
      workedHours: 6,
    })
    expect(log.workedHours).toBe(6)
  })

  it('applies for an order and normalizes blank messages', async () => {
    const application = await bff.applyForOrder('9', 'accept', '  有行业经验  ')

    expect(gateway.applyForOrder).toHaveBeenCalledWith('token-1', '9', {
      type: 'accept',
      message: '有行业经验',
    })
    expect(application.typeLabel).toBe('接单申请')

    await bff.applyForOrder('9', 'delivery', '   ')

    expect(gateway.applyForOrder).toHaveBeenLastCalledWith('token-1', '9', {
      type: 'delivery',
      message: null,
    })
  })

  it('lists my and received applications with the filter', async () => {
    const mine = await bff.listMyApplications({ type: 'accept', status: 'pending', pageSize: 100 })
    const received = await bff.listReceivedApplications({ status: 'pending', pageSize: 100 })

    const filter = { type: 'accept', status: 'pending', pageSize: 100 }
    expect(gateway.listMyApplications).toHaveBeenCalledWith('token-1', filter)
    expect(mine.total).toBe(1)
    expect(gateway.listReceivedApplications).toHaveBeenCalledWith('token-1', {
      status: 'pending',
      pageSize: 100,
    })
    expect(received.applications[0]?.typeLabel).toBe('交付申请')
  })

  it('approves, rejects and withdraws applications', async () => {
    const approved = await bff.approveApplication('3', '请按说明交付')
    const rejected = await bff.rejectApplication('3')
    const withdrawn = await bff.withdrawApplication('3')

    expect(gateway.approveApplication).toHaveBeenCalledWith('token-1', '3', '请按说明交付')
    expect(approved.statusLabel).toBe('已通过')
    expect(gateway.rejectApplication).toHaveBeenCalledWith('token-1', '3', undefined)
    expect(rejected.statusLabel).toBe('已驳回')
    expect(gateway.withdrawApplication).toHaveBeenCalledWith('token-1', '3')
    expect(withdrawn.statusLabel).toBe('已撤回')
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
    await expect(bff.applyForOrder('9', 'accept')).rejects.toMatchObject({
      code: 'session-expired',
    })
    expect(gateway.listOrders).not.toHaveBeenCalled()
    expect(gateway.applyForOrder).not.toHaveBeenCalled()
    expect(() => bff.connectRealtime({ onEvent: vi.fn(), onStateChange: vi.fn() })).toThrowError(
      expect.objectContaining({ code: 'session-expired' }),
    )
    expect(realtime.connect).not.toHaveBeenCalled()
  })

  it('normalizes transport errors into stable BffError codes', async () => {
    vi.mocked(gateway.listOrders).mockRejectedValueOnce(new ApiError(403, 'forbidden'))
    vi.mocked(gateway.createOrder).mockRejectedValueOnce(new ApiError(422, 'invalid input'))
    vi.mocked(gateway.applyForOrder).mockRejectedValueOnce(
      new ApiError(409, '已有待审批申请', '已有待审批申请'),
    )

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
    await expect(bff.applyForOrder('9', 'accept')).rejects.toMatchObject({
      name: 'BffError',
      code: 'conflict',
      message: '已有待审批申请',
    })
  })
})
