import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import {
  buildApplicationListModel,
  buildApplicationView,
  buildOrderView,
  buildViewer,
} from '@/bff/orders/__tests__/fixtures'
import type { FdeOrderView, OrderListModel } from '@/models'
import AssignedOrdersPage from '@/pages/fde/AssignedOrdersPage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/orders', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/bff/orders')>()
  return {
    ...actual,
    ordersBff: {
      listOrders: vi.fn(),
      listMyOrders: vi.fn(),
      listAssignedOrders: vi.fn(),
      getOrder: vi.fn(),
      createOrder: vi.fn(),
      cancelOrder: vi.fn(),
      addWorkLog: vi.fn(),
      applyForOrder: vi.fn(),
      listMyApplications: vi.fn(),
      listReceivedApplications: vi.fn(),
      approveApplication: vi.fn(),
      rejectApplication: vi.fn(),
      withdrawApplication: vi.fn(),
      connectRealtime: vi.fn(),
    },
  }
})

const EmptyView = { template: '<div />' }

const inProgressOrder = buildOrderView({
  id: '5',
  title: '医疗影像数据标注与质检',
  status: 'in_progress',
  statusLabel: '交付中',
  statusTone: 'info',
  publisherId: '7',
  publisherName: 'Luna',
  engineerId: '9',
  engineerName: '工程师阿远',
  engineerCertifications: ['realname', 'engineer'],
  createdAt: '2026-11-01T00:00:00.000Z',
})

const completedOrder = buildOrderView({
  id: '6',
  title: '金融风控模型交付',
  status: 'completed',
  statusLabel: '已完成',
  statusTone: 'success',
  publisherId: '7',
  publisherName: 'Luna',
  engineerId: '9',
  engineerName: '工程师阿远',
  createdAt: '2026-10-01T00:00:00.000Z',
})

function listModel(orders: FdeOrderView[]): OrderListModel {
  return {
    orders,
    total: orders.length,
    stats: {
      total: orders.length,
      openCount: 0,
      inProgressCount: 0,
      completedCount: 0,
      escrowHeldCents: 0,
      escrowHeldLabel: '¥0',
    },
    fetchedAt: '2026-11-01T00:00:00.000Z',
  }
}

