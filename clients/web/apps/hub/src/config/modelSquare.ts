const DEFAULT_MODEL_SQUARE_PORT = 3000
const MODEL_SQUARE_PATH = '/pricing'

/**
 * Absolute URL of the new-api pricing page (模型广场).
 *
 * Defaults to `/pricing` on the current host's port 3000; `VITE_MODEL_SQUARE_URL`
 * overrides the whole URL (including path) for other hosts or reverse proxies.
 */
export function resolveModelSquareUrl(
  origin: Pick<Location, 'protocol' | 'hostname'> = window.location,
  configured: string | undefined = import.meta.env.VITE_MODEL_SQUARE_URL,
): string {
  const override = configured?.trim()
  if (override) return override
  return `${origin.protocol}//${origin.hostname}:${DEFAULT_MODEL_SQUARE_PORT}${MODEL_SQUARE_PATH}`
}

export const MODEL_SQUARE_URL = resolveModelSquareUrl()
