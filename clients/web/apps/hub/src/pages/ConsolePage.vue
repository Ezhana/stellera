<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { buildConsolePageModel } from '@/bff/console'
import UiCard from '@/components/ui/UiCard.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const loggingOut = ref(false)

const model = computed(() => {
  const viewer = auth.viewer
  return viewer ? buildConsolePageModel(viewer) : null
})

const metrics = computed(() => {
  if (!model.value) return []
  return [
    { label: '角色', value: String(model.value.summary.roleCount), hint: '已分配角色' },
    { label: '权限项', value: String(model.value.summary.permissionCount), hint: 'Casbin 授权项' },
    {
      label: '可读模块',
      value: String(model.value.summary.readableModuleCount),
      hint: '含只读与可写',
    },
    {
      label: '可写模块',
      value: String(model.value.summary.writableModuleCount),
      hint: '可执行写操作',
    },
  ]
})

async function handleLogout(): Promise<void> {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await auth.logout()
  } finally {
    await router.replace({ name: 'login' })
    loggingOut.value = false
  }
}
</script>

<template>
  <ConsoleLayout
    v-if="model"
    :viewer="model.viewer"
    :modules="model.modules"
    :logging-out="loggingOut"
    active-key="overview"
    @logout="handleLogout"
  >
    <div class="console-page">
      <header class="console-page__header">
        <div class="console-page__header-copy">
          <p class="hub-eyebrow">OVERVIEW</p>
          <h1 class="console-page__title">控制台总览</h1>
          <p class="console-page__subtitle">身份、权限与业务模块概览。</p>
        </div>
        <UiChip variant="success">已登录</UiChip>
      </header>

      <UiCard padding="none" class="console-page__stats">
        <div class="console-page__metrics" role="list" aria-label="账户概览">
          <div
            v-for="metric in metrics"
            :key="metric.label"
            class="console-page__metric"
            role="listitem"
          >
            <p class="console-page__metric-label">{{ metric.label }}</p>
            <p class="console-page__metric-value">{{ metric.value }}</p>
            <p class="console-page__metric-hint">{{ metric.hint }}</p>
          </div>
        </div>
      </UiCard>

      <div class="console-page__grid">
        <UiCard class="console-page__identity">
          <div class="console-page__section-head">
            <h2 class="console-page__section-title">账户信息</h2>
            <UiChip :variant="model.viewer.status === 'active' ? 'success' : 'error'">{{
              model.viewer.statusLabel
            }}</UiChip>
          </div>

          <div class="console-page__person">
            <span class="console-page__avatar" aria-hidden="true">{{ model.viewer.initials }}</span>
            <div class="console-page__person-copy">
              <p class="console-page__person-name">{{ model.viewer.displayName }}</p>
              <p class="console-page__person-meta">
                @{{ model.viewer.username }}
                <span aria-hidden="true">·</span>
                {{ model.viewer.email ?? '未登记邮箱' }}
              </p>
            </div>
          </div>

          <dl class="console-page__meta">
            <div>
              <dt>用户 ID</dt>
              <dd>{{ model.viewer.id }}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>{{ model.viewer.statusLabel }}</dd>
            </div>
            <div>
              <dt>管理员</dt>
              <dd>{{ model.viewer.isAdmin ? '是' : '否' }}</dd>
            </div>
          </dl>

          <div class="console-page__block">
            <p class="console-page__block-label">角色</p>
            <ul v-if="model.viewer.roles.length" class="console-page__chips" aria-label="角色">
              <li v-for="role in model.viewer.roles" :key="role.key">
                <UiChip :variant="role.tone">{{ role.label }}</UiChip>
              </li>
            </ul>
            <p v-else class="console-page__empty">暂无角色，请联系管理员分配。</p>
          </div>
        </UiCard>

        <UiCard class="console-page__permissions">
          <div class="console-page__section-head">
            <h2 class="console-page__section-title">权限范围</h2>
            <UiChip>{{ model.viewer.permissionCount }} 项</UiChip>
          </div>

          <ul v-if="model.permissionGroups.length" class="console-page__permission-list">
            <li
              v-for="group in model.permissionGroups"
              :key="group.key"
              class="console-page__permission-row"
            >
              <div class="console-page__permission-head">
                <span class="console-page__permission-label">{{ group.label }}</span>
                <span class="console-page__permission-raw">
                  {{ group.rawObjects.join(' · ') }}
                </span>
              </div>
              <div class="console-page__chips">
                <UiChip v-for="action in group.actions" :key="action.key">
                  {{ action.label }}
                </UiChip>
              </div>
            </li>
          </ul>
          <p v-else class="console-page__empty">暂无授权，请联系管理员分配权限。</p>
        </UiCard>
      </div>

      <section class="console-page__modules" aria-labelledby="console-modules-title">
        <div class="console-page__section-head">
          <h2 id="console-modules-title" class="console-page__section-title">业务模块</h2>
          <UiChip variant="warning">即将上线</UiChip>
        </div>

        <div class="console-page__module-grid">
          <UiCard v-for="module in model.modules" :key="module.key" class="console-page__module">
            <div class="console-page__module-head">
              <span class="console-page__module-icon">
                <UiIcon :name="module.icon" :size="20" />
              </span>
              <UiChip :variant="module.accessTone">{{ module.accessLabel }}</UiChip>
            </div>
            <p class="console-page__module-code">{{ module.code }}</p>
            <h3 class="console-page__module-title">{{ module.label }}</h3>
            <p class="console-page__module-description">{{ module.description }}</p>
            <div class="console-page__module-foot">
              <UiChip variant="warning">{{ module.availabilityLabel }}</UiChip>
            </div>
          </UiCard>
        </div>
      </section>
    </div>
  </ConsoleLayout>

  <div v-else class="console-page console-page--loading">正在加载控制台…</div>
