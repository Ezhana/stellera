import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { profileBff } from '@/bff/profile'
import {
  buildCertificationApplicationView,
  buildUserProfileView,
} from '@/bff/profile/__tests__/fixtures'
import { buildViewer } from '@/bff/orders/__tests__/fixtures'
import ProfilePage from '@/pages/ProfilePage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/profile', () => ({
  profileBff: {
    getMyProfile: vi.fn(),
    updateMyProfile: vi.fn(),
    getPublicProfile: vi.fn(),
    listMyCertificationApplications: vi.fn(),
    applyCertification: vi.fn(),
  },
}))

const EmptyView = { template: '<div />' }

async function mountPage(): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.$patch({
    session: {
      viewer: buildViewer({ id: '2', username: 'member', displayName: '会员（演示）' }),
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
  await router.push('/profile')
  await router.isReady()

  const wrapper = mount(ProfilePage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.mocked(profileBff.getMyProfile).mockResolvedValue(buildUserProfileView())
    vi.mocked(profileBff.listMyCertificationApplications).mockResolvedValue({ applications: [] })
    vi.mocked(profileBff.updateMyProfile).mockResolvedValue(
      buildUserProfileView({ nickname: '新昵称', bio: '新的介绍' }),
    )
    vi.mocked(profileBff.applyCertification).mockResolvedValue(
      buildCertificationApplicationView({ type: 'enterprise' }),
    )
  })

  it('renders the profile hero, nickname, certifications and profile form values', async () => {
    const { wrapper } = await mountPage()

    expect(profileBff.getMyProfile).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('会员（演示）')
    expect(wrapper.text()).toContain('实名认证')
    expect(wrapper.text()).toContain('@member')
    expect(wrapper.text()).toContain('张三')
    const nickname = wrapper.find('input[name="profile-nickname"]')
    expect((nickname.element as HTMLInputElement).value).toBe('会员（演示）')
    const profileLinks = wrapper
      .findAll('a[href="/profiles/2"]')
      .map((link) => link.text().replace(/\s+/g, ''))
    expect(profileLinks).toContain('查看公开主页')
  })

  it('saves the profile through the PATCH endpoint', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('input[name="profile-nickname"]').setValue(' 新昵称 ')
    await wrapper.find('textarea[name="profile-bio"]').setValue(' 新的介绍 ')
    await wrapper.find('input[name="profile-city"]').setValue(' 北京 ')
    await wrapper.find('input[name="profile-skills"]').setValue(' Python, SQL ')
    await wrapper.find('form.profile-form').trigger('submit')
    await flushPromises()

    expect(profileBff.updateMyProfile).toHaveBeenCalledWith({
      nickname: '新昵称',
      email: 'member@example.com',
      bio: '新的介绍',
      skills: 'Python, SQL',
      city: '北京',
      contactPhone: '13800000000',
      contactWechat: 'stellera-member',
    })
    expect(wrapper.text()).toContain('个人信息已保存。')
  })

  it('validates nickname and email before saving', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('input[name="profile-nickname"]').setValue('')
    await wrapper.find('input[name="profile-email"]').setValue('not-an-email')
    await wrapper.find('form.profile-form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入昵称')
    expect(wrapper.text()).toContain('请输入有效的邮箱地址')
    expect(profileBff.updateMyProfile).not.toHaveBeenCalled()
  })

  it('offers enterprise and engineer applications after realname certification', async () => {
    const { wrapper } = await mountPage()

    await wrapper.find('[data-tab="certification"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-apply-type="realname"]').exists()).toBe(false)
    expect(wrapper.find('[data-apply-type="enterprise"]').exists()).toBe(true)
    expect(wrapper.find('[data-apply-type="engineer"]').exists()).toBe(true)
  })

  it('only offers realname before the user is verified', async () => {
    vi.mocked(profileBff.getMyProfile).mockResolvedValue(
      buildUserProfileView({
        certifications: [],
        roles: [{ key: 'member', label: '会员', tone: 'default' }],
      }),
    )
    const { wrapper } = await mountPage()

    await wrapper.find('[data-tab="certification"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-apply-type="realname"]').exists()).toBe(true)
    expect(wrapper.find('[data-apply-type="enterprise"]').exists()).toBe(false)
  })

  it('submits an enterprise application and refreshes the profile', async () => {
    const { wrapper } = await mountPage()
    await wrapper.find('[data-tab="certification"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-apply-type="enterprise"]').trigger('click')
    await flushPromises()
    await wrapper.find('input[name="application-company"]').setValue('远山科技')
    await wrapper.find('input[name="application-credit-code"]').setValue('91310000MA1FL0000X')
    await wrapper.find('input[name="application-contact-name"]').setValue('张三')
    await wrapper.find('input[name="application-phone"]').setValue('13800000000')
    await wrapper.find('textarea[name="application-description"]').setValue('资质说明')
    await wrapper.find('form.profile-form').trigger('submit')
    await flushPromises()

    expect(profileBff.applyCertification).toHaveBeenCalledWith({
      type: 'enterprise',
      realName: undefined,
      idNumber: undefined,
      contactPhone: '13800000000',
      companyName: '远山科技',
      creditCode: '91310000MA1FL0000X',
      contactName: '张三',
      skills: undefined,
      workYears: undefined,
      projectExperience: undefined,
      description: '资质说明',
    })
    expect(wrapper.text()).toContain('认证申请已提交，等待平台审核。')
    expect(profileBff.getMyProfile).toHaveBeenCalledTimes(2)
    expect(profileBff.listMyCertificationApplications).toHaveBeenCalledTimes(2)
  })

  it('validates the dynamic application form', async () => {
    const { wrapper } = await mountPage()
    await wrapper.find('[data-tab="certification"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-apply-type="engineer"]').trigger('click')
    await flushPromises()

    await wrapper.find('form.profile-form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请填写技能')
    expect(wrapper.text()).toContain('请输入工作年限')
    expect(wrapper.text()).toContain('请输入联系电话')
    expect(profileBff.applyCertification).not.toHaveBeenCalled()
  })

  it('lists my applications with reviewer, review time and rejection note', async () => {
    vi.mocked(profileBff.listMyCertificationApplications).mockResolvedValue({
      applications: [
        buildCertificationApplicationView({
          id: '31',
          type: 'engineer',
          typeLabel: '工程师认证',
          typeTone: 'success',
          status: 'rejected',
          statusLabel: '已驳回',
          statusTone: 'error',
          reviewNote: '项目经历不足',
          reviewer: {
            id: '1',
            displayName: '审核员',
            certifications: ['realname'],
          },
          reviewedAtLabel: '11-03 10:00',
        }),
      ],
    })
    const { wrapper } = await mountPage()
    await wrapper.find('[data-tab="certification"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('工程师认证')
    expect(wrapper.text()).toContain('已驳回')
    expect(wrapper.text()).toContain('审核员')
    expect(wrapper.text()).toContain('11-03 10:00')
    expect(wrapper.text()).toContain('驳回理由：项目经历不足')
    expect(wrapper.find('[data-reapply-type="engineer"]').exists()).toBe(true)
  })

  it('renders cooperation stats and links records to the order detail', async () => {
    const { wrapper } = await mountPage()
    await wrapper.find('[data-tab="cooperation"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('完成单数')
    expect(wrapper.text()).toContain('合作方')
    expect(wrapper.text()).toContain('¥87,000')
    expect(wrapper.text()).toContain('医疗影像数据标注与质检')
    expect(wrapper.text()).toContain('工程师阿远')
    expect(wrapper.find('a.cooperation-record').attributes('href')).toBe('/fde/orders/42')
  })
})
