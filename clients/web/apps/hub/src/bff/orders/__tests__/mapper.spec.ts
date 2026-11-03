import { describe, expect, it } from 'vitest'

import {
  formatApplicationStatus,
  formatApplicationType,
  formatDateTimeLabel,
  formatDeliveryLabel,
  formatEscrow,
  formatPriceCents,
  formatStatus,
  summarizeOrders,
  toApplicationListModel,
  toApplicationView,
  toOrderDetailView,
  toOrderView,
  toWorkLogView,
  upsertOrder,
} from '../mapper'
import {
  buildApplicationDto,
  buildApplicationListDto,
  buildOrderDetailDto,
  buildOrderDto,
  buildOrderView,
  buildWorkLogDto,
} from './fixtures'

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
        engineer: { id: '9', display_name: '工程师阿远', certifications: ['realname', 'engineer'] },
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
      publisherCertifications: ['realname', 'enterprise'],
      engineerId: '9',
      engineerName: '工程师阿远',
      engineerCertifications: ['realname', 'engineer'],
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

  it('maps detail logs and the full application history', () => {
    const detail = toOrderDetailView(buildOrderDetailDto())

    expect(detail.logs).toHaveLength(1)
    expect(detail.applications).toHaveLength(1)
    expect(detail.applications[0]).toMatchObject({
      id: '1',
      type: 'accept',
      status: 'pending',
      applicantName: '会员（演示）',
    })
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

  it('degrades unknown certifications to null', () => {
    const view = toOrderView(
      buildOrderDto({
        publisher: { id: 7, display_name: 'Luna', certifications: ['vip', 'realname'] },
        engineer: { id: 9, display_name: '工程师阿远', certifications: [] },
      }),
    )

    expect(view.publisherCertifications).toEqual(['realname'])
    expect(view.engineerCertifications).toEqual([])
    expect(view.engineerName).toBe('工程师阿远')
  })
})

describe('orders mapper applications', () => {
  it('maps an application with its order, applicant and reviewer', () => {
    const view = toApplicationView(
      buildApplicationDto({
        id: 5,
        status: 'approved',
        message: '有医疗行业交付经验',
        review_note: '欢迎加入',
        applicant: { id: 6, display_name: '会员（演示）', certifications: [] },
        reviewer: { id: 7, display_name: 'Luna', certifications: ['realname', 'enterprise'] },
        reviewed_at: '2026-11-01T08:00:00.000Z',
      }),
    )

    expect(view).toMatchObject({
      id: '5',
      type: 'accept',
      typeLabel: '接单申请',
      typeTone: 'info',
      status: 'approved',
      statusLabel: '已通过',
      statusTone: 'success',
      message: '有医疗行业交付经验',
      reviewNote: '欢迎加入',
      applicantName: '会员（演示）',
      applicantId: '6',
      applicantCertifications: [],
      reviewerName: 'Luna',
      reviewerId: '7',
      reviewerCertifications: ['realname', 'enterprise'],
      reviewedAtLabel: expect.any(String),
      createdAtLabel: expect.any(String),
    })
    expect(view.order.title).toBe('医疗影像数据标注与质检')
  })

  it('degrades unknown application type/status and keeps nullable fields', () => {
    const view = toApplicationView(
      buildApplicationDto({ type: 'mystery', status: 'archived', reviewer: null }),
    )

    expect(view.typeLabel).toBe('mystery')
    expect(view.typeTone).toBe('default')
    expect(view.statusLabel).toBe('archived')
    expect(view.statusTone).toBe('default')
    expect(view.reviewerName).toBeNull()
    expect(view.reviewedAtLabel).toBeNull()
  })

  it('formats application presentation catalogues', () => {
    expect(formatApplicationType('accept')).toEqual({ label: '接单申请', tone: 'info' })
    expect(formatApplicationType('delivery')).toEqual({ label: '交付申请', tone: 'accent' })
    expect(formatApplicationStatus('pending')).toEqual({ label: '待审批', tone: 'warning' })
    expect(formatApplicationStatus('rejected')).toEqual({ label: '已驳回', tone: 'error' })
    expect(formatApplicationStatus('withdrawn')).toEqual({ label: '已撤回', tone: 'default' })
  })

  it('maps an application list and falls back to the loaded length', () => {
    const model = toApplicationListModel(
      buildApplicationListDto(
        [buildApplicationDto(), buildApplicationDto({ id: 2, type: 'delivery' })],
        { total: 0 },
      ),
    )

    expect(model.applications).toHaveLength(2)
    expect(model.total).toBe(2)
    expect(model.page).toBe(1)
    expect(model.pageSize).toBe(20)
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
