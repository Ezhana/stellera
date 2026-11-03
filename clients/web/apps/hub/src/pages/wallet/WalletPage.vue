<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { z } from 'zod'

import { BffError } from '@/bff/errors'
import { walletBff } from '@/bff/wallet'
import PageHeader from '@/components/console/PageHeader.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import {
  WALLET_TRANSACTION_TYPES,
  type WalletPageModel,
  type WalletTransactionType,
} from '@/models'
import { useAuthStore } from '@/stores/auth'

type WalletTab = 'overview' | 'usage' | 'recharge' | 'redeem'

const TABS: readonly { key: WalletTab; label: string }[] = [
  { key: 'overview', label: '概览' },
  { key: 'usage', label: '用量明细' },
  { key: 'recharge', label: '充值' },
  { key: 'redeem', label: '兑换码' },
]

const USAGE_FILTERS: readonly { key: WalletTransactionType | 'all'; label: string }[] = [
  { key: 'all', label: '全部' },
  ...WALLET_TRANSACTION_TYPES.map((meta) => ({ key: meta.key, label: meta.label })),
]

/** Display-only tiers: online recharge is not enabled yet, so every button stays disabled. */
const RECHARGE_TIERS: readonly { cents: number; label: string }[] = [
  { cents: 10_000, label: '¥100' },
  { cents: 50_000, label: '¥500' },
  { cents: 100_000, label: '¥1,000' },
  { cents: 500_000, label: '¥5,000' },
]

const auth = useAuthStore()
const viewer = computed(() => auth.viewer)

const model = ref<WalletPageModel | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const errorMessage = ref('')
const activeTab = ref<WalletTab>('overview')
const usageFilter = ref<WalletTransactionType | 'all'>('all')

const redeemCode = ref('')
const redeeming = ref(false)
const redeemError = ref('')
const redeemSuccess = ref('')

const redeemSchema = z
  .string()
  .trim()
  .min(1, '请输入兑换码')
  .max(64, '兑换码长度不能超过 64 个字符')

const summary = computed(() => model.value?.summary ?? null)
const recentTransactions = computed(() => model.value?.transactions.transactions.slice(0, 5) ?? [])
const rechargeRecords = computed(() => model.value?.rechargeRecords ?? [])

const filteredTransactions = computed(() => {
  const rows = model.value?.transactions.transactions ?? []
  if (usageFilter.value === 'all') return rows
  return rows.filter((transaction) => transaction.type === usageFilter.value)
})

const statCards = computed(() => {
  const value = summary.value
  if (!value) return []

  return [
    {
      key: 'balance',
      label: '可用余额',
      value: value.balanceLabel,
      meta: '可用于发布需求与托管',
      money: true,
    },
    {
      key: 'usage',
      label: '累计用量',
      value: value.usageTotalLabel,
      meta: '订单消费合计',
      money: false,
    },
    {
      key: 'redeem',
      label: '累计兑换',
      value: value.redeemTotalLabel,
      meta: '兑换码到账合计',
      money: false,
    },
    {
      key: 'recharge',
      label: '累计充值',
      value: value.rechargeTotalLabel,
      meta: '线下充值合计',
      money: false,
    },
  ]
})

/** Map the BFF's stable error codes to wallet copy; the page never inspects HTTP statuses. */
function toLoadErrorMessage(error: unknown): string {
  if (!(error instanceof BffError)) return '钱包数据加载失败，请稍后重试。'

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return '当前账号没有查看钱包的权限。'
    case 'network':
      return '无法连接到服务，请检查网络后重试。'
    case 'server':
      return '钱包服务暂时不可用，请稍后再试。'
    case 'malformed-response':
      return '服务返回的数据格式异常，请联系管理员。'
    default:
      return error.message || '钱包数据加载失败，请稍后重试。'
  }
}

function toRedeemErrorMessage(error: unknown): string {
  if (!(error instanceof BffError)) return '兑换失败，请稍后重试。'

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'network':
      return '无法连接到服务，请检查网络后重试。'
    case 'forbidden':
      return '当前账号没有兑换权限，请联系管理员。'
    default:
      return error.message || '兑换失败，请稍后重试。'
  }
}

