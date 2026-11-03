import { authBff } from '@/bff/auth'

import { HttpOrderGateway } from './gateway'
import { WebSocketOrderRealtimeGateway } from './realtime'
import { OrdersBff } from './service'

/** App-wide orders BFF singleton; pages only consume this instance. */
export const ordersBff = new OrdersBff(
  new HttpOrderGateway(),
  new WebSocketOrderRealtimeGateway(),
  authBff,
)

export { OrdersBff } from './service'
export { HttpOrderGateway } from './gateway'
export type { OrderGateway } from './gateway'
export { WebSocketOrderRealtimeGateway, buildRealtimeUrl, parseRealtimeFrame } from './realtime'
export type {
  OrderRealtimeConnection,
  OrderRealtimeEvent,
  OrderRealtimeGateway,
  OrderRealtimeHandlers,
  OrderRealtimeState,
} from './realtime'
export type { CreateApplicationInput, CreateOrderInput, CreateWorkLogInput } from './types'
export {
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
} from './mapper'
