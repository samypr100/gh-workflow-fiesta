<script setup lang="ts">
import { computed, ref } from 'vue';
import type {
  CatalogItem,
  CatalogResponse,
  ExecutionModel,
  InterpreterOption,
  RunnerInfo,
  SelectionRequest,
} from '../api/types';
import InfoTip from './InfoTip.vue';

const props = defineProps<{
  readonly catalog: CatalogResponse;
  readonly interpreters: readonly InterpreterOption[];
  readonly runners: readonly RunnerInfo[];
  readonly selections: readonly SelectionRequest[];
}>();

const emit = defineEmits<{
  add: [selection: SelectionRequest];
  remove: [index: number];
  submit: [];
}>();

const chosenKey = ref(props.interpreters[0]?.python_key ?? '');
const chosenModel = ref(props.catalog.items[0]?.execution_model ?? 'threading');
const workers = ref(props.catalog.default_workers);
const iterations = ref(props.catalog.default_iterations);

const chosenInterpreter = computed(() =>
  props.interpreters.find((item) => item.python_key === chosenKey.value),
);

function unavailableReason(item: CatalogItem): string | null {
  const interpreter = chosenInterpreter.value;
  if (interpreter === undefined) return 'Select an interpreter first';
  if (interpreter.python_minor >= item.minimum_python_minor) return null;
  return `Needs Python 3.${item.minimum_python_minor} or newer; 3.${interpreter.python_minor} is selected`;
}

const availableItems = computed(() =>
  props.catalog.items.map((item) => ({ item, reason: unavailableReason(item) })),
);

// Which execution models have their source expanded. Collapsed by default:
// a reader choosing a strategy should not have to scroll past code first.
const openSources = ref(new Set<ExecutionModel>());

function isOpen(model: ExecutionModel): boolean {
  return openSources.value.has(model);
}

function toggleSource(model: ExecutionModel): void {
  // Replaced rather than mutated, because Vue does not track Set mutation.
  const next = new Set(openSources.value);
  if (next.has(model)) {
    next.delete(model);
  } else {
    next.add(model);
  }
  openSources.value = next;
}

function addConfiguration(): void {
  const interpreter = chosenInterpreter.value;
  const entry = props.catalog.items.find((item) => item.execution_model === chosenModel.value);
  if (interpreter === undefined || entry === undefined) return;
  emit('add', {
    os: interpreter.os,
    python_key: interpreter.python_key,
    workload: entry.workload,
    execution_model: entry.execution_model,
    workers: workers.value,
    iterations: iterations.value,
  });
}

function describe(selection: SelectionRequest): string {
  const interpreter = props.interpreters.find(
    (item) => item.python_key === selection.python_key,
  );
  const gil = interpreter?.gil_enabled === false ? 'no GIL' : 'GIL';
  return `${selection.os} - Python ${interpreter?.version ?? '?'} (${gil}) - ${selection.execution_model}`;
}
</script>

<template>
  <section class="space-y-6">
    <div class="grid gap-4 md:grid-cols-2">
      <label class="block">
        <span class="text-sm font-medium text-slate-700">
          Interpreter
          <InfoTip
            text="Every build uv can install on a GitHub runner. A free-threaded build has no GIL."
          />
        </span>
        <select
          v-model="chosenKey"
          data-testid="interpreter-select"
          class="mt-1 w-full rounded border border-slate-300 p-2"
        >
          <option v-for="item in interpreters" :key="item.python_key" :value="item.python_key">
            {{ item.os }} - Python {{ item.version }}
            ({{ item.gil_enabled ? 'GIL' : 'no GIL' }})
          </option>
        </select>
      </label>

      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="text-sm font-medium text-slate-700">
            Workers
            <InfoTip text="How many concurrent units the execution model creates." />
          </span>
          <input
            v-model.number="workers"
            type="number"
            :min="1"
            :max="catalog.max_workers"
            class="mt-1 w-full rounded border border-slate-300 p-2"
          />
        </label>
        <label class="block">
          <span class="text-sm font-medium text-slate-700">
            Iterations
            <InfoTip text="Units of work each worker performs." />
          </span>
          <input
            v-model.number="iterations"
            type="number"
            :min="1"
            :max="catalog.max_iterations"
            class="mt-1 w-full rounded border border-slate-300 p-2"
          />
        </label>
      </div>
    </div>

    <fieldset class="space-y-2">
      <legend class="text-sm font-medium text-slate-700">Execution model</legend>
      <div
        v-for="{ item, reason } in availableItems"
        :key="item.execution_model"
        class="rounded border p-3"
        :class="reason ? 'border-slate-200 opacity-60' : 'border-slate-300'"
      >
        <label class="flex gap-3">
          <input
            v-model="chosenModel"
            type="radio"
            :value="item.execution_model"
            :disabled="reason !== null"
            :data-testid="`model-${item.execution_model}`"
            class="mt-1"
          />
          <span>
            <span class="font-medium text-slate-800">{{ item.title }}</span>
            <span class="block text-sm text-slate-600">{{ item.explainer }}</span>
            <span class="block text-sm text-slate-500">Expect: {{ item.expectation }}</span>
            <span v-if="reason" class="mt-1 block text-sm font-medium text-amber-700">
              {{ reason }}
            </span>
          </span>
        </label>

        <!-- Collapsed by default: the code is reassurance for a reader who
             wants it, not something to wade through before choosing. -->
        <button
          type="button"
          class="mt-2 flex items-center gap-1 text-xs font-medium text-sky-700 hover:text-sky-900"
          :data-testid="`toggle-source-${item.execution_model}`"
          :aria-expanded="isOpen(item.execution_model)"
          :aria-controls="`source-${item.execution_model}`"
          @click="toggleSource(item.execution_model)"
        >
          <span
            class="inline-block transition-transform"
            :class="isOpen(item.execution_model) ? 'rotate-90' : ''"
            aria-hidden="true"
            >&#9656;</span
          >
          {{ isOpen(item.execution_model) ? 'Hide' : 'Show' }} the code this runs
        </button>
        <div
          v-show="isOpen(item.execution_model)"
          :id="`source-${item.execution_model}`"
          :data-testid="`source-${item.execution_model}`"
        >
          <pre
            class="mt-2 overflow-x-auto rounded bg-slate-900 p-3 text-xs leading-relaxed text-slate-100"
          ><code>{{ item.source_code }}</code></pre>
          <p class="mt-1 text-xs text-slate-500">
            From <code>{{ item.source_path }}</code> in the benchmark repository.
          </p>
        </div>
      </div>
    </fieldset>

    <button
      type="button"
      data-testid="add-configuration"
      class="rounded bg-sky-600 px-4 py-2 font-medium text-white hover:bg-sky-700"
      @click="addConfiguration"
    >
      Add to comparison
    </button>

    <div v-if="selections.length > 0" class="space-y-2">
      <h2 class="text-sm font-semibold text-slate-700">Comparing</h2>
      <ul class="flex flex-wrap gap-2">
        <li
          v-for="(selection, index) in selections"
          :key="`${selection.python_key}-${index}`"
          data-testid="selection-chip"
          class="flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm"
        >
          {{ describe(selection) }}
          <button
            type="button"
            data-testid="remove-chip"
            class="text-slate-500 hover:text-slate-800"
            :aria-label="`Remove ${describe(selection)}`"
            @click="emit('remove', index)"
          >
            x
          </button>
        </li>
      </ul>
    </div>

    <button
      type="button"
      data-testid="submit"
      :disabled="selections.length === 0"
      class="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      @click="emit('submit')"
    >
      Run comparison
    </button>
  </section>
</template>