</template>

<style scoped>
.console-page {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-8);
  max-width: var(--hub-content-max);
  margin: 0 auto;
}

.console-page--loading {
  min-height: 60vh;
  align-items: center;
  justify-content: center;
  color: var(--color-fg-muted);
}

.console-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--primitive-space-4);
}

.console-page__header-copy {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
}

.console-page__title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.02em;
}

.console-page__stats {
  overflow: hidden;
}

.console-page__subtitle {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.console-page__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 0;
}

.console-page__metric {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-6);
  border-left: var(--border-width-default) solid var(--color-border-subtle);
}

.console-page__metric:first-child {
  border-left: 0;
}

.console-page__metric-label {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
}

.console-page__metric-value {
  margin: 0;
  color: var(--color-accent-hover);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-medium);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.console-page__metric-hint {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
}

.console-page__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  align-items: start;
  gap: var(--primitive-space-6);
}

.console-page__identity,
.console-page__permissions {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-5);
}

.console-page__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.console-page__section-title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.01em;
}

.console-page__person {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-4);
}

.console-page__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  flex: none;
  color: var(--color-accent);
  background-color: var(--color-accent-subtle);
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-pill);
  font-size: var(--font-size-body-lg);
  font-weight: var(--font-weight-strong);
}

.console-page__person-copy {
  min-width: 0;
}

.console-page__person-name {
  color: var(--color-fg-strong);
  font-size: var(--font-size-body-lg);
  font-weight: var(--font-weight-strong);
  overflow-wrap: anywhere;
}

.console-page__person-meta {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  overflow-wrap: anywhere;
}

.console-page__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
  gap: var(--primitive-space-3);
  margin: 0;
  padding: var(--primitive-space-4);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.console-page__meta dt {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
}

.console-page__meta dd {
  margin: 2px 0 0;
  color: var(--color-fg);
  font-size: var(--font-size-small);
  overflow-wrap: anywhere;
}

.console-page__block {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
}

.console-page__block-label {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
}

.console-page__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2);
}

.console-page__permission-list {
  display: flex;
  flex-direction: column;
}

.console-page__permission-row {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
  padding: var(--primitive-space-3) 0;
  border-bottom: var(--border-width-default) solid var(--color-border-subtle);
}

.console-page__permission-row:last-child {
  border-bottom: 0;
}

.console-page__permission-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--primitive-space-2);
}

.console-page__permission-label {
  color: var(--color-fg);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-strong);
}

.console-page__permission-raw {
  color: var(--obsidian-tertiary-text);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-caption);
  overflow-wrap: anywhere;
}

.console-page__empty {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.console-page__modules {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.console-page__module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: var(--primitive-space-4);
}

.console-page__module {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
  height: 100%;
}

.console-page__module-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
}

.console-page__module-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  color: var(--color-accent);
  background-color: transparent;
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-control);
}

.console-page__module-code {
  margin-top: var(--primitive-space-3);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
}

.console-page__module-title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.01em;
}

.console-page__module-description {
  flex: 1;
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.console-page__module-foot {
  margin-top: var(--primitive-space-3);
  padding-top: var(--primitive-space-3);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

@media (max-width: 1100px) {
  .console-page__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .console-page__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .console-page__metric:nth-child(odd) {
    border-left: 0;
  }

  .console-page__metric:nth-child(n + 3) {
    border-top: var(--border-width-default) solid var(--color-border-subtle);
  }
}

@media (max-width: 600px) {
  .console-page__header {
    flex-direction: column;
  }
}
</style>
