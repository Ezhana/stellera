import { beforeEach, describe, expect, it, vi } from 'vitest'

const authState = vi.hoisted(() => ({
  isAuthenticated: true,
  viewer: { isAdmin: false } as { isAdmin: boolean } | null,
  bootstrap: vi.fn(async () => undefined),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

const { router } = await import('@/router')

async function go(path: string): Promise<{ name: string | symbol | undefined; fullPath: string }> {
  await router.push(path)
  await router.isReady()
  return { name: router.currentRoute.value.name, fullPath: router.currentRoute.value.fullPath }
}

describe('router guards', () => {
  beforeEach(() => {
    authState.isAuthenticated = true
    authState.viewer = { isAdmin: false }
    authState.bootstrap.mockClear()
  })

  it('lets an authenticated viewer open the wallet page', async () => {
    expect(await go('/wallet')).toMatchObject({ name: 'wallet' })
    expect(authState.bootstrap).toHaveBeenCalled()
  })

  it('lets an authenticated viewer open the new FDE order pages', async () => {
    expect(await go('/fde/hall')).toMatchObject({ name: 'fde-hall' })
    expect(await go('/fde/published')).toMatchObject({ name: 'fde-published' })
    expect(await go('/fde/publish')).toMatchObject({ name: 'fde-publish' })
    expect(await go('/fde/assigned')).toMatchObject({ name: 'fde-assigned' })
    expect(await go('/fde/applications')).toMatchObject({ name: 'fde-applications' })
  })

  it('lets an authenticated viewer open the profile and order detail pages', async () => {
    expect(await go('/profile')).toMatchObject({ name: 'profile' })
    expect(await go('/profiles/5')).toMatchObject({ name: 'public-profile' })
    expect(await go('/fde/orders/42')).toMatchObject({ name: 'fde-order-detail' })
  })

  it('redirects non-admins away from admin routes to the intro page', async () => {
    expect(await go('/admin/users')).toMatchObject({ name: 'intro' })
    expect(await go('/admin/certifications')).toMatchObject({ name: 'intro' })
    expect(await go('/admin/redeem-codes')).toMatchObject({ name: 'intro' })
    expect(await go('/admin/settings')).toMatchObject({ name: 'intro' })
  })

  it('lets an admin open every admin route', async () => {
    authState.viewer = { isAdmin: true }

    expect(await go('/admin/users')).toMatchObject({ name: 'admin-users' })
    expect(await go('/admin/certifications')).toMatchObject({ name: 'admin-certifications' })
    expect(await go('/admin/redeem-codes')).toMatchObject({ name: 'admin-redeem-codes' })
    expect(await go('/admin/settings')).toMatchObject({ name: 'admin-settings' })
  })

  it('sends anonymous viewers to the login page with a redirect query', async () => {
    authState.isAuthenticated = false
    authState.viewer = null

    const route = await go('/wallet')
    expect(route.name).toBe('login')
    expect(route.fullPath).toContain('redirect=/wallet')
  })

  it('sends anonymous viewers to the login page from assigned orders too', async () => {
    authState.isAuthenticated = false
    authState.viewer = null

    const route = await go('/fde/assigned')
    expect(route.name).toBe('login')
    expect(route.fullPath).toContain('redirect=/fde/assigned')
  })

  it('sends authenticated viewers away from the register page', async () => {
    expect(await go('/register')).toMatchObject({ name: 'intro' })
  })

  it('opens the register page for anonymous viewers', async () => {
    authState.isAuthenticated = false
    authState.viewer = null

    expect(await go('/register')).toMatchObject({ name: 'register' })
  })

  it('sends authenticated viewers away from the login page', async () => {
    expect(await go('/login')).toMatchObject({ name: 'intro' })
  })
})
