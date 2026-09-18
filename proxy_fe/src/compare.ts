import type { RunResult } from './api/types';
import {
  formatBytes,
  formatDuration,
  formatFactor,
  formatSpread,
  formatThroughput,
} from './format';

export type MetricDirection = 'lower' | 'higher' | 'none';
export type MetricGroup = 'Environment' | 'Timing' | 'Memory' | 'Concurrency';

export interface MetricRow {
  readonly key: string;
  readonly group: MetricGroup;
  readonly label: string;
  readonly explainer: string;
  readonly direction: MetricDirection;
  readonly value: (result: RunResult) => number | null;
  readonly render: (result: RunResult) => string;
  readonly spread?: (result: RunResult) => string | null;
}

const MISSING = '-';

// One entry per row of the comparison grid. A new metric is a new entry here,
// never a template change.
export const METRIC_ROWS: readonly MetricRow[] = [
  {
    key: 'python_version',
    group: 'Environment',
    label: 'Python version',
    explainer: 'The interpreter build that actually ran, as reported by the interpreter itself.',
    direction: 'none',
    value: () => null,
    render: (result) => result.environment?.python_version ?? MISSING,
  },
  {
    key: 'gil',
    group: 'Environment',
    label: 'GIL',
    explainer:
      'Whether the global interpreter lock was active. Confirmed at runtime rather than inferred from the build name.',
    direction: 'none',
    value: () => null,
    render: (result) => {
      if (result.environment === null) return MISSING;
      return result.environment.gil_enabled ? 'enabled' : 'disabled';
    },
  },
  {
    key: 'cpu_count',
    group: 'Environment',
    label: 'CPU count seen by Python',
    explainer:
      'Runners differ in core count, so every leg is normalised with PYTHON_CPU_COUNT. This changes what Python reports, and therefore default pool sizing, not the underlying hardware.',
    direction: 'none',
    value: () => null,
    render: (result) => {
      if (result.environment === null) return MISSING;
      const suffix = result.environment.cpu_count_source === 'override' ? ' (normalised)' : '';
      return `${result.environment.cpu_count_effective}${suffix}`;
    },
  },
  {
    key: 'cores',
    group: 'Environment',
    label: 'Runner cores',
    explainer: 'Logical cores the runner image actually provides, before normalisation.',
    direction: 'none',
    value: () => null,
    render: (result) => String(result.environment?.logical_cores ?? MISSING),
  },
  {
    key: 'wall_time',
    group: 'Timing',
    label: 'Wall time',
    explainer:
      'How long the measured work took, excluding interpreter startup. This is the number most people mean by "faster".',
    direction: 'lower',
    value: (result) => result.scalars?.wall_time_s.median ?? null,
    render: (result) =>
      result.scalars === null ? MISSING : formatDuration(result.scalars.wall_time_s.median),
    spread: (result) =>
      result.scalars === null ? null : formatSpread(result.scalars.wall_time_s, formatDuration),
  },
  {
    key: 'cpu_time',
    group: 'Timing',
    label: 'CPU time',
    explainer:
      'Total processor time across every thread. Much larger than wall time means work genuinely happened in parallel.',
    direction: 'none',
    value: (result) =>
      result.scalars === null
        ? null
        : result.scalars.cpu_user_s.median + result.scalars.cpu_sys_s.median,
    render: (result) => {
      if (result.scalars === null) return MISSING;
      return formatDuration(result.scalars.cpu_user_s.median + result.scalars.cpu_sys_s.median);
    },
  },
  {
    key: 'throughput',
    group: 'Timing',
    label: 'Throughput',
    explainer: 'Operations completed per second.',
    direction: 'higher',
    value: (result) => result.scalars?.throughput_ops_s?.median ?? null,
    render: (result) => {
      const stats = result.scalars?.throughput_ops_s;
      return stats === null || stats === undefined ? MISSING : formatThroughput(stats.median);
    },
  },
  {
    key: 'peak_rss',
    group: 'Memory',
    label: 'Peak memory',
    explainer: 'Largest resident set size observed while the work ran.',
    direction: 'lower',
    value: (result) => result.scalars?.peak_rss_bytes.median ?? null,
    render: (result) =>
      result.scalars === null ? MISSING : formatBytes(result.scalars.peak_rss_bytes.median),
  },
  {
    key: 'parallelism',
    group: 'Concurrency',
    label: 'Parallelism factor',
    explainer:
      'CPU time divided by wall time. Near 1.0 means only one core was ever busy, whatever the worker count. Near the worker count means real parallelism. This is the row where the GIL shows itself.',
    direction: 'higher',
    value: (result) => result.scalars?.parallelism_factor.median ?? null,
    render: (result) =>
      result.scalars === null ? MISSING : formatFactor(result.scalars.parallelism_factor.median),
    spread: (result) =>
      result.scalars === null
        ? null
        : formatSpread(result.scalars.parallelism_factor, formatFactor),
  },
  {
    key: 'repeats',
    group: 'Concurrency',
    label: 'Repeats completed',
    explainer:
      'How many times the measurement ran. Reported values are the median of these; the spread shows how noisy the runner was.',
    direction: 'none',
    value: () => null,
    render: (result) => String(result.scalars?.repeats_completed ?? MISSING),
  },
];

export function bestIndex(row: MetricRow, results: readonly RunResult[]): number | null {
  if (row.direction === 'none') return null;

  let winner: number | null = null;
  let best = Number.NaN;
  results.forEach((result, index) => {
    const candidate = row.value(result);
    if (candidate === null) return;
    const isBetter =
      winner === null || (row.direction === 'lower' ? candidate < best : candidate > best);
    if (isBetter) {
      winner = index;
      best = candidate;
    }
  });
  return winner;
}

export function groupedRows(): Map<MetricGroup, MetricRow[]> {
  const grouped = new Map<MetricGroup, MetricRow[]>();
  for (const row of METRIC_ROWS) {
    const existing = grouped.get(row.group) ?? [];
    existing.push(row);
    grouped.set(row.group, existing);
  }
  return grouped;
}
