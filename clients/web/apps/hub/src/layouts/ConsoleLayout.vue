<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import UiBrandMark from '@/components/ui/UiBrandMark.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import type { IconName, ModuleView, ViewerProfile } from '@/models'

interface ConsoleLayoutProps {
  viewer: ViewerProfile
  modules: ModuleView[]
  activeKey?: string
  loggingOut?: boolean
}

const props = withDefaults(defineProps<ConsoleLayoutProps>(), {
  activeKey: 'overview',
  loggingOut: false,
})

defineEmits<{ logout: [] }>()

interface NavItem {
  key: string
  label: string
  icon: IconName
  access?: string
}

const navItems = computed<NavItem[]>(() => [
  { key: 'overview', label: '总览', icon: 'overview' },
  ...props.modules.map((module) => ({
    key: module.key,
    label: module.label,
    icon: module.icon,
    access: module.accessLabel,
  })),
])
</script>

<template>
  <div class="console-layout">
    <aside class="console-layout__sidebar">
      <div class="console-layout__brand">
        <UiBrandMark :size="36" />
        <div class="console-layout__brand-copy">
          <p class="console-layout__wordmark">STELLERA</p>
          <p class="console-layout__submark">HUB CONSOLE</p>
        </div>
      </div>

      <nav class="console-layout__nav" aria-label="主导航">
        <p class="console-layout__nav-title">工作台</p>
        <ul class="console-layout__nav-list">
          <li v-for="item in navItems" :key="item.key">
            <RouterLink
              v-if="item.key === 'overview'"
              :to="{ name: 'console' }"
              class="console-layout__nav-item"
              :class="{ 'is-active': activeKey === 'overview' }"
              :aria-current="activeKey === 'overview' ? 'page' : undefined"
            >
              <UiIcon :name="item.icon" :size="18" />
              <span class="console-layout__nav-label">{{ item.label }}</span>
            </RouterLink>

            <span v-else class="console-layout__nav-item console-layout__nav-item--planned">
              <UiIcon :name="item.icon" :size="18" />
              <span class="console-layout__nav-label">{{ item.label }}</span>
              <span v-if="item.access" class="console-layout__nav-meta">{{ item.access }}</span>
            </span>
          </li>
        </ul>
      </nav>

      <div class="console-layout__account">
        <div class="console-layout__identity">
          <span class="console-layout__avatar" aria-hidden="true">{{ viewer.initials }}</span>
          <div class="console-layout__identity-copy">
            <p class="console-layout__account-name">{{ viewer.displayName }}</p>
            <p class="console-layout__account-meta">{{ viewer.email ?? '未登记邮箱' }}</p>
          </div>
        </div>

        <ul v-if="viewer.roles.length" class="console-layout__roles" aria-label="角色">
          <li v-for="role in viewer.roles" :key="role.key">
            <UiChip :variant="role.tone">{{ role.label }}</UiChip>
          </li>
        </ul>
        <p v-else class="console-layout__account-meta">暂未分配角色</p>

        <UiButton
          class="console-layout__logout"
          variant="ghost"
          size="sm"
          :loading="loggingOut"
          @click="$emit('logout')"
        >
          <UiIcon name="logout" :size="16" />
          退出登录
        </UiButton>
      </div>
    </aside>

    <main class="console-layout__main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.console-layout {
  display: grid;
  grid-template-columns: var(--hub-sidebar-width) minmax(0, 1fr);
  min-height: 100vh;
  background-color: var(--color-bg);
}

.console-layout__sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-8);
  height: 100vh;
  padding: var(--primitive-space-6);
  overflow-y: auto;
  background-color: var(--color-surface);
  border-right: var(--border-width-default) solid var(--color-border);
}

.console-layout__brand {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-3);
  padding-bottom: var(--primitive-space-5);
  border-bottom: var(--border-width-default) solid var(--color-border-subtle);
}

.console-layout__brand-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.console-layout__wordmark {
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.06em;
  line-height: 1.1;
}

.console-layout__submark {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  letter-spacing: var(--font-letter-spacing-label);
  line-height: 1.2;
}

.console-layout__nav-title {
  margin-bottom: var(--primitive-space-2);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
}

.console-layout__nav-list {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
}

.console-layout__nav-item {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-3);
  min-height: 40px;
  padding: 8px 12px;
  color: var(--color-fg-muted);
  border: var(--border-width-default) solid transparent;
  border-radius: var(--radius-control);
  font-size: 0.9375rem;
  font-weight: var(--font-weight-medium);
  text-decoration: none;
  transition:
    color var(--motion-duration-normal) var(--motion-easing-standard),
    background-color var(--motion-duration-normal) var(--motion-easing-standard),
    border-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.console-layout__nav-item:hover {
  color: var(--color-fg);
  background-color: var(--color-bg-subtle);
}

.console-layout__nav-item.is-active {
  color: var(--color-fg-strong);
  background-color: var(--color-accent-subtle);
  border-color: transparent;
  box-shadow: inset 1px 0 0 var(--color-accent);
}

.console-layout__nav-item.is-active .ui-icon {
  color: var(--color-accent-hover);
}

.console-layout__nav-item--planned {
  cursor: default;
}

.console-layout__nav-item--planned:hover {
  background-color: transparent;
  color: var(--color-fg-muted);
}

.console-layout__nav-label {
  flex: 1;
}

.console-layout__nav-meta {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  letter-spacing: 0.01em;
}

.console-layout__account {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  margin-top: auto;
  padding-top: var(--primitive-space-5);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.console-layout__identity {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-3);
}

.console-layout__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex: none;
  color: var(--color-accent);
  background-color: var(--color-accent-subtle);
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-pill);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.02em;
}

.console-layout__identity-copy {
  min-width: 0;
}

.console-layout__account-name {
  color: var(--color-fg-strong);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  overflow-wrap: anywhere;
}

.console-layout__account-meta {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  overflow-wrap: anywhere;
}

.console-layout__roles {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
}

.console-layout__logout {
  justify-content: flex-start;
  align-self: flex-start;
}

.console-layout__main {
  min-width: 0;
  padding: var(--hub-gutter);
}

@media (max-width: 900px) {
  .console-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .console-layout__sidebar {
    position: static;
    height: auto;
    gap: var(--primitive-space-5);
    border-right: 0;
    border-bottom: var(--border-width-default) solid var(--color-border);
  }

  .console-layout__nav-list {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .console-layout__nav-item {
    flex: 1 1 9rem;
  }

  .console-layout__account {
    margin-top: var(--primitive-space-2);
  }

  .console-layout__main {
    padding: var(--primitive-space-6) var(--primitive-space-4) var(--primitive-space-12);
  }
}
</style>
