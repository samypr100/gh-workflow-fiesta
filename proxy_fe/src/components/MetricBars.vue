<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  readonly title: string;
  readonly labels: readonly string[];
  readonly values: readonly number[];
  readonly render: (value: number) => string;
}>();

const WIDTH = 520;
const ROW_HEIGHT = 34;
const LABEL_WIDTH = 210;

const maximum = computed(() => Math.max(...props.values, 0) || 1);
const barWidth = (value: number) => ((WIDTH - LABEL_WIDTH - 90) * value) / maximum.value;
</script>

<template>
  <figure class="my-4">
    <figcaption class="mb-2 text-sm font-semibold text-slate-700">{{ title }}</figcaption>
    <svg
      :width="WIDTH"
      :height="labels.length * ROW_HEIGHT"
      role="img"
      :aria-label="title"
      class="max-w-full"
    >
      <g v-for="(label, index) in labels" :key="label">
        <text :x="0" :y="index * ROW_HEIGHT + 20" class="fill-slate-600 text-xs">
          {{ label }}
        </text>
        <rect
          :x="LABEL_WIDTH"
          :y="index * ROW_HEIGHT + 8"
          :width="barWidth(values[index] ?? 0)"
          height="16"
          rx="3"
          class="fill-sky-600"
        />
        <text
          :x="LABEL_WIDTH + barWidth(values[index] ?? 0) + 8"
          :y="index * ROW_HEIGHT + 20"
          class="fill-slate-700 text-xs"
        >
          {{ render(values[index] ?? 0) }}
        </text>
      </g>
    </svg>
  </figure>
</template>
