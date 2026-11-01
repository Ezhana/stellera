import { describe, expect, it } from 'vitest'

import { buildRealtimeUrl, parseRealtimeFrame } from '../realtime'
import { buildOrderDto } from './fixtures'

describe('buildRealtimeUrl', () => {
  it('turns a relative API base into an absolute ws URL', () => {
    expect(buildRealtimeUrl('token-1', '/api/v1', 'http://localhost:5173')).toBe(
      'ws://localhost:5173/api/v1/fde/ws?token=token-1',
    )
  })

  it('uses wss when the page origin is https', () => {
    expect(buildRealtimeUrl('token-1', '/api/v1', 'https://hub.stellera.dev')).toBe(
      'wss://hub.stellera.dev/api/v1/fde/ws?token=token-1',
    )
  })

  it('keeps an absolute API base', () => {
    expect(
      buildRealtimeUrl('token-1', 'https://api.stellera.dev/api/v1', 'http://localhost:5173'),
    ).toBe('wss://api.stellera.dev/api/v1/fde/ws?token=token-1')
  })

  it('tolerates a trailing slash and encodes the token', () => {
    const url = buildRealtimeUrl('a/b+c', '/api/v1/', 'http://localhost:5173')

    expect(url).toBe('ws://localhost:5173/api/v1/fde/ws?token=a%2Fb%2Bc')
  })
})

describe('parseRealtimeFrame', () => {
  it('parses the connected frame', () => {
    expect(
      parseRealtimeFrame(
        JSON.stringify({ type: 'connected', server_time: '2026-11-01T00:00:00Z' }),
      ),
    ).toEqual({ type: 'connected', serverTime: '2026-11-01T00:00:00Z' })
  })

  it('maps order frames into page models', () => {
    const event = parseRealtimeFrame(
      JSON.stringify({ type: 'order.created', order: buildOrderDto({ id: 9 }) }),
    )

    expect(event?.type).toBe('order.created')
    expect(event && 'order' in event ? event.order.id : null).toBe('9')
    expect(event && 'order' in event ? event.order.priceLabel : null).toBe('¥86,000')
  })

  it('accepts order.updated frames', () => {
    const event = parseRealtimeFrame(
      JSON.stringify({ type: 'order.updated', order: buildOrderDto({ status: 'completed' }) }),
    )

    expect(event?.type).toBe('order.updated')
    expect(event && 'order' in event ? event.order.statusLabel : null).toBe('已完成')
  })

  it('ignores malformed, unknown and invalid-order frames', () => {
    expect(parseRealtimeFrame('not json')).toBeNull()
    expect(parseRealtimeFrame(JSON.stringify({ type: 'ping' }))).toBeNull()
    expect(parseRealtimeFrame(JSON.stringify({ type: 'order.created' }))).toBeNull()
    expect(
      parseRealtimeFrame(JSON.stringify({ type: 'order.created', order: { id: 1 } })),
    ).toBeNull()
    expect(parseRealtimeFrame(null)).toBeNull()
    expect(parseRealtimeFrame(42)).toBeNull()
  })
})
