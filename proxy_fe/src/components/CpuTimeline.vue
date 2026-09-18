<script setup lang="ts">
import { computed } from 'vue';
import type { RunResult } from '../api/types';
import { describeLeg } from '../format';

const props = defineProps<{ readonly results: readonly RunResult[] }>();

const WIDTH = 520;
const HEIGHT = 200;
const COLOURS = ['#0284c7', '#ea580c', '#16a34a', '#9333ea', '#dc2626'] as const;

const traced = computed(() => props.results.filter((result) => result.timeline.length > 0));

const bounds = computed(() => {
  const points = traced.value.flatMap((result) => result.timeline);
  return {
    time: Math.max(...points.map((point) => point.t_s), 0.001),
    cpu: Math.max(...points.map((point) => point.cpu_percent), 100),
  };
});

function pathFor(result: RunResult): string {
  return result.timeline
    .map((point, index) => {
      const x = (point.t_s / bounds.value.time) * WIDTH;
      const y = HEIGHT - (point.cpu_percent / bounds.value.cpu) * HEIGHT;
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}
</script>

<template>
  <figure v-if="traced.length > 0" class="my-4">
    <figcaption class="mb-2 text-sm font-semibold text-slate-700">
      Processor utilisation over time
      <span class="font-normal text-slate-500">
        - a flat line near 100% is one core; higher plateaus are real parallelism
      </span>
    </figcaption>
    <svg :width="WIDTH" :height="HEIGHT" role="img" aria-label="CPU over time" class="max-w-full">
      <line :x1="0" :y1="HEIGHT" :x2="WIDTH" :y2="HEIGHT" class="stroke-slate-300" />
      <path
        v-for="(result, index) in traced"
        :key="result.leg.leg_id"
        data-testid="timeline-path"
        :d="pathFor(result)"
        fill="none"
        stroke-width="2"
        :stroke="COLOURS[index % COLOURS.length]"
      />
    </svg>
    <ul class="mt-1 flex flex-wrap gap-4 text-xs text-slate-600">
      <li v-for="(result, index) in traced" :key="result.leg.leg_id" class="flex items-center gap-1">
        <span
          class="inline-block h-2 w-4 rounded"
          :style="{ backgroundColor: COLOURS[index % COLOURS.length] }"
        />
        {{ describeLeg(result.leg) }}
      </li>
    </ul>
  </figure>
</template>
