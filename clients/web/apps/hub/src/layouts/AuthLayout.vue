<script setup lang="ts">
import UiBrandMark from '@/components/ui/UiBrandMark.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import { MODULE_CATALOG } from '@/models/modules'

const capabilities = [
  { icon: 'shield' as const, label: '统一身份与 RBAC 权限' },
  { icon: 'key' as const, label: '会话与刷新令牌管理' },
  { icon: 'overview' as const, label: '钱包 / 订单 / 广场模块' },
]
</script>

<template>
  <div class="auth-layout">
    <section class="auth-layout__brand">
      <div class="auth-layout__brand-inner">
        <div class="auth-layout__brand-row">
          <UiBrandMark :size="42" />
          <div class="auth-layout__brand-copy">
            <p class="auth-layout__wordmark">STELLERA</p>
            <p class="auth-layout__submark">HUB CONSOLE</p>
          </div>
        </div>

        <p class="hub-eyebrow auth-layout__eyebrow">ACCESS PORTAL</p>
        <h1 class="auth-layout__title">企业控制台</h1>
        <p class="auth-layout__lead">统一管理钱包、订单与广场的业务入口。</p>

        <ul class="auth-layout__capabilities" aria-label="控制台能力">
          <li v-for="capability in capabilities" :key="capability.label">
            <UiIcon :name="capability.icon" :size="18" />
            <span>{{ capability.label }}</span>
          </li>
        </ul>

        <ul class="auth-layout__modules" aria-label="业务模块">
          <li v-for="module in MODULE_CATALOG" :key="module.key">
            <UiChip>{{ module.label }}</UiChip>
          </li>
        </ul>

        <p class="auth-layout__footnote">企业内网 · 仅限授权人员访问</p>
      </div>
    </section>

    <section class="auth-layout__form" aria-label="登录">
      <div class="auth-layout__form-inner">
        <slot />
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth-layout {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  min-height: 100vh;
  background-color: var(--color-bg);
}

.auth-layout__brand {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(2rem, 5vw, 4.5rem);
  background-color: var(--color-bg);
  background-image:
    linear-gradient(rgb(255 255 255 / 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgb(255 255 255 / 0.025) 1px, transparent 1px);
  background-size: 80px 80px;
  border-right: var(--border-width-default) solid var(--color-border);
  overflow: hidden;
}

.auth-layout__brand-inner {
  width: 100%;
  max-width: 30rem;
}

.auth-layout__brand-row {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-3);
}

.auth-layout__brand-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auth-layout__wordmark {
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: 1.25rem;
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.08em;
  line-height: 1;
}

.auth-layout__submark {
  color: var(--color-fg-muted);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  letter-spacing: var(--font-letter-spacing-label);
  line-height: 1.2;
}

.auth-layout__eyebrow {
  margin-top: clamp(2.5rem, 4vw, 4rem);
}

.auth-layout__title {
  margin-top: var(--primitive-space-5);
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h1);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.03em;
  line-height: var(--font-line-height-h1);
}

.auth-layout__lead {
  max-width: 56ch;
  margin-top: var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-body-lg);
  line-height: 1.65;
}

.auth-layout__capabilities {
  display: flex;
  flex-direction: column;
  margin-top: var(--primitive-space-8);
}

.auth-layout__capabilities li {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-3) 0;
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.auth-layout__capabilities li:first-child {
  border-top: 0;
}

.auth-layout__capabilities .ui-icon {
  color: var(--color-accent);
}

.auth-layout__modules {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2);
  margin-top: var(--primitive-space-6);
}

.auth-layout__footnote {
  margin-top: var(--primitive-space-12);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  letter-spacing: 0.01em;
}

.auth-layout__form {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(2rem, 5vw, 4rem);
  background-color: var(--color-bg);
}

.auth-layout__form-inner {
  width: 100%;
  max-width: 26.25rem;
}

@media (max-width: 900px) {
  .auth-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .auth-layout__brand {
    padding: var(--primitive-space-8) var(--primitive-space-6);
    border-right: 0;
    border-bottom: var(--border-width-default) solid var(--color-border);
  }

  .auth-layout__brand-inner {
    max-width: none;
  }

  .auth-layout__eyebrow {
    margin-top: var(--primitive-space-8);
  }

  .auth-layout__title {
    font-size: clamp(2rem, 1.65rem + 1.6vw, 2.75rem);
  }

  .auth-layout__lead {
    font-size: var(--font-size-body);
  }

  /* Mobile: keep the form reachable — shorten the narrative to brand + title + lead. */
  .auth-layout__capabilities,
  .auth-layout__modules,
  .auth-layout__footnote {
    display: none;
  }

  .auth-layout__form {
    padding: var(--primitive-space-8) var(--primitive-space-4) var(--primitive-space-12);
  }
}
</style>
