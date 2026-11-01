import type {
  BadgeTone,
  ConsolePageModel,
  ConsoleSummary,
  ModuleAccess,
  ModuleView,
  ViewerProfile,
} from '@/models'
import { MODULE_CATALOG } from '@/models/modules'

const ACCESS_COPY: Readonly<Record<ModuleAccess, { label: string; tone: BadgeTone }>> = {
  write: { label: '可写', tone: 'success' },
  read: { label: '只读', tone: 'info' },
  none: { label: '无权限', tone: 'default' },
}

/**
 * Console page BFF.
 *
 * Joins backend-derived viewer capabilities with the frontend-owned module catalog and produces
 * the stable model consumed by `ConsolePage`. No raw permission strings or backend field names
 * reach the page.
 */
export function buildConsolePageModel(viewer: ViewerProfile): ConsolePageModel {
  const modules: ModuleView[] = MODULE_CATALOG.map((definition) => {
    const access = viewer.moduleAccess[definition.key]
    const copy = ACCESS_COPY[access]
    return {
      key: definition.key,
      code: definition.code,
      label: definition.label,
      description: definition.description,
      icon: definition.icon,
      access,
      accessLabel: copy.label,
      accessTone: copy.tone,
      availability: 'planned',
      availabilityLabel: '即将上线',
    }
  })

  const summary: ConsoleSummary = {
    roleCount: viewer.roles.length,
    permissionCount: viewer.permissionCount,
    readableModuleCount: modules.filter((module) => module.access !== 'none').length,
    writableModuleCount: modules.filter((module) => module.access === 'write').length,
  }

  return {
    viewer,
    modules,
    permissionGroups: viewer.permissionGroups,
    summary,
  }
}
