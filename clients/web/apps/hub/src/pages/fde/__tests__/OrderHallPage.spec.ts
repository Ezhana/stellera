import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import type { OrderRealtimeHandlers } from '@/bff/orders'
import {
  buildApplicationListModel,
  buildApplicationView,
  buildOrderView,
  buildViewer,
} from '@/bff/orders/__tests__/fixtures'
import type { FdeOrderView, OrderListModel } from '@/models'
import OrderHallPage from '@/pages/fde/OrderHallPage.vue'
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

const myOrder = buildOrderView({
  id: '1',
  title: '医疗影像数据标注与质检',
  status: 'open',
  statusLabel: '待接单',
  statusTone: 'warning',
  publisherId: '7',
  publisherName: 'Luna',
  createdAt: '2026-11-01T00:00:00.000Z',
})

const openOrder = buildOrderView({
  id: '2',
  title: '金融风控模型交付',
  status: 'open',
  statusLabel: '待接单',
  statusTone: 'warning',
  publisherId: '99',
  publisherName: '远山银行',
  createdAt: '2026-10-30T00:00:00.000Z',
})

const inProgressOrder = buildOrderView({
  id: '3',
  title: '新能源调度算法交付',
  status: 'in_progress',
  statusLabel: '交付中',
  statusTone: 'info',
  publisherId: '99',
  publisherName: '远山银行',
  createdAt: '2026-10-29T00:00:00.000Z',
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

interface MountResult {
  wrapper: VueWrapper
  router: Router
}

async function mountPage(): Promise<MountResult> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.$patch({
    session: {
      viewer: buildViewer(),
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
      { path: '/fde/publish', name: 'fde-publish', component: EmptyView },
      { path: '/fde/assigned', name: 'fde-assigned', component: EmptyView },
      { path: '/fde/applications', name: 'fde-applications', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
    ],
  })
  await router.push('/fde/hall')
  await router.isReady()

  const wrapper = mount(OrderHallPage, {
    global: { plugins: [pinia, router], stubs: { teleport: true } },
  })
  await flushPromises()
  return { wrapper, router }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

describe('OrderHallPage', () => {
  let handlers: OrderRealtimeHandlers | null
  let closeSpy: Mock<() => void>

  beforeEach(() => {
    handlers = null
    closeSpy = vi.fn<() => void>()
    vi.mocked(ordersBff.connectRealtime).mockImplementation((nextHandlers) => {
      handlers = nextHandlers
      nextHandlers.onStateChange('live')
      return { close: closeSpy }
    })
    vi.mocked(ordersBff.listMyApplications).mockResolvedValue(buildApplicationListModel([]))
  })

  it('renders the loaded orders, stat cards and live indicator', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([myOrder, inProgressOrder]))

    const { wrapper } = await mountPage()

    expect(ordersBff.listOrders).toHaveBeenCalledTimes(1)
    expect(ordersBff.connectRealtime).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).toContain('新能源调度算法交付')
    expect(wrapper.text()).toContain('¥86,000')
    expect(wrapper.text()).toContain('实时同步')
    expect(wrapper.text()).toContain('我的发布')
    expect(wrapper.text()).toContain('企业认证')
  })

  it('filters the loaded list client-side by status and keyword', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([myOrder, inProgressOrder]))
    const { wrapper } = await mountPage()

    const openTab = wrapper
      .findAll('.status-tabs__button')
      .find((button) => button.text() === '待接单')
    await openTab?.trigger('click')

    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).not.toContain('新能源调度算法交付')

    await wrapper.find('input[type="search"]').setValue('不存在的关键词')

    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
    expect(wrapper.text()).toContain('没有符合筛选条件的订单')
  })

  it('shows an error alert and retries the request', async () => {
    vi.mocked(ordersBff.listOrders)
      .mockRejectedValueOnce(new BffError('network', '网络异常'))
      .mockResolvedValueOnce(listModel([myOrder]))

    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('无法连接到服务')

    const retry = wrapper.findAll('button').find((button) => button.text() === '重试')
    await retry?.trigger('click')
    await flushPromises()

    expect(ordersBff.listOrders).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
  })

  it('shows an empty state when no orders are available', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([]))

    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('暂无可接订单')
    const link = wrapper.findAll('a').find((node) => node.text() === '发布需求')
    expect(link?.attributes('href')).toBe('/fde/publish')
  })

  it('opens the apply modal and submits an accept application with a note', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([myOrder, openOrder]))
    vi.mocked(ordersBff.applyForOrder).mockResolvedValue(buildApplicationView())

    const { wrapper } = await mountPage()

    const applyButtons = wrapper.findAll('button').filter((button) => button.text() === '申请接单')
    expect(applyButtons).toHaveLength(1)

    await applyButtons[0]!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('申请接单后需发布者审批')
    await wrapper.find('textarea[name="apply-message"]').setValue('有医疗行业交付经验')
    await findButton(wrapper, '确认申请')?.trigger('click')
    await flushPromises()

    expect(ordersBff.applyForOrder).toHaveBeenCalledWith('2', 'accept', '有医疗行业交付经验')
    expect(wrapper.text()).toContain('申请已提交，等待发布者审批')
    expect(wrapper.find('textarea[name="apply-message"]').exists()).toBe(false)
    expect(ordersBff.listOrders).toHaveBeenCalledTimes(2)
  })

  it('closes the apply modal without calling the BFF when cancelled', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([openOrder]))

    const { wrapper } = await mountPage()
    await findButton(wrapper, '申请接单')?.trigger('click')
    await flushPromises()

    await findButton(wrapper, '取消')?.trigger('click')
    await flushPromises()

    expect(ordersBff.applyForOrder).not.toHaveBeenCalled()
    expect(wrapper.find('textarea[name="apply-message"]').exists()).toBe(false)
  })

  it('shows a conflict message inside the apply modal when the application is rejected', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([openOrder]))
    vi.mocked(ordersBff.applyForOrder).mockRejectedValue(
      new BffError('conflict', '已有待审批的接单申请。'),
    )

    const { wrapper } = await mountPage()
    await findButton(wrapper, '申请接单')?.trigger('click')
    await flushPromises()
    await findButton(wrapper, '确认申请')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已有待审批的接单申请。')
    expect(wrapper.find('textarea[name="apply-message"]').exists()).toBe(true)
  })

  it('marks orders with a pending accept application as 已申请', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(
      listModel([myOrder, openOrder, inProgressOrder]),
    )
    vi.mocked(ordersBff.listMyApplications).mockResolvedValue(
      buildApplicationListModel([
        buildApplicationView({
          id: '9',
          type: 'accept',
          status: 'pending',
          order: openOrder,
        }),
      ]),
    )

    const { wrapper } = await mountPage()

    const disabled = wrapper.findAll('button').find((button) => button.text() === '已申请')
    expect(disabled?.attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('button').some((button) => button.text() === '申请接单')).toBe(false)
  })

  it('applies realtime upserts and closes the feed on unmount', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([myOrder]))
    const { wrapper } = await mountPage()

    expect(handlers).not.toBeNull()

    handlers?.onEvent({
      type: 'order.updated',
      order: { ...myOrder, status: 'in_progress', statusLabel: '交付中', statusTone: 'info' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('订单更新 · 医疗影像数据标注与质检')

    handlers?.onEvent({
      type: 'order.created',
      order: buildOrderView({
        id: '4',
        title: '新能源调度算法交付',
        createdAt: '2026-11-02T00:00:00.000Z',
      }),
    })
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('新能源调度算法交付')

    wrapper.unmount()
    expect(closeSpy).toHaveBeenCalledTimes(1)
  })
})
