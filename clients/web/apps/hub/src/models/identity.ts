/** Tone names shared by chips and page models. */
export type BadgeTone = 'default' | 'accent' | 'info' | 'success' | 'warning' | 'error'

/** Certifications a viewer can hold; a single user may hold several at once. */
export type Certification = 'realname' | 'enterprise' | 'engineer'

export interface CertificationMeta {
  certification: Certification
  label: string
  tone: BadgeTone
}

/** Frontend-owned labels/tones for the three certifications; `admin` never certifies. */
export const CERTIFICATIONS: readonly CertificationMeta[] = [
  { certification: 'realname', label: '实名认证', tone: 'info' },
  { certification: 'enterprise', label: '企业认证', tone: 'accent' },
  { certification: 'engineer', label: '工程师认证', tone: 'success' },
]

const CERTIFICATION_META = new Map<Certification, CertificationMeta>(
  CERTIFICATIONS.map((meta) => [meta.certification, meta]),
)

/** Known certification label/tone, or `null` for an unknown wire value. */
export function describeCertification(certification: string): CertificationMeta | null {
  return CERTIFICATION_META.get(certification as Certification) ?? null
}

export interface RoleView {
  key: string
  label: string
  tone: BadgeTone
}

export interface PermissionActionView {
  key: string
  label: string
}

/** A human-readable permission group; raw backend patterns stay in `rawObjects` only. */
export interface PermissionGroupView {
  key: string
  label: string
  actions: PermissionActionView[]
  rawObjects: string[]
}

export type ViewerStatus = 'active' | 'inactive'

/**
 * Capabilities the current viewer has across the console modules.
 *
 * Derived by the auth BFF from the raw Casbin permissions; pages only branch on these booleans and
 * never parse policy paths themselves.
 */
export interface HubCapabilities {
  publishOrder: boolean
  applyOrder: boolean
  submitOrderLog: boolean
  viewWallet: boolean
  redeemCode: boolean
  manageAdmin: boolean
}

/**
 * Stable viewer/page model.
 *
 * Pages and components consume this shape only. Backend DTO field names, nullable quirks and raw
 * Casbin patterns are handled by the BFF mapper.
 */
export interface ViewerProfile {
  id: string
  username: string
  nickname: string
  displayName: string
  email: string | null
  initials: string
  status: ViewerStatus
  statusLabel: string
  isAdmin: boolean
  certifications: Certification[]
  roles: RoleView[]
  permissionGroups: PermissionGroupView[]
  permissionCount: number
  capabilities: HubCapabilities
}

/** Authenticated page model; tokens are deliberately not part of it. */
export interface SessionView {
  viewer: ViewerProfile
  remember: boolean
  authenticatedAt: string
}
