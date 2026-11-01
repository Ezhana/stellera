import { ApiError } from '@/lib/http'

/** Stable error codes the pages can branch on without knowing HTTP status codes. */
export type BffErrorCode =
  | 'invalid-credentials'
  | 'forbidden'
  | 'network'
  | 'server'
  | 'session-expired'
  | 'malformed-response'
  | 'unknown'

export type BffErrorContext = 'login' | 'session' | 'refresh'

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
  if (status === 0) return 'network'
  if (status >= 500) return 'server'
  return 'unknown'
}

/** Convert an unknown transport error into the BFF's stable error contract. */
export function toBffError(error: unknown, context: BffErrorContext): BffError {
  if (error instanceof BffError) return error

  if (error instanceof ApiError) {
    const code = mapStatus(error.status, context)
    const message =
      code === 'invalid-credentials'
        ? '用户名或密码不正确。'
        : code === 'session-expired'
          ? '登录已过期，请重新登录。'
          : code === 'forbidden'
            ? '当前账号没有访问权限。'
            : code === 'network'
              ? '无法连接到服务，请检查网络后重试。'
              : code === 'server'
                ? '服务暂时不可用，请稍后再试。'
                : (error.detailMessage ?? '请求失败，请稍后再试。')
    return new BffError(code, message, { status: error.status, originalError: error })
  }

  return new BffError('unknown', '发生未知错误，请稍后再试。', { originalError: error })
}
