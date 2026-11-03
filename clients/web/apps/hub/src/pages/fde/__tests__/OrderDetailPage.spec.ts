import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BffError } from '@/bff/errors'
import { ordersBff } from '@/bff/orders'
import { buildApplicationView, buildOrderView, buildViewer } from '@/bff/orders/__tests__/fixtures'
import { profileBff } from '@/bff/profile'
import { buildPublicProfileView } from '@/bff/profile/__tests__/fixtures'
import type { FdeOrderDetailView } from '@/models'
import OrderDetailPage from '@/pages/fde/OrderDetailPage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/orders', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/bff/orders')>()
  return {
    ...actual,
    ordersBff: {
      getOrder: vi.fn(),
      applyForOrder: vi.fn(),
      cancelOrder: vi.fn(),
      approveApplication: vi.fn(),
      rejectApplication: vi.fn(),
      addWorkLog: vi.fn(),
    },
  }
})

vi.mock('@/bff/profile', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/bff/profile')>()
  return {
    ...actual,
    profileBff: { getPublicProfile: vi.fn() },
  }
})

const EmptyView = { template: '<div />' }

const publisherOrder = buildOrderView({
  id: '42',
  title: '医疗影像数据标注与质检',
  code: 'FDE-20261101-0042',
  status: 'open',
  statusLabel: '待接单',
  statusTone: 'warning',
  publisherId: '7',
  publisherName: 'Luna',
  publisherCertifications: ['realname', 'enterprise'],
  engineerId: null,
  engineerName: null,
  engineerCertifications: [],
})

const pendingAccept = buildApplicationView({
  id: '31',
  order: publisherOrder,
  type: 'accept',
  status: 'pending',
  applicantId: '6',
  applicantName: '会员（演示）',
  applicantCertifications: ['realname'],
  message: '有医疗行业交付经验',
})

function buildDetail(overrides: Partial<FdeOrderDetailView> = {}): FdeOrderDetailView {
  return {
    ...publisherOrder,
    logs: [
      {
        id: '11',
        authorName: '工程师阿远',
        content: '完成首批 200 例标注，已提交质检。',
        workedHours: 6,
        createdAtLabel: '11-01 10:30',
      },
    ],
    applications: [pendingAccept],
    ...overrides,
  }
}

interface MountOptions {
  viewerId?: string
  applications?: FdeOrderDetailView['applications']
  query?: Record<string, string>
}

