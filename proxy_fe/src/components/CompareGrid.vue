<script setup lang="ts">
import { computed } from 'vue';
import type { RunResult } from '../api/types';
import { bestIndex, groupedRows, type MetricRow } from '../compare';
import { describeLeg, formatFactor } from '../format';
import CpuTimeline from './CpuTimeline.vue';
import InfoTip from './InfoTip.vue';
import MetricBars from './MetricBars.vue';

const props = defineProps<{ readonly results: readonly RunResult[] }>();

const groups = computed(() => [...groupedRows().entries()]);
const successful = computed(() => props.results.filter((result) => result.scalars !== null));
const labels = computed(() => successful.value.map((result) => describeLeg(result.leg)));
const parallelism = computed(() =>
  successful.value.map((result) => result.scalars?.parallelism_factor.median ?? 0),
);

function winner(row: MetricRow): number | null {
  return bestIndex(row, props.results);
}

function statusNote(result: RunResult): string | null {
  if (result.status === 'timeout') return 'Timed out before finishing';
  if (result.status === 'error') return result.error?.kind ?? 'Failed';
  return null;
}
</script>

<template>
  <section v-if="results.length === 0" class="rounded border border-slate-200 p-8 text-center">
    <p class="text-slate-600">No results yet. Add configurations and run a comparison.</p>
  </section>

  <section v-else class="space-y-6">
    <div class="overflow-x-auto">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th class="w-64 border-b border-slate-300 p-2 text-left text-slate-500">Metric</th>
            <th
              v-for="result in results"
              :key="result.leg.leg_id"
              data-testid="config-column"
              class="border-b border-slate-300 p-2 text-left"
            >
              <div class="font-semibold text-slate-800">{{ describeLeg(result.leg) }}</div>
              <div class="text-xs font-normal text-slate-500">
                {{ result.leg.execution_model }}, {{ result.leg.params.workers }} workers
              </div>
              <div v-if="statusNote(result)" class="mt-1 text-xs font-medium text-amber-700">
                {{ statusNote(result) }}
                <span v-if="result.error" class="block font-normal text-slate-500">
                  {{ result.error.message }}
                </span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="[group, rows] in groups" :key="group">
            <tr>
              <th
                :colspan="results.length + 1"
                class="bg-slate-50 p-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"
              >
                {{ group }}
              </th>
            </tr>
            <tr v-for="row in rows" :key="row.key" class="border-b border-slate-100">
              <th class="p-2 text-left font-medium text-slate-700">
                {{ row.label }}
                <InfoTip :text="row.explainer" />
              </th>
              <td
                v-for="(result, index) in results"
                :key="result.leg.leg_id"
                :data-testid="winner(row) === index ? 'best-cell' : 'cell'"
                class="p-2"
                :class="winner(row) === index ? 'bg-emerald-50 font-semibold text-emerald-900' : ''"
              >
                {{ row.render(result) }}
                <span
                  v-if="row.spread && row.spread(result)"
                  class="block text-xs font-normal text-slate-400"
                >
                  {{ row.spread(result) }}
                </span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <MetricBars
      v-if="successful.length > 0"
      title="Parallelism factor - higher means more cores genuinely busy"
      :labels="labels"
      :values="parallelism"
      :render="formatFactor"
    />
    <CpuTimeline :results="results" />
  </section>
</template>
