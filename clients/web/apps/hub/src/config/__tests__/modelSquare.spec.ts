import { describe, expect, it } from 'vitest'

import { resolveModelSquareUrl } from '../modelSquare'

const origin = { protocol: 'http:', hostname: 'localhost' }

describe('resolveModelSquareUrl', () => {
  it('defaults to the /pricing route on port 3000 of the current host', () => {
    expect(resolveModelSquareUrl(origin, undefined)).toBe('http://localhost:3000/pricing')
    expect(resolveModelSquareUrl({ protocol: 'https:', hostname: 'hub.example.com' }, '')).toBe(
      'https://hub.example.com:3000/pricing',
    )
  })

  it('uses the configured URL when provided', () => {
    expect(resolveModelSquareUrl(origin, ' https://models.example.com/pricing ')).toBe(
      'https://models.example.com/pricing',
    )
  })
})