async function mountPage(): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.$patch({
    session: {
      viewer: buildViewer({
        id: '9',
        username: 'engineer',
        displayName: '工程师阿远',
        certifications: ['realname', 'engineer'],
        roles: [{ key: 'engineer', label: '工程师', tone: 'success' }],
      }),
      remember: false,
      authenticatedAt: '2026-11-01T00:00:00.000Z',
    },
    status: 'authenticated',
  })

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: EmptyView },
      { path: '/profile', name: 'profile', component: EmptyView },
      { path: '/profiles/:id', name: 'public-profile', component: EmptyView },
      { path: '/fde/orders/:id', name: 'fde-order-detail', component: EmptyView },
      { path: '/intro', name: 'intro', component: EmptyView },
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
      { path: '/fde/published', name: 'fde-published', component: EmptyView },
      { path: '/fde/assigned', name: 'fde-assigned', component: EmptyView },
      { path: '/fde/applications', name: 'fde-applications', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
    ],
  })
  await router.push('/fde/assigned')
  await router.isReady()

  const wrapper = mount(AssignedOrdersPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

describe('AssignedOrdersPage', () => {
  beforeEach(() => {
    vi.mocked(ordersBff.listAssignedOrders).mockResolvedValue(listModel([inProgressOrder]))
    vi.mocked(ordersBff.listMyApplications).mockResolvedValue(buildApplicationListModel([]))
    vi.mocked(ordersBff.addWorkLog).mockResolvedValue({
      id: '11',
      authorName: '工程师阿远',
      content: '完成首批标注',
      workedHours: 6,
      createdAtLabel: '今天 10:30',
    })
    vi.mocked(ordersBff.applyForOrder).mockResolvedValue(
      buildApplicationView({ type: 'delivery', order: inProgressOrder }),
    )
  })

  it('renders assigned orders with the in-progress and read-only actions', async () => {
    vi.mocked(ordersBff.listAssignedOrders).mockResolvedValue(
      listModel([inProgressOrder, completedOrder]),
    )
    const { wrapper } = await mountPage()

    expect(ordersBff.listAssignedOrders).toHaveBeenCalledWith(undefined)
    expect(ordersBff.listMyApplications).toHaveBeenCalledWith({
      type: 'delivery',
      status: 'pending',
      pageSize: 100,
    })
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).toContain('金融风控模型交付')
    expect(findButton(wrapper, '提交工作日志')).toBeDefined()
    expect(findButton(wrapper, '申请交付')).toBeDefined()
    // 已完成订单只读：只展示一条提交日志按钮。
    expect(wrapper.findAll('button').filter((button) => button.text() === '申请交付')).toHaveLength(
      1,
    )
  })

  it('reloads assigned orders with the selected status filter', async () => {
    const { wrapper } = await mountPage()

    const inProgressTab = wrapper
      .findAll('.status-tabs__button')
      .find((button) => button.text() === '交付中')
    await inProgressTab?.trigger('click')
    await flushPromises()

    expect(ordersBff.listAssignedOrders).toHaveBeenLastCalledWith({ status: 'in_progress' })
  })

  it('submits a work log with optional hours and refreshes the list', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '提交工作日志')?.trigger('click')
    await flushPromises()

    await wrapper
      .find('textarea[name="work-log-content"]')
      .setValue('完成首批 200 例标注，已提交质检。')
    await wrapper.find('input[name="work-log-hours"]').setValue('6')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(ordersBff.addWorkLog).toHaveBeenCalledWith('5', {
      content: '完成首批 200 例标注，已提交质检。',
      workedHours: 6,
    })
    expect(wrapper.text()).toContain('工作日志已提交。')
    expect(ordersBff.listAssignedOrders).toHaveBeenCalledTimes(2)
    expect(wrapper.find('textarea[name="work-log-content"]').exists()).toBe(false)
  })

  it('validates the work log content and hours locally', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '提交工作日志')?.trigger('click')
    await flushPromises()
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入工作日志内容')
    expect(ordersBff.addWorkLog).not.toHaveBeenCalled()

    await wrapper.find('textarea[name="work-log-content"]').setValue('完成首批标注')
    await wrapper.find('input[name="work-log-hours"]').setValue('30')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('工时需在 0–24 小时之间')
    expect(ordersBff.addWorkLog).not.toHaveBeenCalled()
  })

  it('applies for delivery with an optional message and refreshes applications', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '申请交付')?.trigger('click')
    await flushPromises()
    await wrapper.find('textarea[name="delivery-message"]').setValue('已按验收标准交付全部成果。')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(ordersBff.applyForOrder).toHaveBeenCalledWith(
      '5',
      'delivery',
      '已按验收标准交付全部成果。',
    )
    expect(wrapper.text()).toContain('交付申请已提交，等待发布者审批。')
    expect(ordersBff.listAssignedOrders).toHaveBeenCalledTimes(2)
    expect(ordersBff.listMyApplications).toHaveBeenCalledTimes(2)
  })

  it('disables the delivery action when a pending delivery application exists', async () => {
    vi.mocked(ordersBff.listMyApplications).mockResolvedValue(
      buildApplicationListModel([
        buildApplicationView({ type: 'delivery', status: 'pending', order: inProgressOrder }),
      ]),
    )

    const { wrapper } = await mountPage()

    const pending = wrapper.findAll('button').find((button) => button.text() === '交付申请待审批')
    expect(pending?.attributes('disabled')).toBeDefined()
    expect(findButton(wrapper, '申请交付')).toBeUndefined()
  })

  it('shows an empty state when no orders are assigned', async () => {
    vi.mocked(ordersBff.listAssignedOrders).mockResolvedValue(listModel([]))
    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('暂时没有接到的订单')
  })

  it('shows a retry state when loading fails', async () => {
    vi.mocked(ordersBff.listAssignedOrders)
      .mockRejectedValueOnce(new BffError('server', '服务异常'))
      .mockResolvedValueOnce(listModel([inProgressOrder]))

    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('订单服务暂时不可用')
    await findButton(wrapper, '重试')?.trigger('click')
    await flushPromises()

    expect(ordersBff.listAssignedOrders).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
  })
})
