import type { CertificationApplicationType } from '@/models'

/** Page-facing profile inputs (camelCase, already validated by the page). */
export interface UpdateMyProfileInput {
  nickname?: string
  email?: string | null
  bio?: string
  /** Comma-separated skill tags; the backend stores the raw string. */
  skills?: string
  city?: string
  contactPhone?: string
  contactWechat?: string
}

/** Payload for a certification application; only the fields for the chosen type are sent. */
export interface CertificationApplicationInput {
  type: CertificationApplicationType
  realName?: string
  idNumber?: string
  contactPhone?: string
  companyName?: string
  creditCode?: string
  contactName?: string
  skills?: string
  workYears?: number | null
  projectExperience?: string
  description?: string
}
