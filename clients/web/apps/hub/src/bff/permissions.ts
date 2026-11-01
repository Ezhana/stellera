/** Minimal permission shape shared by the DTO and the viewer mapper. */
export interface PermissionLike {
  object: string
  action: string
}

/**
 * Frontend-side Casbin-compatible matcher for the subset the backend policies use:
 * `keyMatch2`-style path patterns (`*`, `:param`, trailing wildcards) and `regexMatch`-style action
 * patterns.
 *
 * The BFF uses this to derive viewer capabilities from backend permissions; pages never parse
 * policies.
 */
export function permissionAllows(
  permissions: readonly PermissionLike[],
  path: string,
  method: string,
): boolean {
  return permissions.some(
    (permission) =>
      matchesObjectPattern(permission.object, path) &&
      matchesActionPattern(permission.action, method),
  )
}

export function matchesObjectPattern(pattern: string, path: string): boolean {
  const value = pattern.trim()
  if (!value) return false
  if (value === path) return true

  // Trailing `/*` keeps the historical prefix semantics: `/api/v1/*` also covers `/api/v1`.
  if (value.endsWith('/*')) {
    const prefix = value.slice(0, -1) // keep the trailing slash
    if (path === prefix.slice(0, -1) || path.startsWith(prefix)) return true
  }

  // General keyMatch2 subset: `*` matches across segments, `:name` matches exactly one segment.
  const escaped = value.replace(/[.+^${}()|[\]\\]/g, '\\$&')
  const expression = escaped.replace(/\*/g, '.*').replace(/:([A-Za-z0-9_]+)/g, '[^/]+')

  try {
    return new RegExp(`^${expression}$`).test(path)
  } catch {
    return false
  }
}

export function matchesActionPattern(pattern: string, method: string): boolean {
  const value = pattern.trim()
  if (!value) return false
  if (value === method) return true

  // Only compile patterns that look like regexes; arbitrary backend strings are treated literally.
  if (!/[|^$()[\]\\]/.test(value)) return false

  try {
    return new RegExp(value).test(method)
  } catch {
    return false
  }
}
