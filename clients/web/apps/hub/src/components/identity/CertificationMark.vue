<script setup lang="ts">
import { computed } from 'vue'

import UiChip from '@/components/ui/UiChip.vue'
import { describeCertification, type Certification } from '@/models'

interface CertificationMarkProps {
  certification?: Certification
}

const props = withDefaults(defineProps<CertificationMarkProps>(), {
  certification: null,
})

const meta = computed(() => describeCertification(props.certification))
</script>

<template>
  <UiChip v-if="meta" class="certification-mark" :variant="meta.tone">{{ meta.label }}</UiChip>
</template>
