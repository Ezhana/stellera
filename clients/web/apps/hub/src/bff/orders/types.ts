import type { ApplicationType } from '@/models'

/**
 * Page-facing inputs for the orders BFF (camelCase, already validated by the page).
 */

/** Payload for publishing a new FDE order; the gateway converts it to the snake_case wire shape. */
export interface CreateOrderInput {
  title: string
  industry: string
  description: string
  deliveryDays: number
  priceCents: number
}

/** Payload for appending a delivery log to an order. */
export interface CreateWorkLogInput {
  content: string
  workedHours: number | null
}

/** Payload for a new accept/delivery application; `message` is optional and capped at 500 chars. */
export interface CreateApplicationInput {
  type: ApplicationType
  message: string | null
}
