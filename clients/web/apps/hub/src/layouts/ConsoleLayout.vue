<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import CertificationMark from '@/components/identity/CertificationMark.vue'
import UiBrandMark from '@/components/ui/UiBrandMark.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import { CONSOLE_NAV, findNavGroupForRoute, navForViewer, type ViewerProfile } from '@/models'
import { useAuthStore } from '@/stores/auth'

interface ConsoleLayoutProps {
  viewer: ViewerProfile
}

const props = defineProps<ConsoleLayoutProps>()

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const loggingOut = ref(false)
const groups = computed(() => navForViewer({ isAdmin: props.viewer.isAdmin }))
const expandedGroups = ref<Record<string, boolean>>(
  Object.fromEntries(CONSOLE_NAV.map((group) => [group.key, true])),
)

const active = computed(() => findNavGroupForRoute(route.name, groups.value))

/** Keep the group that owns the current route open, even after a manual collapse. */
watch(
  () => active.value?.group.key,
  (groupKey) => {
    if (groupKey) expandedGroups.value = { ...expandedGroups.value, [groupKey]: true }
  },
)

function toggleGroup(groupKey: string): void {
  expandedGroups.value = {
    ...expandedGroups.value,
    [groupKey]: !expandedGroups.value[groupKey],
  }
}

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
  <div class="console-layout">
    <aside class="console-layout__sidebar">
      <div class="console-layout__brand">
        <UiBrandMark :size="36" />
        <div class="console-layout__brand-copy">
          <p class="console-layout__wordmark">STELLERA</p>
          <p class="console-layout__submark">FDE CONSOLE</p>
        </div>
      </div>

      <nav class="console-layout__nav" aria-label="主导航">
        <p class="console-layout__nav-title">工作台</p>

        <div
          v-for="group in groups"
          :key="group.key"
          class="console-layout__nav-group"
          :class="{ 'is-active-group': active?.group.key === group.key }"
        >
          <button
            class="console-layout__nav-group-toggle"
            type="button"
            :aria-expanded="expandedGroups[group.key] ? 'true' : 'false'"
            :aria-controls="`console-nav-${group.key}`"
            @click="toggleGroup(group.key)"
          >
            <UiIcon :name="group.icon" :size="18" />
            <span class="console-layout__nav-group-label">{{ group.label }}</span>
            <UiIcon
              class="console-layout__nav-group-chevron"
              :class="{ 'is-open': expandedGroups[group.key] }"
              name="chevron"
              :size="14"
            />
          </button>

          <ul
            v-show="expandedGroups[group.key]"
            :id="`console-nav-${group.key}`"
            class="console-layout__nav-list"
          >
            <li v-for="leaf in group.children" :key="leaf.key">
              <RouterLink
                :to="{ name: leaf.routeName }"
                class="console-layout__nav-item"
                :class="{ 'is-active': active?.leaf.key === leaf.key }"
                :aria-current="active?.leaf.key === leaf.key ? 'page' : undefined"
              >
                <UiIcon :name="leaf.icon" :size="17" />
                <span class="console-layout__nav-label">{{ leaf.label }}</span>
                <span v-if="leaf.meta" class="console-layout__nav-meta">
                  <span class="console-layout__live-dot" aria-hidden="true" />
                  {{ leaf.meta }}
                </span>
              </RouterLink>
            </li>
          </ul>
        </div>
      </nav>

      <div class="console-layout__account">
        <div class="console-layout__identity">
          <span class="console-layout__avatar" aria-hidden="true">{{ viewer.initials }}</span>
          <div class="console-layout__identity-copy">
            <p class="console-layout__account-name">{{ viewer.displayName }}</p>
            <p class="console-layout__account-meta">{{ viewer.email ?? '未登记邮箱' }}</p>
          </div>
        </div>

        <div v-if="viewer.certification" class="console-layout__certification">
          <CertificationMark :certification="viewer.certification" />
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
          @click="handleLogout"
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
  min-width: 0;
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
  margin-bottom: var(--primitive-space-3);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-transform: uppercase;
}

.console-layout__nav-group + .console-layout__nav-group {
  margin-top: var(--primitive-space-4);
}

.console-layout__nav-group-toggle {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-3);
  width: 100%;
  padding: var(--primitive-space-1) var(--primitive-space-2);
  color: var(--obsidian-tertiary-text);
  background: transparent;
  border: 0;
  border-radius: var(--radius-small);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
  text-align: left;
  text-transform: uppercase;
  transition: color var(--motion-duration-normal) var(--motion-easing-standard);
}

.console-layout__nav-group-toggle:hover,
.console-layout__nav-group.is-active-group .console-layout__nav-group-toggle {
  color: var(--color-fg-muted);
}

.console-layout__nav-group-label {
  flex: 1;
}

.console-layout__nav-group-chevron {
  transform: rotate(90deg);
  transition: transform var(--motion-duration-normal) var(--motion-easing-standard);
}

.console-layout__nav-group-chevron.is-open {
  transform: rotate(270deg);
}

.console-layout__nav-list {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
  margin-top: var(--primitive-space-1);
}

.console-layout__nav-item {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-3);
  min-height: 40px;
  padding: 8px 12px 8px 14px;
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
  text-decoration: none;
}

.console-layout__nav-item.is-active {
  color: var(--color-fg-strong);
  background-color: var(--color-accent-subtle);
  border-color: transparent;
  box-shadow: inset 2px 0 0 var(--color-accent);
}

.console-layout__nav-item.is-active .ui-icon {
  color: var(--color-accent-hover);
}

.console-layout__nav-label {
  flex: 1;
}

.console-layout__nav-meta {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-1);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  letter-spacing: 0.01em;
}

.console-layout__live-dot {
  width: 6px;
  height: 6px;
  flex: none;
  background-color: var(--color-success);
  border-radius: var(--radius-pill);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-success) 18%, transparent);
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

.console-layout__certification {
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
    gap: var(--primitive-space-4);
    padding: var(--primitive-space-5) var(--primitive-space-4);
    border-right: 0;
    border-bottom: var(--border-width-default) solid var(--color-border);
  }

  .console-layout__brand {
    padding-bottom: var(--primitive-space-4);
  }

  .console-layout__nav {
    display: flex;
    flex-wrap: wrap;
    gap: var(--primitive-space-3);
  }

  .console-layout__nav-title {
    display: none;
  }

  .console-layout__nav-group {
    flex: 1 1 14rem;
  }

  .console-layout__nav-group + .console-layout__nav-group {
    margin-top: 0;
  }

  .console-layout__nav-list {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .console-layout__nav-item {
    flex: 1 1 9rem;
  }

  .console-layout__account {
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--primitive-space-3);
    margin-top: var(--primitive-space-1);
    padding-top: var(--primitive-space-4);
  }

  .console-layout__identity {
    flex: 1 1 12rem;
  }

  .console-layout__roles {
    display: none;
  }

  .console-layout__logout {
    margin-left: auto;
  }

  .console-layout__main {
    padding: var(--primitive-space-6) var(--primitive-space-4) var(--primitive-space-12);
  }
}
</style>
