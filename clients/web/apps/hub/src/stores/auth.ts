import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { authBff } from '@/bff/auth'
import type { LoginCredentials, RegisterCredentials } from '@/bff/auth'
import type { PermissionGroupView, RoleView, SessionView, ViewerProfile } from '@/models'

export type AuthStatus = 'idle' | 'loading' | 'authenticated' | 'anonymous'

/**
 * Thin session state for the hub console.
 *
 * The BFF owns transport, token persistence, refresh and DTO→page-model mapping. The store only
 * holds the resulting `SessionView`, so pages/components never see backend fields or tokens.
 */
export const useAuthStore = defineStore('auth', () => {
  const session = ref<SessionView | null>(null)
  const status = ref<AuthStatus>('idle')
  const bootstrapped = ref(false)

  const viewer = computed<ViewerProfile | null>(() => session.value?.viewer ?? null)
  const isAuthenticated = computed(() => Boolean(session.value))
  const roles = computed<RoleView[]>(() => viewer.value?.roles ?? [])
  const permissionGroups = computed<PermissionGroupView[]>(
    () => viewer.value?.permissionGroups ?? [],
  )

  function setSession(next: SessionView | null): void {
    session.value = next
    status.value = next ? 'authenticated' : 'anonymous'
  }

  async function login(credentials: LoginCredentials, remember: boolean): Promise<SessionView> {
    status.value = 'loading'
    try {
      const next = await authBff.login(credentials, remember)
      setSession(next)
      bootstrapped.value = true
      return next
    } catch (error) {
      status.value = session.value ? 'authenticated' : 'anonymous'
      throw error
    }
  }

  /** Registration mirrors login: the backend returns a full session for the new member. */
  async function register(
    credentials: RegisterCredentials,
    remember: boolean,
  ): Promise<SessionView> {
    status.value = 'loading'
    try {
      const next = await authBff.register(credentials, remember)
      setSession(next)
      bootstrapped.value = true
      return next
    } catch (error) {
      status.value = session.value ? 'authenticated' : 'anonymous'
      throw error
    }
  }

  async function runBootstrap(): Promise<void> {
    try {
      setSession(await authBff.restore())
    } catch {
      setSession(null)
    }
  }

  let bootstrapPromise: Promise<void> | null = null

  /** Restore the session once. Concurrent navigation guards share the same promise. */
  function bootstrap(): Promise<void> {
    if (bootstrapped.value) return Promise.resolve()
    if (!bootstrapPromise) {
      bootstrapPromise = runBootstrap().finally(() => {
        bootstrapped.value = true
        bootstrapPromise = null
      })
    }
    return bootstrapPromise
  }

  async function logout(): Promise<void> {
    try {
      await authBff.logout()
    } finally {
      setSession(null)
    }
  }

  return {
    session,
    viewer,
    status,
    bootstrapped,
    isAuthenticated,
    roles,
    permissionGroups,
    login,
    register,
    bootstrap,
    logout,
  }
})