async function loadWallet(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  errorMessage.value = ''

  try {
    model.value = await walletBff.loadPage()
  } catch (error) {
    errorMessage.value = toLoadErrorMessage(error)
  } finally {
    loading.value = false
  }
}

async function refresh(): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await loadWallet(false)
  } finally {
    refreshing.value = false
  }
}

async function handleRedeem(): Promise<void> {
  if (redeeming.value) return

  redeemError.value = ''
  redeemSuccess.value = ''

  const parsed = redeemSchema.safeParse(redeemCode.value)
  if (!parsed.success) {
    redeemError.value = parsed.error.issues[0]?.message ?? '请输入兑换码'
    return
  }

  redeeming.value = true
  try {
    const result = await walletBff.redeem(parsed.data)
    redeemCode.value = ''
    redeemSuccess.value = `兑换成功，${result.amountLabel} 已到账，当前余额 ${result.balanceLabel}。`
    await loadWallet(false)
  } catch (error) {
    redeemError.value = toRedeemErrorMessage(error)
  } finally {
    redeeming.value = false
  }
}

onMounted(() => {
  void loadWallet()
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="wallet-page">
      <PageHeader
        eyebrow="MY WALLET"
        title="我的钱包"
        description="查看余额与流水、用兑换码充值，并管理交付预算。"
      >
        <template #actions>
          <UiButton variant="secondary" size="sm" :loading="refreshing" @click="refresh">
            <UiIcon name="refresh" :size="16" />
            刷新
          </UiButton>
        </template>
      </PageHeader>

      <div v-if="loading" class="wallet-page__state" role="status" aria-live="polite">
        <span class="wallet-page__spinner" aria-hidden="true" />
        正在加载钱包…
      </div>

      <div v-else-if="errorMessage" class="wallet-page__error">
        <UiAlert variant="error" title="钱包加载失败">{{ errorMessage }}</UiAlert>
        <UiButton variant="secondary" size="sm" @click="loadWallet()">重试</UiButton>
      </div>

      <template v-else-if="summary">
        <div class="wallet-stats">
          <UiCard v-for="card in statCards" :key="card.key" padding="md" class="wallet-stats__card">
            <p class="wallet-stats__label">{{ card.label }}</p>
            <p class="wallet-stats__value" :class="{ 'wallet-stats__value--money': card.money }">
              {{ card.value }}
            </p>
            <p class="wallet-stats__meta">{{ card.meta }}</p>
          </UiCard>
        </div>

        <section class="wallet-panel">
          <div class="wallet-tabs" role="tablist" aria-label="钱包视图">
            <button
              v-for="tab in TABS"
              :key="tab.key"
              class="wallet-tabs__button"
              :class="{ 'is-active': activeTab === tab.key }"
              type="button"
              role="tab"
              :aria-selected="activeTab === tab.key ? 'true' : 'false'"
              @click="activeTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>

          <!-- 概览：近期流水 + 快捷兑换 -->
          <div v-if="activeTab === 'overview'" class="wallet-panel__body" role="tabpanel">
            <div class="wallet-overview">
              <div class="wallet-overview__main">
                <header class="wallet-section-head">
                  <h2 class="wallet-section-title">近期流水</h2>
                  <button class="wallet-link" type="button" @click="activeTab = 'usage'">
                    查看全部
                    <UiIcon name="arrow-right" :size="14" />
                  </button>
                </header>

                <ul v-if="recentTransactions.length" class="wallet-recent">
                  <li
                    v-for="transaction in recentTransactions"
                    :key="transaction.id"
                    class="wallet-recent__item"
                  >
                    <span class="wallet-recent__time">{{ transaction.createdAtLabel }}</span>
                    <UiChip :variant="transaction.typeTone">{{ transaction.typeLabel }}</UiChip>
                    <span class="wallet-recent__description">{{ transaction.description }}</span>
                    <span
                      class="wallet-recent__amount"
                      :class="{ 'is-debit': transaction.direction === 'debit' }"
                    >
                      {{ transaction.amountLabel }}
                    </span>
                  </li>
                </ul>
                <p v-else class="wallet-empty">暂无流水记录，发布需求或兑换后会在这里展示。</p>
              </div>

              <UiCard padding="md" class="wallet-redeem-card">
                <p class="hub-eyebrow">REDEEM CODE</p>
                <h2 class="wallet-redeem-card__title">快捷兑换</h2>
                <p class="wallet-redeem-card__hint">输入管理员发放的兑换码，金额将立即到账。</p>

                <UiAlert
                  v-if="redeemError"
                  variant="error"
                  title="兑换失败"
                  dismissible
                  @close="redeemError = ''"
                >
                  {{ redeemError }}
                </UiAlert>
                <UiAlert
                  v-if="redeemSuccess"
                  variant="success"
                  title="兑换成功"
                  dismissible
                  @close="redeemSuccess = ''"
                >
                  {{ redeemSuccess }}
                </UiAlert>

                <form class="wallet-redeem-form" novalidate @submit.prevent="handleRedeem">
                  <UiInput
                    v-model="redeemCode"
                    name="redeem-code"
                    label="兑换码"
                    placeholder="RDM-XXXX-XXXX-XXXX"
                    :disabled="redeeming"
                  />
                  <UiButton type="submit" :loading="redeeming">立即兑换</UiButton>
                </form>
              </UiCard>
            </div>
          </div>

          <!-- 用量明细：客户端过滤已加载的最近 50 条流水 -->
          <div v-else-if="activeTab === 'usage'" class="wallet-panel__body" role="tabpanel">
            <div class="wallet-toolbar">
              <div class="wallet-filters" role="group" aria-label="按流水类型筛选">
                <button
                  v-for="filter in USAGE_FILTERS"
                  :key="filter.key"
                  class="wallet-filters__button"
                  :class="{ 'is-active': usageFilter === filter.key }"
                  type="button"
                  :aria-pressed="usageFilter === filter.key ? 'true' : 'false'"
                  @click="usageFilter = filter.key"
                >
                  {{ filter.label }}
                </button>
              </div>
              <span class="wallet-toolbar__result">
                已加载 {{ model?.transactions.transactions.length ?? 0 }} 条 · 当前显示
                {{ filteredTransactions.length }} 条
              </span>
            </div>

            <div v-if="filteredTransactions.length" class="wallet-table__scroll">
              <table class="wallet-table">
                <caption class="visually-hidden">
                  钱包用量明细
                </caption>
                <thead>
                  <tr>
                    <th scope="col">时间</th>
                    <th scope="col">类型</th>
                    <th scope="col">说明</th>
                    <th scope="col">金额</th>
                    <th scope="col">余额</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="transaction in filteredTransactions" :key="transaction.id">
                    <td class="wallet-table__cell wallet-table__cell--nowrap">
                      {{ transaction.createdAtLabel }}
                    </td>
                    <td class="wallet-table__cell">
                      <UiChip :variant="transaction.typeTone">{{ transaction.typeLabel }}</UiChip>
                    </td>
                    <td class="wallet-table__cell wallet-table__description">
                      {{ transaction.description }}
                    </td>
                    <td
                      class="wallet-table__cell wallet-table__amount"
                      :class="{ 'is-debit': transaction.direction === 'debit' }"
                    >
                      {{ transaction.amountLabel }}
                    </td>
                    <td class="wallet-table__cell wallet-table__cell--nowrap">
                      {{ transaction.balanceAfterLabel }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-else class="wallet-empty">没有符合筛选条件的流水。</p>
          </div>

          <!-- 充值：在线充值暂未开放，只展示档位与线下充值记录 -->
          <div v-else-if="activeTab === 'recharge'" class="wallet-panel__body" role="tabpanel">
            <UiAlert variant="info" title="在线充值暂未开放">
              接入支付渠道后开启在线充值；当前可联系客服线下充值，或使用兑换码到账。
            </UiAlert>

            <div class="wallet-recharge__tiers" aria-label="充值金额档位">
              <button
                v-for="tier in RECHARGE_TIERS"
                :key="tier.cents"
                class="wallet-recharge__tier"
                type="button"
                disabled
              >
                <span class="wallet-recharge__tier-amount">{{ tier.label }}</span>
                <span class="wallet-recharge__tier-hint">暂不可用</span>
              </button>
            </div>

            <div class="wallet-recharge__notes">
              <p>{{ summary.rechargeNote || '在线充值暂未开放，请通过客服或兑换码充值。' }}</p>
              <p v-if="summary.supportContact">客服联系方式：{{ summary.supportContact }}</p>
            </div>

            <header class="wallet-section-head">
              <h2 class="wallet-section-title">充值记录</h2>
            </header>

            <div v-if="rechargeRecords.length" class="wallet-table__scroll">
              <table class="wallet-table">
                <caption class="visually-hidden">
                  充值记录
                </caption>
                <thead>
                  <tr>
                    <th scope="col">时间</th>
                    <th scope="col">类型</th>
                    <th scope="col">说明</th>
                    <th scope="col">金额</th>
                    <th scope="col">余额</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="transaction in rechargeRecords" :key="transaction.id">
                    <td class="wallet-table__cell wallet-table__cell--nowrap">
                      {{ transaction.createdAtLabel }}
                    </td>
                    <td class="wallet-table__cell">
                      <UiChip :variant="transaction.typeTone">{{ transaction.typeLabel }}</UiChip>
                    </td>
                    <td class="wallet-table__cell wallet-table__description">
                      {{ transaction.description }}
                    </td>
                    <td class="wallet-table__cell wallet-table__amount">
                      {{ transaction.amountLabel }}
                    </td>
                    <td class="wallet-table__cell wallet-table__cell--nowrap">
                      {{ transaction.balanceAfterLabel }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-else class="wallet-empty">暂无充值记录。</p>
          </div>

          <!-- 兑换码 -->
          <div v-else class="wallet-panel__body" role="tabpanel">
            <UiCard padding="md" class="wallet-redeem-card wallet-redeem-card--wide">
              <p class="hub-eyebrow">REDEEM CODE</p>
              <h2 class="wallet-redeem-card__title">兑换码充值</h2>
              <p class="wallet-redeem-card__hint">
                输入 1–64 位兑换码，兑换成功后金额立即计入可用余额。
              </p>

              <UiAlert
                v-if="redeemError"
                variant="error"
                title="兑换失败"
                dismissible
                @close="redeemError = ''"
              >
                {{ redeemError }}
              </UiAlert>
              <UiAlert
                v-if="redeemSuccess"
                variant="success"
                title="兑换成功"
                dismissible
                @close="redeemSuccess = ''"
              >
                {{ redeemSuccess }}
              </UiAlert>

              <form class="wallet-redeem-form" novalidate @submit.prevent="handleRedeem">
                <UiInput
                  v-model="redeemCode"
                  name="redeem-code"
                  label="兑换码"
                  placeholder="RDM-XXXX-XXXX-XXXX"
                  :maxlength="64"
                  :disabled="redeeming"
                />
                <UiButton type="submit" :loading="redeeming">立即兑换</UiButton>
              </form>
            </UiCard>
          </div>
        </section>
      </template>
    </div>
  </ConsoleLayout>
</template>

<style scoped>
.wallet-page {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.wallet-page__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.wallet-page__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: var(--radius-pill);
  animation: wallet-page-spin 0.9s linear infinite;
}

@keyframes wallet-page-spin {
  to {
    transform: rotate(360deg);
  }
}

.wallet-page__error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--primitive-space-3);
}

.wallet-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.wallet-stats__card {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
}

.wallet-stats__label {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  letter-spacing: var(--font-letter-spacing-label);
}

.wallet-stats__value {
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h2);
  font-variant-numeric: tabular-nums;
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.wallet-stats__value--money {
  color: var(--obsidian-gold-text);
  font-size: var(--font-size-h3);
}

.wallet-stats__meta {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  line-height: var(--font-line-height-caption);
}

.wallet-panel {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-5);
  padding: var(--primitive-space-5);
  background-color: var(--color-surface);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-surface);
  box-shadow: var(--obsidian-panel-highlight);
}

