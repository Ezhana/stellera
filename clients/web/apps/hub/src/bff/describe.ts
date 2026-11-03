import type { PermissionActionView } from '@/models'

interface ObjectMeta {
  key: string
  label: string
}

const OBJECT_RULES: readonly {
  key: string
  label: string
  match: (pattern: string) => boolean
}[] = [
  { key: 'profile', label: '账户资料', match: (pattern) => pattern === '/api/v1/auth/me' },
  { key: 'session', label: '登录会话', match: (pattern) => pattern === '/api/v1/auth/logout' },
  { key: 'wallet', label: '钱包', match: (pattern) => pattern.startsWith('/api/v1/wallet') },
  { key: 'fde', label: 'FDE 订单', match: (pattern) => pattern.startsWith('/api/v1/fde') },
  { key: 'admin', label: '管理接口', match: (pattern) => pattern.startsWith('/api/v1/admin') },
  { key: 'business', label: '全部业务接口', match: (pattern) => pattern === '/api/v1/*' },
]

const GROUP_ORDER: Readonly<Record<string, number>> = {
  profile: 0,
  session: 1,
  wallet: 2,
  fde: 3,
  business: 4,
  admin: 5,
}

const METHOD_LABELS: Readonly<Record<string, string>> = {
  GET: '查看',
  HEAD: '查看',
  POST: '创建',
  PUT: '更新',
  PATCH: '更新',
  DELETE: '删除',
}

const METHOD_ORDER: Readonly<Record<string, number>> = {
  all: -1,
  GET: 0,
  HEAD: 1,
  POST: 2,
  PUT: 3,
  PATCH: 4,
  DELETE: 5,
}

const ALL_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] as const

/** Map a raw Casbin object pattern to a stable, human-readable permission group. */
export function describeObject(pattern: string): ObjectMeta {
  const rule = OBJECT_RULES.find((candidate) => candidate.match(pattern))
  if (rule) return { key: rule.key, label: rule.label }
  return { key: 'other', label: '其他接口' }
}

/** Map a raw Casbin action pattern (`GET`, `^(GET|POST)$`, ...) to readable actions. */
export function describeActions(pattern: string): PermissionActionView[] {
  const cleaned = pattern.trim().replace(/^\^/, '').replace(/\$$/, '')
  const inner = cleaned.startsWith('(') && cleaned.endsWith(')') ? cleaned.slice(1, -1) : cleaned

  if (inner === '.*' || inner === '(.+)' || inner === '.+') {
    return [{ key: 'all', label: '全部操作' }]
  }

  const tokens = inner
    .split('|')
    .map((token) => token.trim())
    .filter((token) => /^[A-Z]+$/.test(token))

  if (tokens.length === 0) {
    return [{ key: pattern, label: pattern }]
  }

  const unique = [...new Set(tokens)].sort(
    (left, right) => (METHOD_ORDER[left] ?? 99) - (METHOD_ORDER[right] ?? 99),
  )

  if (ALL_METHODS.every((method) => unique.includes(method))) {
    return [{ key: 'all', label: '全部操作' }]
  }

  return unique.map((method) => ({
    key: method,
    label: METHOD_LABELS[method] ?? method,
  }))
}

export function groupOrder(key: string): number {
  return GROUP_ORDER[key] ?? 99
}

export function actionOrder(key: string): number {
  return METHOD_ORDER[key] ?? 99
}
