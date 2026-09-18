import { expect, test } from '@rstest/core';
import { ApiError, createClient } from '../src/api/client';
import type { SelectionRequest } from '../src/api/types';

const SELECTION: SelectionRequest = {
  os: 'linux',
  python_key: 'cpython-3.14.7-linux-x86_64-gnu',
  workload: 'cpu_bound',
  execution_model: 'threading',
  workers: 4,
  iterations: 100000,
};

function stubFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  return async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json', ...headers },
    });
}

test('createRun returns the token on success', async () => {
  const client = createClient('http://api', stubFetch(202, { run_token: 'a.b', leg_count: 2 }));
  const created = await client.createRun([SELECTION]);
  expect(created.run_token).toBe('a.b');
  expect(created.leg_count).toBe(2);
});

test('createRun sends the selections as the request body', async () => {
  let captured: RequestInit | undefined;
  const client = createClient('http://api', async (_url, init) => {
    captured = init;
    return new Response(JSON.stringify({ run_token: 'a.b', leg_count: 1 }), { status: 202 });
  });
  await client.createRun([SELECTION]);
  expect(JSON.parse(String(captured?.body))).toEqual({ selections: [SELECTION] });
});

test('a duplicate is surfaced as a typed error', async () => {
  const client = createClient('http://api', stubFetch(409, { detail: 'already running' }));
  await expect(client.createRun([SELECTION])).rejects.toMatchObject({
    kind: 'duplicate',
    message: 'already running',
  });
});

test('a rate limit carries its retry delay', async () => {
  const client = createClient(
    'http://api',
    stubFetch(429, { detail: 'slow down' }, { 'retry-after': '120' }),
  );
  try {
    await client.createRun([SELECTION]);
    throw new Error('expected a rejection');
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).kind).toBe('rate_limited');
    expect((error as ApiError).retryAfterSeconds).toBe(120);
  }
});

test('a validation refusal carries the explanation', async () => {
  const client = createClient(
    'http://api',
    stubFetch(400, { detail: 'requires Python 3.14 or newer' }),
  );
  await expect(client.createRun([SELECTION])).rejects.toMatchObject({
    kind: 'rejected',
    message: 'requires Python 3.14 or newer',
  });
});

test('a network failure is surfaced as a typed error', async () => {
  const client = createClient('http://api', async () => {
    throw new TypeError('offline');
  });
  await expect(client.runStatus('a.b')).rejects.toMatchObject({ kind: 'network' });
});

test('runStatus requests the token path', async () => {
  let captured = '';
  const client = createClient('http://api', async (url) => {
    captured = String(url);
    return new Response(
      JSON.stringify({ phase: 'pending', expected_legs: 0, results: [], detail: null }),
      { status: 200 },
    );
  });
  await client.runStatus('tok.sig');
  expect(captured).toBe('http://api/api/runs/tok.sig');
});
