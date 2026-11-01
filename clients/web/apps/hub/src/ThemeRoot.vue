<script setup lang="ts">
import App from './App.vue'
</script>

<template>
  <App />
</template>


<script lang="ts">
import {useTheme} from "@/theme/useTheme.ts";

useTheme().setTheme("quest")
</script>
