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

const enterpriseViewer: ViewerProfile = {
  id: '4',
  username: 'enterprise',
  displayName: '企业（演示）',
  email: 'enterprise@example.com',
  initials: '企业',
  status: 'active',
  statusLabel: '已启用',
  isAdmin: false,
  nickname: '企业（演示）',
  certifications: ['realname', 'enterprise'],
  roles: [{ key: 'enterprise', label: '企业', tone: 'accent' }],
  permissionGroups: [],
  permissionCount: 0,
  capabilities: {
    publishOrder: true,
    applyOrder: true,
    submitOrderLog: true,
    viewWallet: true,
    redeemCode: true,
    manageAdmin: false,
  },
}

const adminViewer: ViewerProfile = {
  ...enterpriseViewer,
  username: 'admin',
  displayName: '系统管理员',
  isAdmin: true,
  certifications: [],
  roles: [{ key: 'admin', label: '管理员', tone: 'accent' }],
  capabilities: { ...enterpriseViewer.capabilities, manageAdmin: true },
}

async function mountLayout(
  path = '/intro',
  currentViewer: ViewerProfile = enterpriseViewer,
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
      { path: '/fde/assigned', name: 'fde-assigned', component: EmptyView },
      { path: '/fde/applications', name: 'fde-applications', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
      { path: '/profile', name: 'profile', component: EmptyView },
      { path: '/profiles/:id', name: 'public-profile', component: EmptyView },
      { path: '/fde/orders/:id', name: 'fde-order-detail', component: EmptyView },
      { path: '/admin/users', name: 'admin-users', component: EmptyView },
      { path: '/admin/certifications', name: 'admin-certifications', component: EmptyView },
      { path: '/admin/redeem-codes', name: 'admin-redeem-codes', component: EmptyView },
      { path: '/admin/settings', name: 'admin-settings', component: EmptyView },
    ],
  })
  await router.push(path)
  await router.isReady()

  const wrapper = mount(ConsoleLayout, {
    props: { viewer: currentViewer },
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
    expect(groupLabels).toEqual(['平台', '个人', 'FDE 订单', '钱包'])

    const links = wrapper.findAll('.console-layout__nav-item')
    const labels = links.map((node) => node.text().replace(/\s+/g, ''))
    expect(labels).toEqual(
      expect.arrayContaining([
        '平台简介',
        '个人信息',
        '订单大厅实时',
        '我发布的',
        '我接到的',
        '我的申请',
        '我的钱包',
      ]),
    )
    expect(wrapper.find('[data-test="content"]').text()).toBe('内容')
  })

  it('never renders the admin group for a non-admin viewer', async () => {
    const { wrapper } = await mountLayout('/wallet')

    const groupLabels = wrapper
      .findAll('.console-layout__nav-group-label')
      .map((node) => node.text())
    expect(groupLabels).toEqual(['平台', '个人', 'FDE 订单', '钱包'])
    expect(wrapper.text()).not.toContain('管理')
    expect(wrapper.find('#console-nav-admin').exists()).toBe(false)
  })

  it('renders the admin group and resolves admin routes for admins', async () => {
    const { wrapper } = await mountLayout('/admin/redeem-codes', adminViewer)

    const groupLabels = wrapper
      .findAll('.console-layout__nav-group-label')
      .map((node) => node.text())
    expect(groupLabels).toEqual(['平台', '个人', 'FDE 订单', '钱包', '管理'])

    const links = wrapper.findAll('.console-layout__nav-item')
    expect(links.map((node) => node.text().replace(/\s+/g, ''))).toEqual(
      expect.arrayContaining(['用户', '认证审核', '兑换码', '系统设置']),
    )

    const active = wrapper.find('.console-layout__nav-item.is-active')
    expect(active.text()).toBe('兑换码')
    expect(wrapper.find('#console-nav-admin').attributes('style') ?? '').not.toContain(
      'display: none',
    )
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

  it('shows the account summary, certification badge and realtime marker', async () => {
    const { wrapper } = await mountLayout()

    expect(wrapper.text()).toContain('企业（演示）')
    expect(wrapper.text()).toContain('实时')
    expect(wrapper.text()).toContain('退出登录')
    expect(wrapper.findAll('.certification-mark .ui-chip').map((node) => node.text())).toEqual([
      '实名认证',
      '企业认证',
    ])
    expect(wrapper.find('a[href="/profiles/4"]').text()).toBe('公开主页')
  })

  it('does not render a certification badge for admin-only viewers', async () => {
    const { wrapper } = await mountLayout('/intro', adminViewer)

    expect(wrapper.find('.certification-mark').exists()).toBe(false)
  })
})
