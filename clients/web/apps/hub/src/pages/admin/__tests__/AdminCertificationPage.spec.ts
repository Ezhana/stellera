import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { adminBff } from '@/bff/admin'
import {
  buildAdminCertificationApplicationListModel,
  buildAdminCertificationApplicationView,
} from '@/bff/admin/__tests__/fixtures'
import { BffError } from '@/bff/errors'
import { buildViewer } from '@/bff/orders/__tests__/fixtures'
import AdminCertificationPage from '@/pages/admin/AdminCertificationPage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/admin', () => ({
  adminBff: {
    listCertificationApplications: vi.fn(),
    approveCertificationApplication: vi.fn(),
    rejectCertificationApplication: vi.fn(),
  },
}))

const EmptyView = { template: '<div />' }

const pendingApplication = buildAdminCertificationApplicationView({
  id: '11',
  type: 'realname',
  typeLabel: '实名认证',
  typeTone: 'info',
  status: 'pending',
  statusLabel: '待审核',
  statusTone: 'warning',
  realName: '张三',
  idNumber: '310101199001011234',
  contactPhone: '13800000000',
  description: '已实名认证，请审核。',
})

const enterpriseApplication = buildAdminCertificationApplicationView({
  id: '12',
  type: 'enterprise',
  typeLabel: '企业认证',
  typeTone: 'accent',
  status: 'approved',
  statusLabel: '已通过',
  statusTone: 'success',
  companyName: '远山科技',
  creditCode: '91310000MA1FL0000X',
  contactName: '张三',
  contactPhone: '13800000000',
  reviewer: { id: '1', displayName: '审核员', certifications: ['realname'] },
  reviewedAtLabel: '11-03 10:00',
  reviewNote: '材料齐全',
})

const adminViewer = buildViewer({
  isAdmin: true,
  certifications: [],
  roles: [{ key: 'admin', label: '管理员', tone: 'accent' }],
  capabilities: {
    publishOrder: true,
    applyOrder: true,
    submitOrderLog: true,
    viewWallet: true,
    redeemCode: true,
    manageAdmin: true,
  },
})

async function mountPage(): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.$patch({
    session: { viewer: adminViewer, remember: false, authenticatedAt: '2026-11-01T00:00:00.000Z' },
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
      { path: '/admin/users', name: 'admin-users', component: EmptyView },
      { path: '/admin/certifications', name: 'admin-certifications', component: EmptyView },
      { path: '/admin/redeem-codes', name: 'admin-redeem-codes', component: EmptyView },
      { path: '/admin/settings', name: 'admin-settings', component: EmptyView },
    ],
  })
  await router.push('/admin/certifications')
  await router.isReady()

  const wrapper = mount(AdminCertificationPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

describe('AdminCertificationPage', () => {
  beforeEach(() => {
    vi.mocked(adminBff.listCertificationApplications).mockResolvedValue(
      buildAdminCertificationApplicationListModel([pendingApplication, enterpriseApplication]),
    )
    vi.mocked(adminBff.approveCertificationApplication).mockResolvedValue(
      buildAdminCertificationApplicationView({ ...pendingApplication, status: 'approved' }),
    )
    vi.mocked(adminBff.rejectCertificationApplication).mockResolvedValue(
      buildAdminCertificationApplicationView({ ...pendingApplication, status: 'rejected' }),
    )
  })

  it('lists applications with applicant, type, status and summary', async () => {
    const { wrapper } = await mountPage()

    expect(adminBff.listCertificationApplications).toHaveBeenCalledWith({
      status: 'all',
      type: 'all',
      q: undefined,
      page: 1,
      pageSize: 20,
    })
    expect(wrapper.findAll('.cert-admin__row')).toHaveLength(2)
    expect(wrapper.text()).toContain('会员（演示）')
    expect(wrapper.text()).toContain('@member')
    expect(wrapper.text()).toContain('实名认证')
    expect(wrapper.text()).toContain('待审核')
    expect(wrapper.text()).toContain('企业认证')
    expect(wrapper.text()).toContain('已通过')
    expect(wrapper.text()).toContain('远山科技')
    expect(wrapper.text()).toContain('共 2 条申请')
  })

  it('reloads with the chosen status/type filters and keyword', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('#cert-status-filter').setValue('pending')
    await flushPromises()
    expect(adminBff.listCertificationApplications).toHaveBeenLastCalledWith({
      status: 'pending',
      type: 'all',
      q: undefined,
      page: 1,
      pageSize: 20,
    })

    await wrapper.find('#cert-type-filter').setValue('engineer')
    await flushPromises()
    expect(adminBff.listCertificationApplications).toHaveBeenLastCalledWith({
      status: 'pending',
      type: 'engineer',
      q: undefined,
      page: 1,
      pageSize: 20,
    })

    await wrapper.find('input[name="cert-search"]').setValue(' 阿远 ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(adminBff.listCertificationApplications).toHaveBeenLastCalledWith({
      status: 'pending',
      type: 'engineer',
      q: '阿远',
      page: 1,
      pageSize: 20,
    })
  })

  it('expands an application to show every field and the review record', async () => {
    const { wrapper } = await mountPage()

    const detailButtons = wrapper.findAll('button').filter((button) => button.text() === '详情')
    await detailButtons[1]?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('真实姓名')
    expect(wrapper.text()).toContain('310101199001011234')
    expect(wrapper.text()).toContain('已实名认证，请审核。')
    expect(wrapper.text()).toContain('统一社会信用代码')
    expect(wrapper.text()).toContain('91310000MA1FL0000X')
    expect(wrapper.text()).toContain('审核意见')
    expect(wrapper.text()).toContain('材料齐全')
    expect(wrapper.text()).toContain('审核员')
  })

  it('approves a pending application and refreshes the list', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '通过')?.trigger('click')
    await flushPromises()

    expect(adminBff.approveCertificationApplication).toHaveBeenCalledWith('11')
    expect(wrapper.text()).toContain('已通过实名认证申请，认证已授予该用户。')
    expect(adminBff.listCertificationApplications).toHaveBeenCalledTimes(2)
  })

  it('rejects a pending application with an optional note', async () => {
    const { wrapper } = await mountPage()

    await findButton(wrapper, '驳回')?.trigger('click')
    await flushPromises()
    await wrapper.find('textarea[name="cert-reject-note"]').setValue('材料不完整，请补充')
    await findButton(wrapper, '提交驳回')?.trigger('click')
    await flushPromises()

    expect(adminBff.rejectCertificationApplication).toHaveBeenCalledWith('11', '材料不完整，请补充')
    expect(wrapper.text()).toContain('已驳回实名认证申请。')
    expect(adminBff.listCertificationApplications).toHaveBeenCalledTimes(2)
  })

  it('does not offer review actions on already approved applications', async () => {
    const { wrapper } = await mountPage()

    const rows = wrapper.findAll('.cert-admin__row')
    const approvedRow = rows[1]
    expect(approvedRow?.text()).toContain('已通过')
    expect(approvedRow?.findAll('button').map((button) => button.text())).toEqual(['详情'])
  })

  it('shows a retry state when loading fails', async () => {
    vi.mocked(adminBff.listCertificationApplications)
      .mockRejectedValueOnce(new BffError('server', '服务异常'))
      .mockResolvedValueOnce(buildAdminCertificationApplicationListModel([pendingApplication]))

    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('管理服务暂时不可用')
    await findButton(wrapper, '重试')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('会员（演示）')
  })
})
