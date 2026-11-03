/** Tone names shared by chips and page models. */
export type BadgeTone = 'default' | 'accent' | 'info' | 'success' | 'warning' | 'error'

/** Certification derived from the viewer's enterprise/engineer roles. */
export type Certification = 'enterprise' | 'engineer' | null

export interface CertificationMeta {
  certification: Exclude<Certification, null>
  label: string
  tone: BadgeTone
}

/** Frontend-owned labels/tones for the two certifications; `admin` never certifies. */
export const CERTIFICATIONS: readonly CertificationMeta[] = [
  { certification: 'enterprise', label: '企业认证', tone: 'accent' },
  { certification: 'engineer', label: '工程师认证', tone: 'success' },
]

const CERTIFICATION_META = new Map<Exclude<Certification, null>, CertificationMeta>(
  CERTIFICATIONS.map((meta) => [meta.certification, meta]),
)

/** Known certification label/tone, or `null` when the viewer is not certified. */
export function describeCertification(certification: Certification): CertificationMeta | null {
  if (!certification) return null
  return CERTIFICATION_META.get(certification) ?? null
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
  displayName: string
  email: string | null
  initials: string
  status: ViewerStatus
  statusLabel: string
  isAdmin: boolean
  certification: Certification
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