async function mountPage(
  options: MountOptions = {},
): Promise<{ wrapper: VueWrapper; router: Router }> {
  const viewerId = options.viewerId ?? '6'
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.$patch({
    session: {
      viewer: buildViewer({ id: viewerId, username: 'viewer', displayName: '当前用户' }),
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
  await router.push({ name: 'fde-order-detail', params: { id: '42' }, query: options.query })
  await router.isReady()

  const wrapper = mount(OrderDetailPage, {
    global: { plugins: [pinia, router], stubs: { teleport: true } },
  })
  await flushPromises()
  return { wrapper, router }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

describe('OrderDetailPage', () => {
  beforeEach(() => {
    vi.mocked(ordersBff.getOrder).mockResolvedValue(buildDetail())
    vi.mocked(profileBff.getPublicProfile).mockImplementation(async (id) =>
      buildPublicProfileView({ id, nickname: id === '7' ? 'Luna' : '工程师阿远' }),
    )
    vi.mocked(ordersBff.applyForOrder).mockResolvedValue(pendingAccept)
    vi.mocked(ordersBff.cancelOrder).mockResolvedValue({ ...publisherOrder, status: 'cancelled' })
    vi.mocked(ordersBff.approveApplication).mockResolvedValue({
      ...pendingAccept,
      status: 'approved',
    })
    vi.mocked(ordersBff.rejectApplication).mockResolvedValue({
      ...pendingAccept,
      status: 'rejected',
    })
    vi.mocked(ordersBff.addWorkLog).mockResolvedValue({
      id: '12',
      authorName: '工程师阿远',
      content: '完成标注',
      workedHours: 4,
      createdAtLabel: '今天 11:00',
    })
  })

  it('loads the order, parties, work logs and the full application history', async () => {
    const { wrapper } = await mountPage()

    expect(ordersBff.getOrder).toHaveBeenCalledWith('42')
    expect(profileBff.getPublicProfile).toHaveBeenCalledWith('7')

    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).toContain('FDE-20261101-0042')
    expect(wrapper.text()).toContain('¥86,000')
    expect(wrapper.text()).toContain('7 天')
    expect(wrapper.text()).toContain('完成 500 例影像数据的标注与抽检。')
    expect(wrapper.text()).toContain('Luna')
    expect(wrapper.text()).toContain('企业认证')
    expect(wrapper.text()).toContain('完成首批 200 例标注，已提交质检。')
    expect(wrapper.text()).toContain('会员（演示）')
    expect(wrapper.text()).toContain('待审批')
    expect(wrapper.text()).toContain('有医疗行业交付经验')
  })

  it('lets a non-publisher apply to accept an open order through the modal', async () => {
    const { wrapper } = await mountPage({ viewerId: '8' })

    await findButton(wrapper, '申请接单')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('申请接单后需发布者审批')
    await wrapper.find('textarea[name="apply-message"]').setValue('有医疗行业交付经验')
    await findButton(wrapper, '确认申请')?.trigger('click')
    await flushPromises()

    expect(ordersBff.applyForOrder).toHaveBeenCalledWith('42', 'accept', '有医疗行业交付经验')
    expect(wrapper.text()).toContain('接单申请已提交，等待发布者审批。')
    expect(ordersBff.getOrder).toHaveBeenCalledTimes(2)
    expect(wrapper.find('textarea[name="apply-message"]').exists()).toBe(false)
  })

  it('lets the publisher cancel an open order after the second confirmation', async () => {
    const { wrapper } = await mountPage({ viewerId: '7' })

    await findButton(wrapper, '取消订单')?.trigger('click')
    await flushPromises()
    expect(ordersBff.cancelOrder).not.toHaveBeenCalled()
    expect(findButton(wrapper, '确认取消订单')).toBeDefined()

    await findButton(wrapper, '确认取消订单')?.trigger('click')
    await flushPromises()

    expect(ordersBff.cancelOrder).toHaveBeenCalledWith('42')
    expect(ordersBff.getOrder).toHaveBeenCalledTimes(2)
  })

  it('lets the publisher approve or reject a pending accept application', async () => {
    const { wrapper } = await mountPage({ viewerId: '7' })

    await findButton(wrapper, '通过接单')?.trigger('click')
    await flushPromises()
    expect(ordersBff.approveApplication).toHaveBeenCalledWith('31')

    await findButton(wrapper, '驳回')?.trigger('click')
    await flushPromises()
    await wrapper.find('textarea[name="detail-reject-note"]').setValue('经验不足')
    await findButton(wrapper, '提交驳回')?.trigger('click')
    await flushPromises()

    expect(ordersBff.rejectApplication).toHaveBeenCalledWith('31', '经验不足')
    expect(wrapper.text()).toContain('已驳回申请。')
  })

  it('lets the publisher confirm a pending delivery application', async () => {
    const delivery = buildApplicationView({
      id: '41',
      order: {
        ...publisherOrder,
        status: 'in_progress',
        statusLabel: '交付中',
        statusTone: 'info',
      },
      type: 'delivery',
      status: 'pending',
      applicantId: '9',
      applicantName: '工程师阿远',
      applicantCertifications: ['realname', 'engineer'],
      message: '已按验收标准完成交付。',
    })
    vi.mocked(ordersBff.getOrder).mockResolvedValue(
      buildDetail({
        status: 'in_progress',
        statusLabel: '交付中',
        statusTone: 'info',
        engineerId: '9',
        engineerName: '工程师阿远',
        applications: [delivery],
      }),
    )

    const { wrapper } = await mountPage({ viewerId: '7' })

    await findButton(wrapper, '确认交付')?.trigger('click')
    await flushPromises()

    expect(ordersBff.approveApplication).toHaveBeenCalledWith('41')
    expect(wrapper.text()).toContain('已确认交付，托管资金已结算给工程师。')
  })

  it('lets the assigned engineer submit a work log and apply for delivery from drawers', async () => {
    const inProgress = buildDetail({
      status: 'in_progress',
      statusLabel: '交付中',
      statusTone: 'info',
      engineerId: '9',
      engineerName: '工程师阿远',
      applications: [],
    })
    vi.mocked(ordersBff.getOrder).mockResolvedValue(inProgress)

    const { wrapper } = await mountPage({ viewerId: '9' })

    await findButton(wrapper, '提交工作日志')?.trigger('click')
    await flushPromises()
    await wrapper.find('textarea[name="work-log-content"]').setValue('完成 300 例标注')
    await wrapper.find('input[name="work-log-hours"]').setValue('6')
    await findButton(wrapper, '提交日志')?.trigger('click')
    await flushPromises()

    expect(ordersBff.addWorkLog).toHaveBeenCalledWith('42', {
      content: '完成 300 例标注',
      workedHours: 6,
    })
    expect(wrapper.text()).toContain('工作日志已提交。')
    expect(wrapper.find('textarea[name="work-log-content"]').exists()).toBe(false)

    await findButton(wrapper, '申请交付')?.trigger('click')
    await flushPromises()
    await wrapper.find('textarea[name="delivery-message"]').setValue('已按标准交付')
    await findButton(wrapper, '提交交付申请')?.trigger('click')
    await flushPromises()

    expect(ordersBff.applyForOrder).toHaveBeenCalledWith('42', 'delivery', '已按标准交付')
    expect(wrapper.text()).toContain('交付申请已提交，等待发布者审批。')
    expect(wrapper.find('textarea[name="delivery-message"]').exists()).toBe(false)
  })

  it('shows the one-time publish success notice after a created redirect', async () => {
    const { wrapper, router } = await mountPage({ query: { created: '1' } })

    expect(wrapper.text()).toContain('需求已发布，预算已进入托管。')
    expect(router.currentRoute.value.query.created).toBeUndefined()

    const dismiss = wrapper.find('.ui-alert__close')
    await dismiss.trigger('click')
    await flushPromises()

    expect(wrapper.find('.ui-alert--success').exists()).toBe(false)
  })

  it('keeps a completed order read-only', async () => {
    vi.mocked(ordersBff.getOrder).mockResolvedValue(
      buildDetail({
        status: 'completed',
        statusLabel: '已完成',
        statusTone: 'success',
        engineerId: '9',
        engineerName: '工程师阿远',
        applications: [],
      }),
    )

    const { wrapper } = await mountPage({ viewerId: '7' })

    expect(wrapper.text()).toContain('已完成')
    expect(findButton(wrapper, '申请接单')).toBeUndefined()
    expect(findButton(wrapper, '取消订单')).toBeUndefined()
    expect(findButton(wrapper, '提交工作日志')).toBeUndefined()
    expect(findButton(wrapper, '申请交付')).toBeUndefined()
  })

  it('shows a retry state when loading fails', async () => {
    vi.mocked(ordersBff.getOrder)
      .mockRejectedValueOnce(new BffError('not-found', 'missing'))
      .mockResolvedValueOnce(buildDetail())

    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('订单不存在或已被移除')
    await findButton(wrapper, '重试')?.trigger('click')
    await flushPromises()

    expect(ordersBff.getOrder).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
  })
})
