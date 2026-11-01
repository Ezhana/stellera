import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import type { OrderRealtimeHandlers } from '@/bff/orders'
import { buildOrderView, buildViewer } from '@/bff/orders/__tests__/fixtures'
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
      getOrder: vi.fn(),
      createOrder: vi.fn(),
      claimOrder: vi.fn(),
      addWorkLog: vi.fn(),
      completeOrder: vi.fn(),
      connectRealtime: vi.fn(),
    },
  }
})

const EmptyView = { template: '<div />' }

const openOrder = buildOrderView({
  id: '1',
  title: '医疗影像数据标注与质检',
  status: 'open',
  statusLabel: '待接单',
  statusTone: 'warning',
  publisherId: '7',
  publisherName: 'Luna',
  createdAt: '2026-11-01T00:00:00.000Z',
})

const inProgressOrder = buildOrderView({
  id: '2',
  title: '金融风控模型交付',
  status: 'in_progress',
  statusLabel: '交付中',
  statusTone: 'info',
  publisherId: '99',
  publisherName: '远山银行',
  createdAt: '2026-10-30T00:00:00.000Z',
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
      { path: '/intro', name: 'intro', component: EmptyView },
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
      { path: '/fde/published', name: 'fde-published', component: EmptyView },
    ],
  })
  await router.push('/fde/hall')
  await router.isReady()

  const wrapper = mount(OrderHallPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
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
  })

  it('renders the loaded orders, stat cards and live indicator', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([openOrder, inProgressOrder]))

    const { wrapper } = await mountPage()

    expect(ordersBff.listOrders).toHaveBeenCalledTimes(1)
    expect(ordersBff.connectRealtime).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).toContain('金融风控模型交付')
    expect(wrapper.text()).toContain('¥86,000')
    expect(wrapper.text()).toContain('实时同步')
    expect(wrapper.text()).toContain('我的发布')
  })

  it('filters the loaded list client-side by status and keyword', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([openOrder, inProgressOrder]))
    const { wrapper } = await mountPage()

    const openTab = wrapper
      .findAll('.status-tabs__button')
      .find((button) => button.text() === '待接单')
    await openTab?.trigger('click')

    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).not.toContain('金融风控模型交付')

    await wrapper.find('input[type="search"]').setValue('不存在的关键词')

    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
    expect(wrapper.text()).toContain('没有符合筛选条件的订单')
  })

  it('shows an error alert and retries the request', async () => {
    vi.mocked(ordersBff.listOrders)
      .mockRejectedValueOnce(new BffError('network', '网络异常'))
      .mockResolvedValueOnce(listModel([openOrder]))

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
    expect(wrapper.text()).toContain('前往我发布的')
  })

  it('applies realtime upserts and closes the feed on unmount', async () => {
    vi.mocked(ordersBff.listOrders).mockResolvedValue(listModel([openOrder]))
    const { wrapper } = await mountPage()

    expect(handlers).not.toBeNull()

    handlers?.onEvent({
      type: 'order.updated',
      order: { ...openOrder, status: 'in_progress', statusLabel: '交付中', statusTone: 'info' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('订单更新 · 医疗影像数据标注与质检')

    handlers?.onEvent({
      type: 'order.created',
      order: buildOrderView({
        id: '3',
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
