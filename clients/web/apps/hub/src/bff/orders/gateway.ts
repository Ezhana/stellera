import type { ZodType } from 'zod'

import type { OrderListFilter } from '@/models'
import { request } from '@/lib/http'

import { BffError } from '../errors'
import {
  orderDetailDtoSchema,
  orderDtoSchema,
  orderListDtoSchema,
  workLogDtoSchema,
  type OrderDetailDto,
  type OrderDto,
  type OrderListDto,
  type WorkLogDto,
} from './dto'
import type { CreateOrderInput, CreateWorkLogInput } from './types'

/** Server maximum; the hall list is client-filtered, so one page is enough for now. */
const HALL_PAGE_SIZE = 100

function parseDto<T>(schema: ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value)
  if (!result.success) {
    throw new BffError('malformed-response', '服务返回的订单数据格式异常。', {
      originalError: result.error,
    })
  }
  return result.data
}

function encodeId(id: string): string {
  return encodeURIComponent(id)
}

function isActiveStatus(
  status: OrderListFilter['status'],
): status is Exclude<OrderListFilter['status'], 'all' | undefined> {
  return typeof status === 'string' && status !== 'all'
}

/**
 * Port for the FDE order backend.
 *
 * Implemented today by `HttpOrderGateway` (direct `/api/v1/fde/*` calls). A future server-side BFF
 * can implement the same interface without touching the service or the pages.
 */
export interface OrderGateway {
  listOrders(token: string, filter?: OrderListFilter): Promise<OrderListDto>
  listMyOrders(token: string, filter?: OrderListFilter): Promise<OrderListDto>
  getOrder(token: string, id: string): Promise<OrderDetailDto>
  createOrder(token: string, input: CreateOrderInput): Promise<OrderDto>
  claimOrder(token: string, id: string): Promise<OrderDto>
  addWorkLog(token: string, id: string, input: CreateWorkLogInput): Promise<WorkLogDto>
  completeOrder(token: string, id: string): Promise<OrderDto>
}

export class HttpOrderGateway implements OrderGateway {
  async listOrders(token: string, filter?: OrderListFilter): Promise<OrderListDto> {
    const query = new URLSearchParams()
    if (isActiveStatus(filter?.status)) query.set('status', filter.status)
    const industry = filter?.industry?.trim()
    if (industry) query.set('industry', industry)
    const keyword = filter?.keyword?.trim()
    if (keyword) query.set('q', keyword)
    query.set('page', '1')
    query.set('page_size', String(HALL_PAGE_SIZE))

    const raw = await request<unknown>(`/fde/orders?${query.toString()}`, { token })
    return parseDto(orderListDtoSchema, raw)
  }

  async listMyOrders(token: string, filter?: OrderListFilter): Promise<OrderListDto> {
    const query = new URLSearchParams()
    if (isActiveStatus(filter?.status)) query.set('status', filter.status)
    const search = query.toString()
    const raw = await request<unknown>(`/fde/orders/mine${search ? `?${search}` : ''}`, { token })
    return parseDto(orderListDtoSchema, raw)
  }

  async getOrder(token: string, id: string): Promise<OrderDetailDto> {
    const raw = await request<unknown>(`/fde/orders/${encodeId(id)}`, { token })
    return parseDto(orderDetailDtoSchema, raw)
  }

  async createOrder(token: string, input: CreateOrderInput): Promise<OrderDto> {
    const raw = await request<unknown>('/fde/orders', {
      method: 'POST',
      token,
      body: {
        title: input.title,
        industry: input.industry,
        description: input.description,
        delivery_days: input.deliveryDays,
        price_cents: input.priceCents,
      },
    })
    return parseDto(orderDtoSchema, raw)
  }

  async claimOrder(token: string, id: string): Promise<OrderDto> {
    const raw = await request<unknown>(`/fde/orders/${encodeId(id)}/claim`, {
      method: 'POST',
      token,
    })
    return parseDto(orderDtoSchema, raw)
  }

  async addWorkLog(token: string, id: string, input: CreateWorkLogInput): Promise<WorkLogDto> {
    const raw = await request<unknown>(`/fde/orders/${encodeId(id)}/logs`, {
      method: 'POST',
      token,
      body: {
        content: input.content,
        worked_hours: input.workedHours,
      },
    })
    return parseDto(workLogDtoSchema, raw)
  }

  async completeOrder(token: string, id: string): Promise<OrderDto> {
    const raw = await request<unknown>(`/fde/orders/${encodeId(id)}/complete`, {
      method: 'POST',
      token,
    })
    return parseDto(orderDtoSchema, raw)
  }
}
