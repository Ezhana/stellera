import type { BadgeTone, PermissionGroupView, ViewerProfile } from './identity'
import type { ModuleAccess, ModuleDefinition } from './modules'

/** A module card as rendered by the console page. */
export interface ModuleView extends Omit<ModuleDefinition, 'probePath'> {
  access: ModuleAccess
  accessLabel: string
  accessTone: BadgeTone
  availability: 'planned' | 'available'
  availabilityLabel: string
}

export interface ConsoleSummary {
  roleCount: number
  permissionCount: number
  readableModuleCount: number
  writableModuleCount: number
}

/** Stable page model for `/console`; assembled by the console BFF. */
export interface ConsolePageModel {
  viewer: ViewerProfile
  modules: ModuleView[]
  permissionGroups: PermissionGroupView[]
  summary: ConsoleSummary
}
