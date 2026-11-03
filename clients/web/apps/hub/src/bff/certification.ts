import type { Certification } from '@/models'

/** Canonical display order across badges, lists and forms. */
const CERTIFICATION_ORDER: readonly Certification[] = ['realname', 'enterprise', 'engineer']

/** Normalize a wire list: drop unknown values, dedupe and keep the canonical order. */
export function normalizeCertifications(
  values: readonly string[] | null | undefined,
): Certification[] {
  const present = new Set<string>(values ?? [])
  return CERTIFICATION_ORDER.filter((certification) => present.has(certification))
}

/** Fallback for payloads that only carry roles: each certification maps to a role. */
export function certificationsFromRoles(roleKeys: readonly string[]): Certification[] {
  return CERTIFICATION_ORDER.filter((certification) => roleKeys.includes(certification))
}
