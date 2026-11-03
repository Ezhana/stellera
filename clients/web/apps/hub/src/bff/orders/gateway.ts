import type { ZodType } from 'zod'

import type { ApplicationListFilter, OrderListFilter } from '@/models'
import { request } from '@/lib/http'

import { BffError } from '../errors'
import {
  applicationDtoSchema,
  applicationListDtoSchema,
  orderDetailDtoSchema,
  orderDtoSchema,
  orderListDtoSchema,
  workLogDtoSchema,
  type ApplicationDto,
  type ApplicationListDto,
  type OrderDetailDto,
  type OrderDto,
  type OrderListDto,
  type WorkLogDto,
} from './dto'
import type { CreateApplicationInput, CreateOrderInput, CreateWorkLogInput } from './types'

/** Server maximum; the hall list is client-filtered, so one page is enough for now. */
const HALL_PAGE_SIZE = 100
const APPLICATION_PAGE_SIZE = 20

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

function isActiveApplicationFilter(value: string | undefined): value is string {
  return typeof value === 'string' && value !== 'all'
}

/** Build the query string for `/fde/applications/*` list endpoints. */
function applicationQuery(filter?: ApplicationListFilter): string {
  const query = new URLSearchParams()
  const type = filter?.type
  if (isActiveApplicationFilter(type)) query.set('type', type)
  const status = filter?.status
  if (isActiveApplicationFilter(status)) query.set('status', status)
  query.set('page', String(filter?.page ?? 1))
  query.set('page_size', String(filter?.pageSize ?? APPLICATION_PAGE_SIZE))
  return query.toString()
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
  listAssignedOrders(token: string, filter?: OrderListFilter): Promise<OrderListDto>
  getOrder(token: string, id: string): Promise<OrderDetailDto>
  createOrder(token: string, input: CreateOrderInput): Promise<OrderDto>
  cancelOrder(token: string, id: string): Promise<OrderDto>
  addWorkLog(token: string, id: string, input: CreateWorkLogInput): Promise<WorkLogDto>
  applyForOrder(
    token: string,
    orderId: string,
    input: CreateApplicationInput,
  ): Promise<ApplicationDto>
  listMyApplications(token: string, filter?: ApplicationListFilter): Promise<ApplicationListDto>
  listReceivedApplications(
    token: string,
    filter?: ApplicationListFilter,
  ): Promise<ApplicationListDto>
  approveApplication(token: string, id: string, note?: string | null): Promise<ApplicationDto>
  rejectApplication(token: string, id: string, note?: string | null): Promise<ApplicationDto>
  withdrawApplication(token: string, id: string): Promise<ApplicationDto>
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

  async listAssignedOrders(token: string, filter?: OrderListFilter): Promise<OrderListDto> {
    const query = new URLSearchParams()
    if (isActiveStatus(filter?.status)) query.set('status', filter.status)
    query.set('page', '1')
    query.set('page_size', String(HALL_PAGE_SIZE))
    const raw = await request<unknown>(`/fde/orders/assigned?${query.toString()}`, { token })
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

  async cancelOrder(token: string, id: string): Promise<OrderDto> {
    const raw = await request<unknown>(`/fde/orders/${encodeId(id)}/cancel`, {
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

  async applyForOrder(
    token: string,
    orderId: string,
    input: CreateApplicationInput,
  ): Promise<ApplicationDto> {
    const raw = await request<unknown>(`/fde/orders/${encodeId(orderId)}/applications`, {
      method: 'POST',
      token,
      body: {
        type: input.type,
        message: input.message ?? undefined,
      },
    })
    return parseDto(applicationDtoSchema, raw)
  }

  async listMyApplications(
    token: string,
    filter?: ApplicationListFilter,
  ): Promise<ApplicationListDto> {
    const raw = await request<unknown>(`/fde/applications/mine?${applicationQuery(filter)}`, {
      token,
    })
    return parseDto(applicationListDtoSchema, raw)
  }

  async listReceivedApplications(
    token: string,
    filter?: ApplicationListFilter,
  ): Promise<ApplicationListDto> {
    const raw = await request<unknown>(`/fde/applications/received?${applicationQuery(filter)}`, {
      token,
    })
    return parseDto(applicationListDtoSchema, raw)
  }

  async approveApplication(
    token: string,
    id: string,
    note?: string | null,
  ): Promise<ApplicationDto> {
    const raw = await request<unknown>(`/fde/applications/${encodeId(id)}/approve`, {
      method: 'POST',
      token,
      body: note ? { note } : {},
    })
    return parseDto(applicationDtoSchema, raw)
  }

  async rejectApplication(
    token: string,
    id: string,
    note?: string | null,
  ): Promise<ApplicationDto> {
    const raw = await request<unknown>(`/fde/applications/${encodeId(id)}/reject`, {
      method: 'POST',
      token,
      body: note ? { note } : {},
    })
    return parseDto(applicationDtoSchema, raw)
  }

  async withdrawApplication(token: string, id: string): Promise<ApplicationDto> {
    const raw = await request<unknown>(`/fde/applications/${encodeId(id)}/withdraw`, {
      method: 'POST',
      token,
    })
    return parseDto(applicationDtoSchema, raw)
  }
}