.wallet-tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-1);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
  align-self: flex-start;
}

.wallet-tabs__button {
  min-height: 34px;
  padding: 0 var(--primitive-space-4);
  color: var(--color-fg-muted);
  background: transparent;
  border: var(--border-width-default) solid transparent;
  border-radius: var(--radius-small);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: 1;
  white-space: nowrap;
  transition:
    color var(--motion-duration-fast) var(--motion-easing-standard),
    background-color var(--motion-duration-fast) var(--motion-easing-standard),
    border-color var(--motion-duration-fast) var(--motion-easing-standard);
}

.wallet-tabs__button:hover {
  color: var(--color-fg);
}

.wallet-tabs__button.is-active {
  color: var(--obsidian-gold-text);
  background-color: var(--color-accent-subtle);
  border-color: var(--color-accent-border);
}

.wallet-panel__body {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.wallet-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  align-items: start;
  gap: var(--primitive-space-4);
}

.wallet-overview__main {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  min-width: 0;
}

.wallet-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.wallet-section-title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
}

.wallet-link {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-1);
  color: var(--color-accent-hover);
  background: transparent;
  border: 0;
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
}

.wallet-link:hover {
  color: var(--color-accent);
}

.wallet-recent {
  display: flex;
  flex-direction: column;
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.wallet-recent__item {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-3) 0;
  border-bottom: var(--border-width-default) solid var(--color-border-subtle);
}

