<script setup lang="ts">
import { computed } from 'vue'

import UiChip from '@/components/ui/UiChip.vue'
import { describeCertification, type Certification, type CertificationMeta } from '@/models'

interface CertificationMarkProps {
  certifications?: readonly Certification[]
}

const props = withDefaults(defineProps<CertificationMarkProps>(), {
  certifications: () => [],
})

const metas = computed<CertificationMeta[]>(() =>
  props.certifications
    .map((certification) => describeCertification(certification))
    .filter((meta): meta is CertificationMeta => Boolean(meta)),
)
</script>

<template>
  <span v-if="metas.length" class="certification-mark">
    <UiChip v-for="meta in metas" :key="meta.certification" :variant="meta.tone">
      {{ meta.label }}
    </UiChip>
  </span>
</template>

<style scoped>
.certification-mark {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
}
</style>
