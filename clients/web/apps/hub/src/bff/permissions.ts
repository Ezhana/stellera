/** Minimal permission shape shared by the DTO and the viewer mapper. */
export interface PermissionLike {
  object: string
  action: string
}

/**
 * Frontend-side Casbin-compatible matcher for the subset the backend policies use:
 * `keyMatch2`-style path patterns and `regexMatch`-style action patterns.
 *
 * The BFF uses this to derive module access from backend permissions; pages never parse policies.
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

  if (value.endsWith('/*')) {
    const prefix = value.slice(0, -1) // keep the trailing slash
    return path === prefix.slice(0, -1) || path.startsWith(prefix)
  }

  if (value.endsWith('*')) {
    return path.startsWith(value.slice(0, -1))
  }

  return false
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