.wallet-recent__time {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.wallet-recent__description {
  color: var(--color-fg);
  font-size: var(--font-size-small);
  overflow-wrap: anywhere;
}

.wallet-recent__amount {
  color: var(--color-success);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-small);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.wallet-recent__amount.is-debit {
  color: var(--color-warning);
}

.wallet-redeem-card {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  background-color: var(--color-surface-elevated);
}

.wallet-redeem-card--wide {
  width: 100%;
  max-width: 36rem;
}

.wallet-redeem-card__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
}

.wallet-redeem-card__hint {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.wallet-redeem-form {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
}

.wallet-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.wallet-filters {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-1);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.wallet-filters__button {
  min-height: 30px;
  padding: 0 var(--primitive-space-3);
  color: var(--color-fg-muted);
  background: transparent;
  border: var(--border-width-default) solid transparent;
  border-radius: var(--radius-small);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: 1;
  white-space: nowrap;
}

.wallet-filters__button:hover {
  color: var(--color-fg);
}

.wallet-filters__button.is-active {
  color: var(--obsidian-gold-text);
  background-color: var(--color-accent-subtle);
  border-color: var(--color-accent-border);
}

.wallet-toolbar__result {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.wallet-recharge__tiers {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--primitive-space-3);
}

.wallet-recharge__tier {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-4);
  color: var(--color-fg-muted);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.wallet-recharge__tier-amount {
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h3);
  font-variant-numeric: tabular-nums;
}

