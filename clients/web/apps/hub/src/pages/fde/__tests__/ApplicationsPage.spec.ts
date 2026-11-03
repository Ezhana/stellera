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
import ApplicationsPage from '@/pages/fde/ApplicationsPage.vue'
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

const order = buildOrderView({ id: '5', title: '医疗影像数据标注与质检', status: 'open' })

const acceptApplication = buildApplicationView({
  id: '31',
  type: 'accept',
  status: 'pending',
  order,
  applicantName: '会员（演示）',
  applicantCertification: null,
  message: '有医疗行业交付经验',
})

const deliveryApplication = buildApplicationView({
  id: '32',
  type: 'delivery',
  status: 'pending',
  order: { ...order, status: 'in_progress', statusLabel: '交付中', statusTone: 'info' },
  applicantName: '工程师阿远',
  applicantCertification: 'engineer',
  message: '已按验收标准完成交付。',
})

async function mountPage(
  path = '/fde/applications',
): Promise<{ wrapper: VueWrapper; router: Router }> {
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
      { path: '/fde/assigned', name: 'fde-assigned', component: EmptyView },
      { path: '/fde/applications', name: 'fde-applications', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
    ],
  })
  await router.push(path)
  await router.isReady()

  const wrapper = mount(ApplicationsPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

describe('ApplicationsPage', () => {
  beforeEach(() => {
    vi.mocked(ordersBff.listMyApplications).mockResolvedValue(
      buildApplicationListModel([acceptApplication]),
    )
    vi.mocked(ordersBff.listReceivedApplications).mockResolvedValue(
      buildApplicationListModel([acceptApplication]),
    )
    vi.mocked(ordersBff.withdrawApplication).mockResolvedValue(
      buildApplicationView({ ...acceptApplication, status: 'withdrawn' }),
    )
    vi.mocked(ordersBff.approveApplication).mockResolvedValue(
      buildApplicationView({ ...acceptApplication, status: 'approved' }),
    )
    vi.mocked(ordersBff.rejectApplication).mockResolvedValue(
      buildApplicationView({ ...acceptApplication, status: 'rejected' }),
    )
  })

  it('loads my applications and renders the order, applicant certification and actions', async () => {
    const { wrapper } = await mountPage()

    expect(ordersBff.listMyApplications).toHaveBeenCalledWith({
      type: 'all',
      status: 'all',
      page: 1,
      pageSize: 10,
    })
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).toContain('接单申请')
    expect(wrapper.text()).toContain('待审批')
    expect(wrapper.text()).toContain('会员（演示）')
    expect(wrapper.text()).toContain('有医疗行业交付经验')
    expect(findButton(wrapper, '撤回申请')).toBeDefined()
    expect(findButton(wrapper, '通过接单')).toBeUndefined()
    expect(wrapper.findAll('.application-card')).toHaveLength(1)
  })

  it('switches to the received tab and loads applications awaiting my review', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('[data-tab="received"]').trigger('click')
    await flushPromises()

    expect(ordersBff.listReceivedApplications).toHaveBeenCalledWith({
      type: 'all',
      status: 'pending',
      page: 1,
      pageSize: 10,
    })
    expect(findButton(wrapper, '通过接单')).toBeDefined()
    expect(findButton(wrapper, '驳回')).toBeDefined()
    expect(findButton(wrapper, '撤回申请')).toBeUndefined()
  })

  it('opens directly on the review tab when the query asks for it', async () => {
    await mountPage('/fde/applications?tab=received')

    expect(ordersBff.listReceivedApplications).toHaveBeenCalledTimes(1)
    expect(ordersBff.listReceivedApplications).toHaveBeenCalledWith({
      type: 'all',
      status: 'pending',
      page: 1,
      pageSize: 10,
    })
    expect(ordersBff.listMyApplications).not.toHaveBeenCalled()
  })

  it('withdraws a pending application and refreshes the list', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '撤回申请')?.trigger('click')
    await flushPromises()

    expect(ordersBff.withdrawApplication).toHaveBeenCalledWith('31')
    expect(wrapper.text()).toContain('申请已撤回。')
    expect(ordersBff.listMyApplications).toHaveBeenCalledTimes(2)
  })

  it('approves a received application', async () => {
    const { wrapper } = await mountPage('/fde/applications?tab=received')

    await findButton(wrapper, '通过接单')?.trigger('click')
    await flushPromises()

    expect(ordersBff.approveApplication).toHaveBeenCalledWith('31')
    expect(wrapper.text()).toContain('已通过接单申请。')
    expect(ordersBff.listReceivedApplications).toHaveBeenCalledTimes(2)
  })

  it('rejects a received application with an optional note', async () => {
    const { wrapper } = await mountPage('/fde/applications?tab=received')

    await findButton(wrapper, '驳回')?.trigger('click')
    await flushPromises()
    await wrapper.find('textarea[name="reject-note"]').setValue('暂不符合岗位要求')
    await findButton(wrapper, '提交驳回')?.trigger('click')
    await flushPromises()

    expect(ordersBff.rejectApplication).toHaveBeenCalledWith('31', '暂不符合岗位要求')
    expect(wrapper.text()).toContain('已驳回申请。')
    expect(ordersBff.listReceivedApplications).toHaveBeenCalledTimes(2)
  })

  it('renders the delivery action label for a delivery application', async () => {
    vi.mocked(ordersBff.listReceivedApplications).mockResolvedValue(
      buildApplicationListModel([deliveryApplication]),
    )
    const { wrapper } = await mountPage('/fde/applications?tab=received')

    expect(findButton(wrapper, '确认交付')).toBeDefined()
    expect(wrapper.text()).toContain('工程师认证')
    expect(wrapper.text()).toContain('已按验收标准完成交付。')
  })

  it('reloads with the selected type and status filters', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('#application-type-filter').setValue('accept')
    await flushPromises()
    expect(ordersBff.listMyApplications).toHaveBeenLastCalledWith({
      type: 'accept',
      status: 'all',
      page: 1,
      pageSize: 10,
    })

    await wrapper.find('#application-status-filter').setValue('approved')
    await flushPromises()
    expect(ordersBff.listMyApplications).toHaveBeenLastCalledWith({
      type: 'accept',
      status: 'approved',
      page: 1,
      pageSize: 10,
    })
  })

  it('shows an empty state and paginates the loaded page', async () => {
    vi.mocked(ordersBff.listMyApplications).mockResolvedValue(
      buildApplicationListModel([], { total: 12, pageSize: 10 }),
    )
    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('暂无符合条件的申请。')
    expect(wrapper.text()).toContain('共 12 条申请 · 第 1 / 2 页')

    await findButton(wrapper, '下一页')?.trigger('click')
    await flushPromises()

    expect(ordersBff.listMyApplications).toHaveBeenLastCalledWith({
      type: 'all',
      status: 'all',
      page: 2,
      pageSize: 10,
    })
  })

  it('shows a retry state when loading fails', async () => {
    vi.mocked(ordersBff.listMyApplications)
      .mockRejectedValueOnce(new BffError('server', '服务异常'))
      .mockResolvedValueOnce(buildApplicationListModel([acceptApplication]))

    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('订单服务暂时不可用')
    await findButton(wrapper, '重试')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
  })
})
