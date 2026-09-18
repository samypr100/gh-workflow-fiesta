import type { SelectionRequest } from '../api/types';

export const HISTORY_KEY = 'benchmark.submissions.v1';
export const MAX_HISTORY = 20;

export interface StoredSubmission {
  readonly run_token: string;
  readonly created_at: number;
  readonly leg_count: number;
  readonly selections: readonly SelectionRequest[];
}

// The browser is the only place submission history exists; the backend keeps
// none. A stale entry from an older schema must therefore degrade to an empty
// list rather than break the page.
function isSubmission(value: unknown): value is StoredSubmission {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Partial<StoredSubmission>;
  return (
    typeof candidate.run_token === 'string' &&
    typeof candidate.created_at === 'number' &&
    typeof candidate.leg_count === 'number' &&
    Array.isArray(candidate.selections)
  );
}

export function loadHistory(storage: Storage): StoredSubmission[] {
  const raw = storage.getItem(HISTORY_KEY);
  if (raw === null) return [];

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];

  return parsed
    .filter(isSubmission)
    .sort((left, right) => right.created_at - left.created_at)
    .slice(0, MAX_HISTORY);
}

function persist(storage: Storage, entries: readonly StoredSubmission[]): void {
  try {
    storage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, MAX_HISTORY)));
  } catch {
    // A full or disabled storage costs the user their history, not the page.
  }
}

export function recordSubmission(storage: Storage, entry: StoredSubmission): void {
  const existing = loadHistory(storage).filter((item) => item.run_token !== entry.run_token);
  persist(storage, [entry, ...existing].sort((left, right) => right.created_at - left.created_at));
}

export function forgetSubmission(storage: Storage, runToken: string): void {
  persist(
    storage,
    loadHistory(storage).filter((item) => item.run_token !== runToken),
  );
}
