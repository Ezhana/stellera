/**
 * Minimal JSON HTTP client for the STELLERA HUB API.
 *
 * - Base URL: `(VITE_API_BASE_URL ?? '/api') + '/v1'`
 * - Throws {@link ApiError} with the HTTP status and the parsed `detail` on non-2xx responses.
 * - Treats network failures and timeouts as status `0`.
 */

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/+$/, '')
export const API_BASE_URL = `${baseUrl}/v1`

const DEFAULT_TIMEOUT_MS = 15_000

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface RequestOptions {
  method?: HttpMethod
  body?: unknown
  /** Bearer token for authenticated endpoints. */
  token?: string | null
  timeoutMs?: number
  signal?: AbortSignal
}

/** FastAPI `detail` values can be a string, a validation-issue array or an object. */
function extractDetail(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (typeof item === 'object' && item !== null && 'msg' in item) {
          const msg = (item as { msg?: unknown }).msg
          return typeof msg === 'string' ? msg : null
        }
        return null
      })
      .filter((message): message is string => Boolean(message))
    return messages.length > 0 ? messages.join('；') : null
  }

  return null
}

export class ApiError extends Error {
  /** HTTP status, or `0` for a network error / timeout. */
  readonly status: number
  /** Parsed response body (`detail` field for FastAPI errors), or `null`. */
  readonly detail: unknown

  constructor(status: number, message: string, detail: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }

  get isNetworkError(): boolean {
    return this.status === 0
  }

  /** Human-readable backend detail, when the API returned one. */
  get detailMessage(): string | null {
    return extractDetail(this.detail)
  }
}

async function readPayload(response: Response): Promise<unknown> {
  if (response.status === 204) return null
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}

/**
 * Perform a JSON request against the API and return the parsed body.
 * The caller is responsible for validating the response shape.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, token, timeoutMs = DEFAULT_TIMEOUT_MS, signal } = options

  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const forwardAbort = () => controller.abort()
  signal?.addEventListener('abort', forwardAbort)

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  try {
    let response: Response
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      })
    } catch (error) {
      if (timedOut) throw new ApiError(0, '请求超时，请稍后重试。')
      if (signal?.aborted) throw error
      throw new ApiError(0, '网络连接失败，请检查网络后重试。')
    }

    const payload = await readPayload(response)
    if (!response.ok) {
      const detail = extractDetail(payload)
      throw new ApiError(response.status, detail ?? `请求失败（HTTP ${response.status}）`, payload)
    }

    return payload as T
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', forwardAbort)
  }
}
