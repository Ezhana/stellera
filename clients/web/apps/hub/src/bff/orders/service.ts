import type {
  FdeOrderDetailView,
  FdeOrderView,
  OrderListFilter,
  OrderListModel,
  WorkLogView,
} from '@/models'

import { BffError, toBffError } from '../errors'
import type { TokenProvider } from '../token-provider'
import type { OrderListDto } from './dto'
import type { OrderGateway } from './gateway'
import { summarizeOrders, toOrderDetailView, toOrderView, toWorkLogView } from './mapper'
import type {
  OrderRealtimeConnection,
  OrderRealtimeGateway,
  OrderRealtimeHandlers,
} from './realtime'
import type { CreateOrderInput, CreateWorkLogInput } from './types'

/** Kept for backwards compatibility with existing orders tests; the port lives in `bff/token-provider`. */
export type OrderTokenProvider = TokenProvider

/**
 * Orders BFF.
 *
 * Owns:
 * - token lookup (pages never see tokens);
 * - gateway/realtime orchestration;
 * - DTO → page model mapping, stat aggregation and timestamps;
 * - normalization of every transport error into `BffError`.
 */
export class OrdersBff {
  constructor(
    private readonly gateway: OrderGateway,
    private readonly realtime: OrderRealtimeGateway,
    private readonly tokenProvider: OrderTokenProvider,
  ) {}

  async listOrders(filter?: OrderListFilter): Promise<OrderListModel> {
    const token = this.requireToken()
    try {
      return this.toListModel(await this.gateway.listOrders(token, filter))
    } catch (error) {
      throw toBffError(error, 'orders')
    }
  }

  async listMyOrders(filter?: OrderListFilter): Promise<OrderListModel> {
    const token = this.requireToken()
    try {
      return this.toListModel(await this.gateway.listMyOrders(token, filter))
    } catch (error) {
      throw toBffError(error, 'orders')
    }
  }

  async getOrder(id: string): Promise<FdeOrderDetailView> {
    const token = this.requireToken()
    try {
      return toOrderDetailView(await this.gateway.getOrder(token, id))
    } catch (error) {
      throw toBffError(error, 'orders')
    }
  }

  async createOrder(input: CreateOrderInput): Promise<FdeOrderView> {
    const token = this.requireToken()
    try {
      return toOrderView(await this.gateway.createOrder(token, input))
    } catch (error) {
      throw toBffError(error, 'orders')
    }
  }

  async claimOrder(id: string): Promise<FdeOrderView> {
    const token = this.requireToken()
    try {
      return toOrderView(await this.gateway.claimOrder(token, id))
    } catch (error) {
      throw toBffError(error, 'orders')
    }
  }

  async addWorkLog(id: string, input: CreateWorkLogInput): Promise<WorkLogView> {
    const token = this.requireToken()
    try {
      return toWorkLogView(await this.gateway.addWorkLog(token, id, input))
    } catch (error) {
      throw toBffError(error, 'orders')
    }
  }

  async completeOrder(id: string): Promise<FdeOrderView> {
    const token = this.requireToken()
    try {
      return toOrderView(await this.gateway.completeOrder(token, id))
    } catch (error) {
      throw toBffError(error, 'orders')
    }
  }

  /** Open the realtime feed. The returned connection must be closed on page unmount. */
  connectRealtime(handlers: OrderRealtimeHandlers): OrderRealtimeConnection {
    const token = this.requireToken()
    try {
      return this.realtime.connect(token, handlers)
    } catch (error) {
      throw toBffError(error, 'orders')
    }
  }

  private toListModel(dto: OrderListDto): OrderListModel {
    const orders = dto.items.map(toOrderView)
    return {
      orders,
      total: dto.total > 0 ? dto.total : orders.length,
      stats: summarizeOrders(orders),
      fetchedAt: new Date().toISOString(),
    }
  }

  private requireToken(): string {
    const token = this.tokenProvider.accessToken()
    if (!token) {
      throw new BffError('session-expired', '登录已过期，请重新登录。')
    }
    return token
  }
}
