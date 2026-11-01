import type { FdeOrderView } from '@/models'
import { API_BASE_URL } from '@/lib/http'

import { orderDtoSchema } from './dto'
import { toOrderView } from './mapper'

export type OrderRealtimeState = 'connecting' | 'live' | 'reconnecting' | 'offline'

export interface OrderRealtimeConnectedEvent {
  type: 'connected'
  serverTime: string
}

export interface OrderRealtimeOrderEvent {
  type: 'order.created' | 'order.updated'
  order: FdeOrderView
}

/** Public realtime event: wire DTOs are already mapped into page models. */
export type OrderRealtimeEvent = OrderRealtimeConnectedEvent | OrderRealtimeOrderEvent

export interface OrderRealtimeHandlers {
  onEvent: (event: OrderRealtimeEvent) => void
  onStateChange: (state: OrderRealtimeState) => void
}

export interface OrderRealtimeConnection {
  close(): void
}

/** Port for the realtime order feed (WebSocket today, polling/SSE could implement it later). */
export interface OrderRealtimeGateway {
  connect(token: string, handlers: OrderRealtimeHandlers): OrderRealtimeConnection
}

/** Exponential backoff (ms), capped at 15s. */
const RECONNECT_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 15_000]

/** Close code the backend uses for an invalid/expired access token; never retry it. */
const UNAUTHORIZED_CLOSE_CODE = 4401

/**
 * Build the absolute WebSocket URL for the order feed.
 *
 * `base` is the HTTP API base (`/api/v1` by default, or an absolute
 * `https://host/api/v1`), and `origin` is used only for relative bases so the resulting URL is
 * always absolute for the WebSocket constructor.
 */
export function buildRealtimeUrl(
  token: string,
  base: string = API_BASE_URL,
  origin: string = window.location.origin,
): string {
  const path = `${base.replace(/\/+$/, '')}/fde/ws?token=${encodeURIComponent(token)}`
  const url = new URL(path, origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

/** Parse one server frame defensively; malformed/unknown frames are ignored. */
export function parseRealtimeFrame(raw: unknown): OrderRealtimeEvent | null {
  if (typeof raw !== 'string') return null

  let payload: unknown
  try {
    payload = JSON.parse(raw) as unknown
  } catch {
    return null
  }
  if (typeof payload !== 'object' || payload === null) return null

  const frame = payload as Record<string, unknown>
  const type = frame.type

  if (type === 'connected') {
    return {
      type: 'connected',
      serverTime:
        typeof frame.server_time === 'string' ? frame.server_time : new Date().toISOString(),
    }
  }

  if (type === 'order.created' || type === 'order.updated') {
    const parsed = orderDtoSchema.safeParse(frame.order)
    if (!parsed.success) return null
    return { type, order: toOrderView(parsed.data) }
  }

  return null
}

export class WebSocketOrderRealtimeGateway implements OrderRealtimeGateway {
  connect(token: string, handlers: OrderRealtimeHandlers): OrderRealtimeConnection {
    let socket: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let closed = false
    let attempt = 0
    let state: OrderRealtimeState | null = null

    const emitState = (next: OrderRealtimeState): void => {
      // Once the page closed the connection we must never emit again.
      if (closed || state === next) return
      state = next
      handlers.onStateChange(next)
    }

    const open = (): void => {
      if (closed) return
      emitState(attempt === 0 ? 'connecting' : 'reconnecting')

      let nextSocket: WebSocket
      try {
        nextSocket = new WebSocket(buildRealtimeUrl(token))
      } catch {
        scheduleReconnect()
        return
      }
      socket = nextSocket

      nextSocket.onopen = () => {
        if (closed) return
        attempt = 0
        emitState('live')
      }

      nextSocket.onmessage = (event: MessageEvent) => {
        if (closed) return
        const parsed = parseRealtimeFrame(event.data)
        if (parsed) handlers.onEvent(parsed)
      }

      nextSocket.onclose = (event: CloseEvent) => {
        socket = null
        if (closed) return
        if (event.code === UNAUTHORIZED_CLOSE_CODE) {
          closed = true
          emitState('offline')
          return
        }
        scheduleReconnect()
      }

      // Errors are followed by a close event; reconnection is handled there.
      nextSocket.onerror = () => undefined
    }

    const scheduleReconnect = (): void => {
      if (closed) return
      const delay = RECONNECT_DELAYS_MS[Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)] ?? 15_000
      attempt += 1
      emitState('reconnecting')
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        open()
      }, delay)
    }

    open()

    return {
      close(): void {
        if (closed) return
        closed = true
        if (reconnectTimer) {
          clearTimeout(reconnectTimer)
          reconnectTimer = null
        }
        const current = socket
        socket = null
        if (current) {
          current.onopen = null
          current.onmessage = null
          current.onerror = null
          current.onclose = null
          try {
            current.close()
          } catch {
            // The socket may already be closing; nothing else to clean up.
          }
        }
      },
    }
  }
}
