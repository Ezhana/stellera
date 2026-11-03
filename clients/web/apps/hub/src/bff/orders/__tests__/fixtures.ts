import type { FdeOrderView, ViewerProfile } from '@/models'

import type { OrderDetailDto, OrderDto, OrderListDto, WorkLogDto } from '../dto'
import { toOrderView } from '../mapper'

/** Deterministic DTO/view fixtures shared by the BFF and page tests. */
export function buildOrderDto(overrides: Partial<OrderDto> = {}): OrderDto {
  return {
    id: 1,
    code: 'FDE-20261101-0001',
    title: '医疗影像数据标注与质检',
    industry: '医疗健康',
    description: '完成 500 例影像数据的标注与抽检。',
    delivery_days: 7,
    price_cents: 8_600_000,
    status: 'open',
    escrow_status: 'held',
    publisher: { id: 7, display_name: 'Luna' },
    engineer: null,
    work_log_count: 0,
    created_at: '2026-11-01T06:20:00.000Z',
    updated_at: '2026-11-01T06:20:00.000Z',
    claimed_at: null,
    completed_at: null,
    ...overrides,
  }
}

export function buildOrderView(overrides: Partial<FdeOrderView> = {}): FdeOrderView {
  return { ...toOrderView(buildOrderDto()), ...overrides }
}

export function buildOrderListDto(
  items: OrderDto[] = [buildOrderDto()],
  overrides: Partial<OrderListDto> = {},
): OrderListDto {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 100,
    ...overrides,
  }
}

export function buildWorkLogDto(overrides: Partial<WorkLogDto> = {}): WorkLogDto {
  return {
    id: 11,
    order_id: 1,
    author: { id: 9, display_name: '工程师阿远' },
    content: '完成首批 200 例标注，已提交质检。',
    worked_hours: 6,
    created_at: '2026-11-01T10:30:00.000Z',
    ...overrides,
  }
}

export function buildOrderDetailDto(overrides: Partial<OrderDetailDto> = {}): OrderDetailDto {
  return {
    ...buildOrderDto(),
    logs: [buildWorkLogDto()],
    ...overrides,
  }
}

export function buildViewer(overrides: Partial<ViewerProfile> = {}): ViewerProfile {
  return {
    id: '7',
    username: 'luna',
    displayName: 'Luna',
    email: 'luna@example.com',
    initials: 'LU',
    status: 'active',
    statusLabel: '已启用',
    isAdmin: false,
    roles: [{ key: 'enterprise', label: '企业', tone: 'accent' }],
    permissionGroups: [],
    permissionCount: 0,
    capabilities: {
      publishOrder: true,
      claimOrder: false,
      submitOrderLog: false,
      completeOrder: false,
      viewWallet: true,
      redeemCode: true,
      manageAdmin: false,
    },
    ...overrides,
  }
}
