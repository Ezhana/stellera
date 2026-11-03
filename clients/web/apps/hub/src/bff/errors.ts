import { ApiError } from '@/lib/http'

/** Stable error codes the pages can branch on without knowing HTTP status codes. */
export type BffErrorCode =
  | 'invalid-credentials'
  | 'forbidden'
  | 'not-found'
  | 'conflict'
  | 'invalid-input'
  | 'network'
  | 'server'
  | 'session-expired'
  | 'malformed-response'
  | 'unknown'

export type BffErrorContext = 'login' | 'session' | 'refresh' | 'orders' | 'wallet' | 'admin'

interface BffErrorOptions {
  status?: number
  originalError?: unknown
}

/**
 * Transport/response error normalized by the BFF.
 *
 * Pages map `code` to their own copy; they never import `ApiError` or inspect backend `detail`.
 */
export class BffError extends Error {
  readonly code: BffErrorCode
  readonly status: number | undefined
  readonly originalError: unknown

  constructor(code: BffErrorCode, message: string, options: BffErrorOptions = {}) {
    super(message)
    this.name = 'BffError'
    this.code = code
    this.status = options.status
    this.originalError = options.originalError
  }
}

function mapStatus(status: number, context: BffErrorContext): BffErrorCode {
  if (status === 401) return context === 'login' ? 'invalid-credentials' : 'session-expired'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'not-found'
  if (status === 409) return 'conflict'
  if (status === 400 || status === 422) return 'invalid-input'
  if (status === 0) return 'network'
  if (status >= 500) return 'server'
  return 'unknown'
}

const CODE_MESSAGES: Readonly<Record<BffErrorCode, string>> = {
  'invalid-credentials': '用户名或密码不正确。',
  forbidden: '当前账号没有访问权限。',
  'not-found': '请求的资源不存在或已被移除。',
  conflict: '当前状态不允许该操作，请刷新后重试。',
  'invalid-input': '提交的内容不符合要求，请检查后重试。',
  network: '无法连接到服务，请检查网络后重试。',
  server: '服务暂时不可用，请稍后再试。',
  'session-expired': '登录已过期，请重新登录。',
  'malformed-response': '服务返回的数据格式异常，请联系管理员。',
  unknown: '请求失败，请稍后再试。',
}

/** Convert an unknown transport error into the BFF's stable error contract. */
export function toBffError(error: unknown, context: BffErrorContext): BffError {
  if (error instanceof BffError) return error

  if (error instanceof ApiError) {
    const code = mapStatus(error.status, context)
    const message =
      (code === 'conflict' || code === 'invalid-input' ? error.detailMessage : null) ??
      CODE_MESSAGES[code]
    return new BffError(code, message, { status: error.status, originalError: error })
  }

  return new BffError('unknown', CODE_MESSAGES.unknown, { originalError: error })
}
