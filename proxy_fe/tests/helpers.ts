import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { RunResult } from '../src/api/types';

const FIXTURE_DIR = join(dirname(fileURLToPath(import.meta.url)), 'fixtures');

export function loadFixtures(): RunResult[] {
  return readdirSync(FIXTURE_DIR)
    .filter((name) => name.endsWith('.json'))
    .map((name) => JSON.parse(readFileSync(join(FIXTURE_DIR, name), 'utf-8')) as RunResult);
}

export function successfulFixtures(): RunResult[] {
  return loadFixtures().filter((result) => result.status === 'ok');
}