.wallet-recharge__tier-hint {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
}

.wallet-recharge__notes {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--color-fg-muted);
  background-color: var(--color-bg-subtle);
  border-left: 2px solid var(--color-accent-border);
  border-radius: var(--radius-small);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.wallet-empty {
  padding: var(--primitive-space-8) var(--primitive-space-4);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  text-align: center;
}

.wallet-table__scroll {
  width: 100%;
  overflow-x: auto;
}

.wallet-table {
  width: 100%;
  min-width: 44rem;
  border-collapse: collapse;
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  text-align: left;
}

.wallet-table thead th {
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--obsidian-tertiary-text);
  border-bottom: var(--border-width-default) solid var(--color-border);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
  white-space: nowrap;
}

.wallet-table tbody tr {
  transition: background-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.wallet-table tbody tr:hover {
  background-color: var(--color-bg-subtle);
}

.wallet-table__cell {
  padding: var(--primitive-space-4);
  color: var(--color-fg);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
  vertical-align: top;
}

.wallet-table__cell--nowrap {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.wallet-table__description {
  max-width: 22rem;
  overflow-wrap: anywhere;
}

.wallet-table__amount {
  color: var(--color-success);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-body);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.wallet-table__amount.is-debit {
  color: var(--color-warning);
}

@media (max-width: 1100px) {
  .wallet-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .wallet-overview {
    grid-template-columns: minmax(0, 1fr);
  }

  .wallet-recharge__tiers {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .wallet-stats,
  .wallet-recharge__tiers {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
