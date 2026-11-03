<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { BffError } from '@/bff/errors'
import { profileBff } from '@/bff/profile'
import PageHeader from '@/components/console/PageHeader.vue'
import CertificationMark from '@/components/identity/CertificationMark.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import type { PublicProfileView } from '@/models'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const viewer = computed(() => auth.viewer)
const viewerId = computed(() => auth.viewer?.id ?? '')

const profile = ref<PublicProfileView | null>(null)
const loading = ref(true)
const errorMessage = ref('')

const isSelf = computed(() => Boolean(profile.value && profile.value.id === viewerId.value))

function toErrorMessage(error: unknown): string {
  if (!(error instanceof BffError)) return '公开主页加载失败，请稍后重试。'

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'not-found':
      return '该用户不存在，或公开主页已被移除。'
    case 'forbidden':
      return '无法查看该用户的公开主页。'
    case 'network':
      return '无法连接到服务，请检查网络后重试。'
    case 'server':
      return '服务暂时不可用，请稍后再试。'
    case 'malformed-response':
      return '服务返回的数据格式异常，请联系管理员。'
    default:
      return error.message || '公开主页加载失败，请稍后重试。'
  }
}

async function loadProfile(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const userId = String(route.params.id ?? '')
    profile.value = await profileBff.getPublicProfile(userId)
  } catch (error) {
    profile.value = null
    errorMessage.value = toErrorMessage(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadProfile()
})

watch(
  () => route.params.id,
  () => {
    if (route.name === 'public-profile') void loadProfile()
  },
)
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="public-profile">
      <PageHeader eyebrow="PUBLIC PROFILE" title="公开主页">
        <template #actions>
          <RouterLink v-if="isSelf" class="public-profile__link-button" :to="{ name: 'profile' }">
            编辑个人信息
            <UiIcon name="arrow-right" :size="16" />
          </RouterLink>
        </template>
      </PageHeader>

      <div v-if="loading" class="public-profile__state" role="status" aria-live="polite">
        正在加载公开主页…
      </div>

      <div v-else-if="errorMessage" class="public-profile__state public-profile__state--error">
        <UiAlert variant="error" title="公开主页加载失败">{{ errorMessage }}</UiAlert>
        <UiButton variant="secondary" size="sm" @click="loadProfile">重试</UiButton>
      </div>

      <template v-else-if="profile">
        <UiCard padding="lg" class="public-profile__hero">
          <div class="public-profile__identity">
            <span class="public-profile__avatar" aria-hidden="true">
              {{ profile.nickname.slice(0, 2) || '?' }}
            </span>
            <div class="public-profile__copy">
              <div class="public-profile__name-row">
                <h1 class="public-profile__name">{{ profile.nickname }}</h1>
                <CertificationMark :certifications="profile.certifications" />
              </div>
              <p class="public-profile__meta">
                <span v-if="profile.city">{{ profile.city }}</span>
                <span v-if="profile.city" aria-hidden="true">·</span>
                <span>加入于 {{ profile.memberSinceLabel }}</span>
              </p>
              <p v-if="profile.bio" class="public-profile__bio">{{ profile.bio }}</p>
            </div>
          </div>
          <div v-if="profile.skills.length" class="public-profile__skills">
            <UiChip v-for="skill in profile.skills" :key="skill">{{ skill }}</UiChip>
          </div>
        </UiCard>

        <UiCard padding="lg" class="public-profile__section">
          <header class="public-profile__section-head">
            <h2 class="public-profile__section-title">合作记录</h2>
            <p class="public-profile__section-hint">该用户已完成的平台合作订单。</p>
          </header>

          <div class="public-profile__stats">
            <div class="public-profile__stat">
              <p class="public-profile__stat-value">{{ profile.cooperation.completedCount }}</p>
              <p class="public-profile__stat-label">完成单数</p>
            </div>
            <div class="public-profile__stat">
              <p class="public-profile__stat-value">{{ profile.cooperation.partnerCount }}</p>
              <p class="public-profile__stat-label">合作方</p>
            </div>
            <div class="public-profile__stat">
              <p class="public-profile__stat-value public-profile__stat-value--money">
                {{ profile.cooperation.totalAmountLabel }}
              </p>
              <p class="public-profile__stat-label">累计金额</p>
            </div>
          </div>

          <p v-if="profile.cooperation.records.length === 0" class="public-profile__empty">
            暂无已完成的合作订单。
          </p>
          <ul v-else class="public-profile__records">
            <li v-for="record in profile.cooperation.records" :key="record.orderId">
              <RouterLink
                class="public-profile__record"
                :to="{ name: 'fde-order-detail', params: { id: record.orderId } }"
              >
                <div>
                  <p class="public-profile__record-title">{{ record.title }}</p>
                  <p class="public-profile__record-meta">
                    {{ record.code }} · {{ record.roleLabel }} · 完成于
                    {{ record.completedAtLabel }}
                  </p>
                </div>
                <span class="public-profile__record-amount">{{ record.priceLabel }}</span>
              </RouterLink>
            </li>
          </ul>
        </UiCard>
      </template>
    </div>
  </ConsoleLayout>
</template>

<style scoped>
.public-profile {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.public-profile__link-button {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
  min-height: 44px;
  padding: 0 var(--primitive-space-5);
  color: var(--color-fg);
  background: var(--obsidian-surface-glass);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}

.public-profile__link-button:hover {
  border-color: var(--color-accent);
  text-decoration: none;
}

.public-profile__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.public-profile__state--error {
  flex-direction: column;
  align-items: flex-start;
}

.public-profile__hero {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.public-profile__identity {
  display: flex;
  align-items: flex-start;
  gap: var(--primitive-space-4);
}

.public-profile__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  flex: none;
  color: var(--color-accent);
  background-color: var(--color-accent-subtle);
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-pill);
  font-size: var(--font-size-body);
}

.public-profile__copy {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
  min-width: 0;
}

.public-profile__name-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.public-profile__name {
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.02em;
}

.public-profile__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.public-profile__bio {
  max-width: 62ch;
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.7;
}

.public-profile__skills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2);
}

.public-profile__section {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.public-profile__section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--primitive-space-1) var(--primitive-space-3);
}

.public-profile__section-title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
}

.public-profile__section-hint,
.public-profile__empty {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.public-profile__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.public-profile__stat {
  padding: var(--primitive-space-4);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.public-profile__stat-value {
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h2);
  font-variant-numeric: tabular-nums;
  font-weight: var(--font-weight-medium);
  line-height: 1.1;
}

.public-profile__stat-value--money {
  color: var(--obsidian-gold-text);
  font-size: var(--font-size-h3);
}

.public-profile__stat-label {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.public-profile__records {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
}

.public-profile__record {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-3) var(--primitive-space-4);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.public-profile__record:hover {
  border-color: var(--color-accent-border);
  text-decoration: none;
}

.public-profile__record-title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
}

.public-profile__record-meta {
  margin-top: 2px;
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.public-profile__record-amount {
  color: var(--obsidian-gold-text);
  font-family: var(--font-family-heading);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 760px) {
  .public-profile__stats {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
