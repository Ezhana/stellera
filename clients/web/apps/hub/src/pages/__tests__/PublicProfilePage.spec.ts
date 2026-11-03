import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BffError } from '@/bff/errors'
import { buildViewer } from '@/bff/orders/__tests__/fixtures'
import { profileBff } from '@/bff/profile'
import { buildPublicProfileView } from '@/bff/profile/__tests__/fixtures'
import PublicProfilePage from '@/pages/PublicProfilePage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/profile', () => ({
  profileBff: { getPublicProfile: vi.fn() },
}))

const EmptyView = { template: '<div />' }

async function mountPage(id = '5'): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.$patch({
    session: {
      viewer: buildViewer({ id: '2', username: 'member', displayName: '会员（演示）' }),
      remember: false,
      authenticatedAt: '2026-11-01T00:00:00.000Z',
    },
    status: 'authenticated',
  })

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: EmptyView },
      { path: '/intro', name: 'intro', component: EmptyView },
      { path: '/profile', name: 'profile', component: EmptyView },
      { path: '/profiles/:id', name: 'public-profile', component: EmptyView },
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
      { path: '/fde/published', name: 'fde-published', component: EmptyView },
      { path: '/fde/assigned', name: 'fde-assigned', component: EmptyView },
      { path: '/fde/applications', name: 'fde-applications', component: EmptyView },
      { path: '/fde/orders/:id', name: 'fde-order-detail', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
    ],
  })
  await router.push(`/profiles/${id}`)
  await router.isReady()

  const wrapper = mount(PublicProfilePage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('PublicProfilePage', () => {
  beforeEach(() => {
    vi.mocked(profileBff.getPublicProfile).mockResolvedValue(buildPublicProfileView())
  })

  it('loads the public profile by route id and renders public fields only', async () => {
    const { wrapper } = await mountPage('5')

    expect(profileBff.getPublicProfile).toHaveBeenCalledWith('5')
    expect(wrapper.text()).toContain('工程师阿远')
    expect(wrapper.text()).toContain('实名认证')
    expect(wrapper.text()).toContain('工程师认证')
    expect(wrapper.text()).toContain('曾交付多个医疗影像项目。')
    expect(wrapper.text()).toContain('Python')
    expect(wrapper.text()).toContain('杭州')
    expect(wrapper.text()).toContain('加入于')

    expect(wrapper.text()).not.toContain('member@example.com')
    expect(wrapper.text()).not.toContain('13800000000')
    expect(wrapper.text()).not.toContain('张三')
    expect(wrapper.find('input').exists()).toBe(false)
  })

  it('renders cooperation stats and record links to the order detail', async () => {
    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('完成单数')
    expect(wrapper.text()).toContain('累计金额')
    const link = wrapper.find('a.public-profile__record')
    expect(link.attributes('href')).toBe('/fde/orders/42')
    expect(link.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).toContain('接单工程师')
  })

  it('hides the edit link for someone else and shows it for my own profile', async () => {
    vi.mocked(profileBff.getPublicProfile).mockResolvedValue(
      buildPublicProfileView({ id: '2', nickname: '会员（演示）' }),
    )
    const { wrapper } = await mountPage('2')

    const editLink = wrapper.findAll('a').find((node) => node.text() === '编辑个人信息')
    expect(editLink?.attributes('href')).toBe('/profile')
  })

  it('shows a not-found message and retries', async () => {
    vi.mocked(profileBff.getPublicProfile)
      .mockRejectedValueOnce(new BffError('not-found', 'missing'))
      .mockResolvedValueOnce(buildPublicProfileView())

    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('该用户不存在')
    const retry = wrapper.findAll('button').find((button) => button.text() === '重试')
    await retry?.trigger('click')
    await flushPromises()

    expect(profileBff.getPublicProfile).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('工程师阿远')
  })
})
