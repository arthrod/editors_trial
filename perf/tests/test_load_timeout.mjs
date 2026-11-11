// The lax layer, item 2 (owner decision 2026-11-11): ready/navigation load
// timeouts. The shared policy lives in perf/runner/load_timeout.mjs; every
// probe imports it instead of hardcoding 120 s. Run with: node --test.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULT_LOAD_TIMEOUT_MS, loadTimeoutMs } from '../runner/load_timeout.mjs';

test('the default load timeout is 300 seconds', () => {
  assert.equal(DEFAULT_LOAD_TIMEOUT_MS, 300_000);
});

test('an explicit environment timeout is honoured', () => {
  assert.equal(loadTimeoutMs({ PERF_LOAD_TIMEOUT_MS: '600000' }), 600_000);
  assert.equal(loadTimeoutMs({ PERF_LOAD_TIMEOUT_MS: '300000' }), 300_000);
});

test('a broken environment value falls back to the default, never to zero', () => {
  assert.equal(loadTimeoutMs({}), DEFAULT_LOAD_TIMEOUT_MS);
  assert.equal(loadTimeoutMs({ PERF_LOAD_TIMEOUT_MS: 'not-a-number' }), DEFAULT_LOAD_TIMEOUT_MS);
  assert.equal(loadTimeoutMs({ PERF_LOAD_TIMEOUT_MS: '0' }), DEFAULT_LOAD_TIMEOUT_MS);
  assert.equal(loadTimeoutMs({ PERF_LOAD_TIMEOUT_MS: '-5' }), DEFAULT_LOAD_TIMEOUT_MS);
});
