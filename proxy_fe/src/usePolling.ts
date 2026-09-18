import type { RunStatusResponse } from './api/types';

const BASE_INTERVAL_MS = 2000;
const MAX_INTERVAL_MS = 10000;

export function shouldKeepPolling(status: RunStatusResponse): boolean {
  return status.phase === 'pending' || status.phase === 'running';
}

// A benchmark run takes minutes, so the poll interval widens as it goes
// rather than hammering the API at a fixed rate for the whole wait.
export function pollIntervalMs(elapsedPolls: number): number {
  return Math.min(BASE_INTERVAL_MS + elapsedPolls * 250, MAX_INTERVAL_MS);
}

export function nextStatus(
  previous: RunStatusResponse | null,
  incoming: RunStatusResponse | null,
): RunStatusResponse | null {
  return incoming ?? previous;
}
