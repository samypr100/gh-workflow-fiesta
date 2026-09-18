<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { ApiError, createClient } from './api/client';
import type {
  CatalogResponse,
  InterpreterOption,
  RunStatusResponse,
  RunnerInfo,
  SelectionRequest,
} from './api/types';
import CompareGrid from './components/CompareGrid.vue';
import ConfigureView from './components/ConfigureView.vue';
import { loadHistory, recordSubmission, type StoredSubmission } from './stores/history';
import { pollIntervalMs, shouldKeepPolling } from './usePolling';

const BASE_URL = process.env.PUBLIC_API_URL ?? 'http://localhost:8000';
const client = createClient(BASE_URL);

const catalog = ref<CatalogResponse | null>(null);
const interpreters = ref<InterpreterOption[]>([]);
const runners = ref<RunnerInfo[]>([]);
const selections = ref<SelectionRequest[]>([]);
const status = ref<RunStatusResponse | null>(null);
const history = ref<StoredSubmission[]>([]);
const message = ref<string | null>(null);
const busy = ref(false);

let timer: ReturnType<typeof setTimeout> | null = null;

onMounted(async () => {
  history.value = loadHistory(window.localStorage);
  try {
    const [loadedCatalog, loadedInterpreters, loadedRunners] = await Promise.all([
      client.catalog(),
      client.interpreters(),
      client.runners(),
    ]);
    catalog.value = loadedCatalog;
    interpreters.value = [...loadedInterpreters.interpreters];
    runners.value = [...loadedRunners.runners];
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : 'Could not reach the API';
  }
});

onUnmounted(() => {
  if (timer !== null) clearTimeout(timer);
});

function poll(runToken: string, attempt: number): void {
  timer = setTimeout(async () => {
    try {
      const incoming = await client.runStatus(runToken);
      status.value = incoming;
      if (shouldKeepPolling(incoming)) poll(runToken, attempt + 1);
      else busy.value = false;
    } catch {
      poll(runToken, attempt + 1);
    }
  }, pollIntervalMs(attempt));
}

async function submit(): Promise<void> {
  message.value = null;
  busy.value = true;
  try {
    const created = await client.createRun(selections.value);
    recordSubmission(window.localStorage, {
      run_token: created.run_token,
      created_at: Date.now(),
      leg_count: created.leg_count,
      selections: [...selections.value],
    });
    history.value = loadHistory(window.localStorage);
    status.value = { phase: 'pending', expected_legs: created.leg_count, results: [], detail: null };
    poll(created.run_token, 0);
  } catch (error) {
    busy.value = false;
    if (error instanceof ApiError && error.kind === 'rate_limited') {
      message.value = `${error.message}. Try again in ${error.retryAfterSeconds} seconds.`;
    } else {
      message.value = error instanceof ApiError ? error.message : 'Something went wrong';
    }
  }
}

function reopen(entry: StoredSubmission): void {
  selections.value = [...entry.selections];
  busy.value = true;
  poll(entry.run_token, 0);
}
</script>

<template>
  <main class="mx-auto max-w-5xl space-y-8 p-6">
    <header>
      <h1 class="text-2xl font-bold text-slate-900">Python concurrency explorer</h1>
      <p class="text-slate-600">
        Compare how the same workload behaves across interpreter versions, GIL modes, operating
        systems, and concurrency strategies. Every run executes on a real GitHub Actions runner.
      </p>
    </header>

    <p v-if="message" class="rounded border border-amber-300 bg-amber-50 p-3 text-amber-900">
      {{ message }}
    </p>

    <ConfigureView
      v-if="catalog"
      :catalog="catalog"
      :interpreters="interpreters"
      :runners="runners"
      :selections="selections"
      @add="(selection) => selections.push(selection)"
      @remove="(index) => selections.splice(index, 1)"
      @submit="submit"
    />

    <section v-if="busy" class="rounded border border-sky-200 bg-sky-50 p-4 text-sky-900">
      Running on GitHub Actions. Legs appear below as they finish
      <span v-if="status"> ({{ status.results.length }} of {{ status.expected_legs }} so far)</span>.
    </section>

    <CompareGrid v-if="status" :results="status.results" />

    <section v-if="history.length > 0">
      <h2 class="mb-2 text-sm font-semibold text-slate-700">Recent comparisons</h2>
      <ul class="space-y-1 text-sm">
        <li v-for="entry in history" :key="entry.run_token">
          <button type="button" class="text-sky-700 hover:underline" @click="reopen(entry)">
            {{ new Date(entry.created_at).toLocaleString() }} - {{ entry.leg_count }} legs
          </button>
        </li>
      </ul>
    </section>
  </main>
</template>
