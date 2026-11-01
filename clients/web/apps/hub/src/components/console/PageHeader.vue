<script setup lang="ts">
interface PageHeaderProps {
  eyebrow?: string
  title: string
  description?: string
}

withDefaults(defineProps<PageHeaderProps>(), {
  eyebrow: undefined,
  description: undefined,
})
</script>

<template>
  <header class="page-header">
    <div class="page-header__copy">
      <p v-if="eyebrow" class="hub-eyebrow">{{ eyebrow }}</p>
      <h1 class="page-header__title">{{ title }}</h1>
      <p v-if="description" class="page-header__description">{{ description }}</p>
      <slot name="meta" />
    </div>
    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--primitive-space-4);
}

.page-header__copy {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
  min-width: 0;
}

.page-header__title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.02em;
}

.page-header__description {
  max-width: 60ch;
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.page-header__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-3);
}
</style>
