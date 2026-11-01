<script setup lang="ts">
import { useRouter } from 'vue-router'

import UiBrandMark from '@/components/ui/UiBrandMark.vue'
import UiButton from '@/components/ui/UiButton.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

function goHome(): void {
  void router.replace(auth.isAuthenticated ? { name: 'intro' } : { name: 'login' })
}
</script>

<template>
  <main class="not-found">
    <UiBrandMark :size="64" title="STELLERA HUB" />
    <p class="not-found__code">404</p>
    <h1 class="not-found__title">页面不存在</h1>
    <p class="not-found__message">你访问的页面可能已被移动或删除，请返回工作台继续操作。</p>
    <div class="not-found__actions">
      <UiButton @click="goHome">{{ auth.isAuthenticated ? '返回平台简介' : '前往登录' }}</UiButton>
    </div>
  </main>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-3);
  min-height: 100vh;
  padding: var(--primitive-space-8);
  background-color: var(--color-bg);
  text-align: center;
}

.not-found__code {
  color: var(--color-accent);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: 0.24em;
}

.not-found__title {
  font-size: var(--font-size-h1);
  letter-spacing: -0.02em;
}

.not-found__message {
  max-width: 26rem;
  color: var(--color-fg-muted);
  font-size: var(--font-size-body);
}

.not-found__actions {
  display: flex;
  gap: var(--primitive-space-3);
  margin-top: var(--primitive-space-4);
}
</style>
