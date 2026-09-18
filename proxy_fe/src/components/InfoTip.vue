<script setup lang="ts">
defineProps<{ readonly text: string }>();
</script>

<template>
  <span
    data-testid="info-tip"
    class="ml-1 cursor-help border-b border-dotted border-slate-400 text-slate-400"
    :title="text"
    >?</span
  >
</template>
