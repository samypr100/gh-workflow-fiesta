import { expect, test } from '@rstest/core';
import type { RunResult } from '../src/api/types';
import { loadFixtures } from './helpers';

test('every fixture parses as a RunResult', () => {
  const results: RunResult[] = loadFixtures();
  expect(results.length).toBe(4);
  for (const result of results) {
    expect(result.leg.leg_id).toBeTruthy();
    expect(['ok', 'error', 'timeout']).toContain(result.status);
  }
});

test('fixtures contrast the two GIL modes', () => {
  const modes = loadFixtures()
    .map((result) => result.environment?.gil_enabled)
    .filter((value): value is boolean => value !== undefined && value !== null);
  expect(new Set(modes)).toEqual(new Set([true, false]));
});

test('a successful fixture carries scalars and a timeline', () => {
  const ok = loadFixtures().find((result) => result.status === 'ok');
  expect(ok?.scalars?.parallelism_factor.median).toBeGreaterThan(0);
  expect(ok?.timeline.length).toBeGreaterThan(0);
});

test('a timeout fixture keeps its partial timeline but has no scalars', () => {
  const timedOut = loadFixtures().find((result) => result.status === 'timeout');
  expect(timedOut?.scalars).toBeNull();
  expect(timedOut?.timeline.length).toBeGreaterThan(0);
});
