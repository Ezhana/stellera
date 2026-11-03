import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import { buildOrderView, buildViewer } from '@/bff/orders/__tests__/fixtures'
import PublishOrderPage from '@/pages/fde/PublishOrderPage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/orders', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/bff/orders')>()
  return {
    ...actual,
    ordersBff: {
      createOrder: vi.fn(),
    },
  }
})

const EmptyView = { template: '<div />' }

async function mountPage(): Promise<{ wrapper: VueWrapper; router: Router }> {
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
      { path: '/profile', name: 'profile', component: EmptyView },
      { path: '/profiles/:id', name: 'public-profile', component: EmptyView },
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
      { path: '/fde/published', name: 'fde-published', component: EmptyView },
      { path: '/fde/publish', name: 'fde-publish', component: EmptyView },
      { path: '/fde/orders/:id', name: 'fde-order-detail', component: EmptyView },
      { path: '/fde/applications', name: 'fde-applications', component: EmptyView },
      { path: '/fde/assigned', name: 'fde-assigned', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
    ],
  })
  await router.push('/fde/publish')
  await router.isReady()

  const wrapper = mount(PublishOrderPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
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

function submitButton(wrapper: VueWrapper) {
  return wrapper.find('form button[type="submit"]')
}

describe('PublishOrderPage', () => {
  beforeEach(() => {
    vi.mocked(ordersBff.createOrder).mockReset()
  })

  it('renders the publish form with back links to the published list and the hall', async () => {
    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('发布需求')
    expect(wrapper.find('input[name="title"]').exists()).toBe(true)
    expect(wrapper.findAll('#publish-industry option')).toHaveLength(9)
    expect(wrapper.find('input[name="deliveryDays"]').exists()).toBe(true)
    expect(wrapper.find('input[name="priceYuan"]').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(true)

    const publishedLink = wrapper.findAll('a').find((node) => node.text() === '返回我发布的')
    expect(publishedLink?.attributes('href')).toBe('/fde/published')
    const hallLink = wrapper.findAll('a').find((node) => node.text() === '订单大厅')
    expect(hallLink?.attributes('href')).toBe('/fde/hall')
  })

  it('validates every field with Chinese messages before calling the BFF', async () => {
    const { wrapper } = await mountPage()

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

  it('publishes a demand, converts yuan to cents and opens the created order detail', async () => {
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

    const { wrapper, router } = await mountPage()
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
    expect(router.currentRoute.value.name).toBe('fde-order-detail')
    expect(router.currentRoute.value.params.id).toBe('12')
    expect(router.currentRoute.value.query.created).toBe('1')
  })

  it('keeps the page open and shows the error when publishing fails', async () => {
    vi.mocked(ordersBff.createOrder).mockRejectedValue(new BffError('server', '服务异常'))

    const { wrapper, router } = await mountPage()
    await fillForm(wrapper, {
      title: '新能源调度算法交付',
      industry: '能源电力',
      deliveryDays: '14',
      priceYuan: '860.50',
      description: '交付一套调度算法与验收报告。',
    })
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('订单服务暂时不可用')
    expect(router.currentRoute.value.name).toBe('fde-publish')
    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('disables the submit button while the request is in flight', async () => {
    let resolveCreate: ((value: ReturnType<typeof buildOrderView>) => void) | undefined
    vi.mocked(ordersBff.createOrder).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve
        }),
    )

    const { wrapper } = await mountPage()
    await fillForm(wrapper, {
      title: '新能源调度算法交付',
      industry: '能源电力',
      deliveryDays: '14',
      priceYuan: '860.50',
      description: '交付一套调度算法与验收报告。',
    })
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(ordersBff.createOrder).toHaveBeenCalledTimes(1)
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    expect(submitButton(wrapper).attributes('aria-busy')).toBe('true')

    resolveCreate?.(buildOrderView({ id: '12' }))
    await flushPromises()
  })
})
