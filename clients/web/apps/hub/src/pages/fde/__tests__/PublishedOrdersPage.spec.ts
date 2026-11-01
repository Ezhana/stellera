import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import type { OrderRealtimeHandlers } from '@/bff/orders'
import { buildOrderView, buildViewer } from '@/bff/orders/__tests__/fixtures'
import type { FdeOrderView, OrderListModel, ViewerProfile } from '@/models'
import PublishedOrdersPage from '@/pages/fde/PublishedOrdersPage.vue'
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

async function mountPage(viewer: ViewerProfile = buildViewer()): Promise<MountResult> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.$patch({
    session: { viewer, remember: false, authenticatedAt: '2026-11-01T00:00:00.000Z' },
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
  await router.push('/fde/published')
  await router.isReady()

  const wrapper = mount(PublishedOrdersPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

async function openForm(wrapper: VueWrapper): Promise<void> {
  const toggle = wrapper.findAll('button').find((button) => button.text() === '发布需求')
  await toggle?.trigger('click')
  await flushPromises()
}

async function fillForm(
  wrapper: VueWrapper,
  values: {
    title: string
    industry: string
    deliveryDays: string
    priceYuan: string
    description: string
  },
): Promise<void> {
  await wrapper.find('input[name="title"]').setValue(values.title)
  await wrapper.find('#publish-industry').setValue(values.industry)
  await wrapper.find('input[name="deliveryDays"]').setValue(values.deliveryDays)
  await wrapper.find('input[name="priceYuan"]').setValue(values.priceYuan)
  await wrapper.find('textarea').setValue(values.description)
}

describe('PublishedOrdersPage', () => {
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

  it('lists my orders and opens the inline publish form for permitted users', async () => {
    vi.mocked(ordersBff.listMyOrders).mockResolvedValue(listModel([myOrder]))
    const { wrapper } = await mountPage()

    expect(ordersBff.listMyOrders).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).toContain('我的订单')

    await openForm(wrapper)

    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.text()).toContain('发布新需求')
  })

  it('validates the inline form with Chinese messages before calling the BFF', async () => {
    vi.mocked(ordersBff.listMyOrders).mockResolvedValue(listModel([myOrder]))
    const { wrapper } = await mountPage()
    await openForm(wrapper)

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入任务标题')
    expect(wrapper.text()).toContain('请选择行业')
    expect(wrapper.text()).toContain('请输入交付周期')
    expect(wrapper.text()).toContain('请输入预算金额')
    expect(wrapper.text()).toContain('请填写需求描述')
    expect(ordersBff.createOrder).not.toHaveBeenCalled()

    await fillForm(wrapper, {
      title: '新能源调度算法交付',
      industry: '能源电力',
      deliveryDays: '0',
      priceYuan: '0',
      description: '交付一套调度算法与验收报告。',
    })
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('交付周期需在 1–365 天之间')
    expect(wrapper.text()).toContain('预算金额必须大于 0')
    expect(ordersBff.createOrder).not.toHaveBeenCalled()
  })

  it('publishes a demand, converts yuan to cents and prepends the new order', async () => {
    vi.mocked(ordersBff.listMyOrders).mockResolvedValue(listModel([myOrder]))
    vi.mocked(ordersBff.createOrder).mockResolvedValue(
      buildOrderView({
        id: '12',
        title: '新能源调度算法交付',
        industry: '能源电力',
        publisherId: '7',
        publisherName: 'Luna',
        createdAt: '2026-11-02T00:00:00.000Z',
      }),
    )

    const { wrapper } = await mountPage()
    await openForm(wrapper)
    await fillForm(wrapper, {
      title: '新能源调度算法交付',
      industry: '能源电力',
      deliveryDays: '14',
      priceYuan: '860.50',
      description: '交付一套调度算法与验收报告。',
    })
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(ordersBff.createOrder).toHaveBeenCalledWith({
      title: '新能源调度算法交付',
      industry: '能源电力',
      description: '交付一套调度算法与验收报告。',
      deliveryDays: 14,
      priceCents: 86_050,
    })
    expect(wrapper.text()).toContain('需求已发布并进入订单大厅，资金已进入平台托管。')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('shows an info alert and hides the form when publishing is not permitted', async () => {
    vi.mocked(ordersBff.listMyOrders).mockResolvedValue(listModel([myOrder]))
    const { wrapper } = await mountPage(
      buildViewer({
        capabilities: {
          publishOrder: false,
          claimOrder: false,
          submitOrderLog: false,
          completeOrder: false,
        },
      }),
    )

    expect(wrapper.text()).toContain('无发布权限')
    expect(wrapper.find('form').exists()).toBe(false)
    const toggle = wrapper.findAll('button').find((button) => button.text() === '发布需求')
    expect(toggle).toBeUndefined()
  })

  it('only applies realtime events for tracked or self-published orders', async () => {
    vi.mocked(ordersBff.listMyOrders).mockResolvedValue(listModel([myOrder]))
    const { wrapper } = await mountPage()

    expect(handlers).not.toBeNull()

    handlers?.onEvent({
      type: 'order.created',
      order: buildOrderView({ id: '9', title: '其他企业的需求', publisherId: '99' }),
    })
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('其他企业的需求')

    handlers?.onEvent({
      type: 'order.updated',
      order: { ...myOrder, status: 'completed', statusLabel: '已完成', statusTone: 'success' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('订单更新 · 医疗影像数据标注与质检')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('已完成')
  })

  it('shows a retry state when loading my orders fails', async () => {
    vi.mocked(ordersBff.listMyOrders)
      .mockRejectedValueOnce(new BffError('server', '服务异常'))
      .mockResolvedValueOnce(listModel([myOrder]))

    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('订单服务暂时不可用')

    const retry = wrapper.findAll('button').find((button) => button.text() === '重试')
    await retry?.trigger('click')
    await flushPromises()

    expect(ordersBff.listMyOrders).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
  })
})
