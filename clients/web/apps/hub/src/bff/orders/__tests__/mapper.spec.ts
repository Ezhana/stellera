import { describe, expect, it } from 'vitest'

import {
  formatDateTimeLabel,
  formatDeliveryLabel,
  formatEscrow,
  formatPriceCents,
  formatStatus,
  summarizeOrders,
  toOrderDetailView,
  toOrderView,
  toWorkLogView,
  upsertOrder,
} from '../mapper'
import { buildOrderDetailDto, buildOrderDto, buildOrderView, buildWorkLogDto } from './fixtures'

describe('orders mapper formatting', () => {
  it('formats cents as grouped yuan with optional fen', () => {
    expect(formatPriceCents(0)).toBe('¥0')
    expect(formatPriceCents(8_600_000)).toBe('¥86,000')
    expect(formatPriceCents(12_345)).toBe('¥123.45')
    expect(formatPriceCents(100)).toBe('¥1')
    expect(formatPriceCents(-2_500)).toBe('-¥25')
    expect(formatPriceCents(Number.NaN)).toBe('¥0')
  })

  it('formats same-day and cross-day timestamps', () => {
    const now = new Date(2026, 10, 1, 15, 0)

    expect(formatDateTimeLabel(new Date(2026, 10, 1, 14, 20).toISOString(), now)).toBe('今天 14:20')
    expect(formatDateTimeLabel(new Date(2026, 9, 31, 9, 5).toISOString(), now)).toBe('10-31 09:05')
    expect(formatDateTimeLabel('not-a-date', now)).toBe('—')
  })

  it('formats delivery days', () => {
    expect(formatDeliveryLabel(7)).toBe('7 天')
    expect(formatDeliveryLabel(0)).toBe('0 天')
  })

  it('degrades unknown status and escrow values safely', () => {
    expect(formatStatus('open')).toEqual({ label: '待接单', tone: 'warning' })
    expect(formatStatus('in_progress')).toEqual({ label: '交付中', tone: 'info' })
    expect(formatStatus('completed')).toEqual({ label: '已完成', tone: 'success' })
    expect(formatStatus('cancelled')).toEqual({ label: '已取消', tone: 'default' })
    expect(formatStatus('archived')).toEqual({ label: 'archived', tone: 'default' })
    expect(formatStatus('')).toEqual({ label: '未知状态', tone: 'default' })

    expect(formatEscrow('held')).toEqual({ label: '资金托管中', tone: 'accent' })
    expect(formatEscrow('released')).toEqual({ label: '已结算', tone: 'success' })
    expect(formatEscrow('refunded')).toEqual({ label: '已退回', tone: 'default' })
    expect(formatEscrow('frozen')).toEqual({ label: 'frozen', tone: 'default' })
  })
})

describe('orders mapper DTO → page model', () => {
  it('maps a full order DTO into the stable view', () => {
    const view = toOrderView(
      buildOrderDto({
        id: 42,
        code: 'FDE-42',
        status: 'in_progress',
        escrow_status: 'held',
        engineer: { id: '9', display_name: '工程师阿远' },
        work_log_count: 3,
        claimed_at: '2026-11-01T08:00:00.000Z',
      }),
    )

    expect(view).toMatchObject({
      id: '42',
      code: 'FDE-42',
      title: '医疗影像数据标注与质检',
      industry: '医疗健康',
      deliveryDays: 7,
      deliveryLabel: '7 天',
      priceCents: 8_600_000,
      priceLabel: '¥86,000',
      status: 'in_progress',
      statusLabel: '交付中',
      statusTone: 'info',
      escrowStatus: 'held',
      escrowLabel: '资金托管中',
      escrowTone: 'accent',
      publisherId: '7',
      publisherName: 'Luna',
      engineerId: '9',
      engineerName: '工程师阿远',
      workLogCount: 3,
      createdAt: '2026-11-01T06:20:00.000Z',
      claimedAtLabel: expect.any(String),
      completedAtLabel: null,
    })
  })

  it('keeps unknown enum keys as labels instead of crashing', () => {
    const view = toOrderView(buildOrderDto({ status: 'archived', escrow_status: 'frozen' }))

    expect(view.status).toBe('archived')
    expect(view.statusLabel).toBe('archived')
    expect(view.statusTone).toBe('default')
    expect(view.escrowLabel).toBe('frozen')
    expect(view.escrowTone).toBe('default')
  })

  it('maps detail logs', () => {
    const detail = toOrderDetailView(buildOrderDetailDto())

    expect(detail.logs).toHaveLength(1)
    expect(detail.logs[0]).toMatchObject({
      id: '11',
      authorName: '工程师阿远',
      content: '完成首批 200 例标注，已提交质检。',
      workedHours: 6,
      createdAtLabel: expect.any(String),
    })
  })

  it('maps a work log', () => {
    const log = toWorkLogView(buildWorkLogDto({ worked_hours: null }))

    expect(log.workedHours).toBeNull()
    expect(log.authorName).toBe('工程师阿远')
  })
})

describe('orders mapper aggregation', () => {
  it('summarizes counts and held escrow money', () => {
    const stats = summarizeOrders([
      buildOrderView({ id: '1', status: 'open', escrowStatus: 'held', priceCents: 100_000 }),
      buildOrderView({ id: '2', status: 'open', escrowStatus: 'held', priceCents: 50_000 }),
      buildOrderView({ id: '3', status: 'in_progress', escrowStatus: 'held', priceCents: 25_000 }),
      buildOrderView({
        id: '4',
        status: 'completed',
        escrowStatus: 'released',
        priceCents: 10_000,
      }),
      buildOrderView({ id: '5', status: 'cancelled', escrowStatus: 'refunded', priceCents: 1 }),
    ])

    expect(stats).toEqual({
      total: 5,
      openCount: 2,
      inProgressCount: 1,
      completedCount: 1,
      escrowHeldCents: 175_000,
      escrowHeldLabel: '¥1,750',
    })
  })

  it('inserts new orders and replaces updated ones by id, newest first', () => {
    const older = buildOrderView({ id: '1', createdAt: '2026-10-01T00:00:00.000Z' })
    const newer = buildOrderView({ id: '2', createdAt: '2026-11-01T00:00:00.000Z' })
    const inserted = buildOrderView({ id: '3', createdAt: '2026-10-15T00:00:00.000Z' })

    expect(upsertOrder([newer, older], inserted).map((order) => order.id)).toEqual(['2', '3', '1'])

    const updated = { ...newer, title: '已更新的标题' }
    const afterUpdate = upsertOrder([newer, older], updated)
    expect(afterUpdate).toHaveLength(2)
    expect(afterUpdate.find((order) => order.id === '2')?.title).toBe('已更新的标题')
  })
})
