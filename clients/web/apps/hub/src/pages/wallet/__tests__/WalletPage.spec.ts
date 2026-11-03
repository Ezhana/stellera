import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BffError } from '@/bff/errors'
import { buildViewer } from '@/bff/orders/__tests__/fixtures'
import { walletBff } from '@/bff/wallet'
import {
  buildRedeemResultView,
  buildWalletPageModel,
  buildWalletSummaryView,
  buildWalletTransactionListModel,
  buildWalletTransactionView,
} from '@/bff/wallet/__tests__/fixtures'
import WalletPage from '@/pages/wallet/WalletPage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/bff/wallet', () => ({
  walletBff: {
    loadPage: vi.fn(),
    redeem: vi.fn(),
  },
}))

const EmptyView = { template: '<div />' }

const payment = buildWalletTransactionView({
  id: '1',
  type: 'order_payment',
  typeLabel: '消费',
  typeTone: 'warning',
  direction: 'debit',
  amountCents: 50_000,
  amountLabel: '-¥500',
  balanceAfterLabel: '¥9,500',
  description: '发布需求托管',
})

const recharge = buildWalletTransactionView({
  id: '2',
  type: 'recharge',
  typeLabel: '充值',
  typeTone: 'success',
  direction: 'credit',
  amountCents: 10_000,
  amountLabel: '+¥100',
  balanceAfterLabel: '¥9,600',
  description: '线下充值',
})

const refund = buildWalletTransactionView({
  id: '3',
  type: 'order_refund',
  typeLabel: '退款',
  typeTone: 'info',
  direction: 'credit',
  amountCents: 30_000,
  amountLabel: '+¥300',
  balanceAfterLabel: '¥9,900',
  description: '取消订单退回',
})

