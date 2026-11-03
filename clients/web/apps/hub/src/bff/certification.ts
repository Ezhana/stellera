import type { Certification } from '@/models'

/** Wire values are plain strings; anything unknown degrades to "not certified". */
export function normalizeCertification(value: string | null | undefined): Certification {
  return value === 'enterprise' || value === 'engineer' ? value : null
}

/** Viewer certification is derived from roles; admin never implies a certification. */
export function certificationFromRoles(roleKeys: readonly string[]): Certification {
  if (roleKeys.includes('enterprise')) return 'enterprise'
  if (roleKeys.includes('engineer')) return 'engineer'
  return null
}
