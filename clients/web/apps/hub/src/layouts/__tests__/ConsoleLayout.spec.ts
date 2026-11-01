import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ViewerProfile } from '@/models'
import ConsoleLayout from '../ConsoleLayout.vue'

vi.mock('@/bff/auth', () => ({
  authBff: {
    logout: vi.fn(async () => undefined),
  },
}))

const EmptyView = { template: '<div />' }

const viewer: ViewerProfile = {
  id: '4',
  username: 'enterprise',
  displayName: '企业（演示）',
  email: 'enterprise@example.com',
  initials: '企业',
  status: 'active',
  statusLabel: '已启用',
  isAdmin: false,
  roles: [{ key: 'enterprise', label: '企业', tone: 'accent' }],
  permissionGroups: [],
  permissionCount: 0,
  capabilities: {
    publishOrder: true,
    claimOrder: false,
    submitOrderLog: false,
    completeOrder: true,
  },
}

async function mountLayout(
  path = '/intro',
): Promise<{ wrapper: ReturnType<typeof mount>; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: EmptyView },
      { path: '/intro', name: 'intro', component: EmptyView },
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
      { path: '/fde/published', name: 'fde-published', component: EmptyView },
    ],
  })
  await router.push(path)
  await router.isReady()

  const wrapper = mount(ConsoleLayout, {
    props: { viewer },
    global: { plugins: [pinia, router] },
    slots: { default: '<div data-test="content">内容</div>' },
  })
  return { wrapper, router }
}

describe('ConsoleLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a two-level navigation tree with group headers and child links', async () => {
    const { wrapper } = await mountLayout('/fde/hall')

    const groupLabels = wrapper
      .findAll('.console-layout__nav-group-label')
      .map((node) => node.text())
    expect(groupLabels).toEqual(['平台', 'FDE 订单'])

    const links = wrapper.findAll('.console-layout__nav-item')
    const labels = links.map((node) => node.text().replace(/\s+/g, ''))
    expect(labels).toEqual(expect.arrayContaining(['平台简介', '订单大厅实时', '我发布的']))
    expect(wrapper.find('[data-test="content"]').text()).toBe('内容')
  })

  it('marks the active child and keeps its group expanded', async () => {
    const { wrapper } = await mountLayout('/fde/hall')

    const active = wrapper.find('.console-layout__nav-item.is-active')
    expect(active.text()).toContain('订单大厅')
    expect(active.attributes('aria-current')).toBe('page')
    expect(wrapper.find('#console-nav-fde').attributes('style') ?? '').not.toContain(
      'display: none',
    )
  })

  it('collapses and re-expands a group from its toggle', async () => {
    const { wrapper } = await mountLayout('/intro')

    const fdeToggle = wrapper
      .findAll('.console-layout__nav-group-toggle')
      .find((node) => node.text().includes('FDE 订单'))
    expect(fdeToggle).toBeDefined()

    await fdeToggle!.trigger('click')
    expect(fdeToggle!.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('#console-nav-fde').attributes('style')).toContain('display: none')

    await fdeToggle!.trigger('click')
    expect(fdeToggle!.attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('#console-nav-fde').attributes('style') ?? '').not.toContain(
      'display: none',
    )
  })

  it('shows the account summary and realtime marker', async () => {
    const { wrapper } = await mountLayout()

    expect(wrapper.text()).toContain('企业（演示）')
    expect(wrapper.text()).toContain('实时')
    expect(wrapper.text()).toContain('退出登录')
  })
})