const summary = buildWalletSummaryView({
  balanceCents: 1_234_500,
  balanceLabel: '¥12,345',
  usageTotalLabel: '¥2,000',
  redeemTotalLabel: '¥500',
  rechargeTotalLabel: '¥4,000',
  rechargeNote: '在线充值暂未开放，请联系客服线下充值。',
  supportContact: '客服微信：stellera-support',
})

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
      { path: '/fde/hall', name: 'fde-hall', component: EmptyView },
      { path: '/fde/published', name: 'fde-published', component: EmptyView },
      { path: '/fde/assigned', name: 'fde-assigned', component: EmptyView },
      { path: '/fde/applications', name: 'fde-applications', component: EmptyView },
      { path: '/wallet', name: 'wallet', component: EmptyView },
    ],
  })
  await router.push('/wallet')
  await router.isReady()

  const wrapper = mount(WalletPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

function findTab(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('.wallet-tabs__button').find((button) => button.text() === label)
}

describe('WalletPage', () => {
  beforeEach(() => {
    vi.mocked(walletBff.loadPage).mockResolvedValue(
      buildWalletPageModel({
        summary,
        transactions: buildWalletTransactionListModel([payment, recharge, refund]),
        rechargeRecords: [recharge],
      }),
    )
    vi.mocked(walletBff.redeem).mockResolvedValue(buildRedeemResultView())
  })

  it('renders the balance cards, recent transactions and tab bar', async () => {
    const { wrapper } = await mountPage()

    expect(walletBff.loadPage).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('我的钱包')
    expect(wrapper.text()).toContain('¥12,345')
    expect(wrapper.text()).toContain('¥2,000')
    expect(wrapper.text()).toContain('¥500')
    expect(wrapper.text()).toContain('¥4,000')
    expect(wrapper.text()).toContain('发布需求托管')
    expect(wrapper.text()).toContain('线下充值')
    expect(wrapper.findAll('.wallet-tabs__button').map((button) => button.text())).toEqual([
      '概览',
      '用量明细',
      '充值',
      '兑换码',
    ])
  })

  it('switches to the usage tab and filters the loaded rows client-side', async () => {
    const { wrapper } = await mountPage()

    await findTab(wrapper, '用量明细')?.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.wallet-table tbody tr')).toHaveLength(3)

    const paymentFilter = wrapper
      .findAll('.wallet-filters__button')
      .find((button) => button.text() === '消费')
    await paymentFilter?.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.wallet-table tbody tr')).toHaveLength(1)
    expect(wrapper.find('.wallet-table').text()).toContain('发布需求托管')
    expect(wrapper.find('.wallet-table').text()).not.toContain('线下充值')

    const refundFilter = wrapper
      .findAll('.wallet-filters__button')
      .find((button) => button.text() === '退款')
    await refundFilter?.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.wallet-table tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('取消订单退回')
  })

  it('shows the recharge tab with disabled tiers and the offline copy', async () => {
    const { wrapper } = await mountPage()

    await findTab(wrapper, '充值')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('在线充值暂未开放')

    const tiers = wrapper.findAll('.wallet-recharge__tier')
    expect(tiers).toHaveLength(4)
    expect(tiers.map((tier) => tier.text().replace(/\s+/g, ''))).toEqual([
      '¥100暂不可用',
      '¥500暂不可用',
      '¥1,000暂不可用',
      '¥5,000暂不可用',
    ])
    for (const tier of tiers) {
      expect(tier.attributes('disabled')).toBeDefined()
    }

    expect(wrapper.text()).toContain('在线充值暂未开放，请联系客服线下充值。')
    expect(wrapper.text()).toContain('客服微信：stellera-support')
    expect(wrapper.findAll('.wallet-table tbody tr')).toHaveLength(1)
  })

  it('redeems a code, reports the credited amount and refreshes the wallet', async () => {
    vi.mocked(walletBff.loadPage)
      .mockResolvedValueOnce(
        buildWalletPageModel({
          summary,
          transactions: buildWalletTransactionListModel([payment]),
          rechargeRecords: [],
        }),
      )
      .mockResolvedValueOnce(
        buildWalletPageModel({
          summary: buildWalletSummaryView({ ...summary, balanceLabel: '¥12,445' }),
          transactions: buildWalletTransactionListModel([payment]),
          rechargeRecords: [],
        }),
      )

    const { wrapper } = await mountPage()

    await wrapper.find('input[name="redeem-code"]').setValue('RDM-AAAA-BBBB-CCCC')
    await wrapper.find('form.wallet-redeem-form').trigger('submit')
    await flushPromises()

    expect(walletBff.redeem).toHaveBeenCalledWith('RDM-AAAA-BBBB-CCCC')
    expect(walletBff.loadPage).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('兑换成功')
    expect(wrapper.text()).toContain('¥100 已到账')
    expect(wrapper.find('input[name="redeem-code"]').attributes('value')).toBeUndefined()
  })

  it('validates the code locally and surfaces the BffError message from the backend', async () => {
    vi.mocked(walletBff.redeem).mockRejectedValue(
      new BffError('conflict', '该兑换码已被使用。', { status: 409 }),
    )

    const { wrapper } = await mountPage()

    await wrapper.find('form.wallet-redeem-form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入兑换码')
    expect(walletBff.redeem).not.toHaveBeenCalled()

    await wrapper.find('input[name="redeem-code"]').setValue('RDM-USED')
    await wrapper.find('form.wallet-redeem-form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('该兑换码已被使用。')
    expect(walletBff.loadPage).toHaveBeenCalledTimes(1)
  })

  it('shows a load error and retries', async () => {
    vi.mocked(walletBff.loadPage)
      .mockRejectedValueOnce(new BffError('network', '网络异常'))
      .mockResolvedValueOnce(
        buildWalletPageModel({
          summary,
          transactions: buildWalletTransactionListModel([payment]),
          rechargeRecords: [],
        }),
      )

    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('无法连接到服务')

    const retry = wrapper.findAll('button').find((button) => button.text() === '重试')
    await retry?.trigger('click')
    await flushPromises()

    expect(walletBff.loadPage).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('¥12,345')
  })
})
