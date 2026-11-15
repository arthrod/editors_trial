/** Ready/navigation load-timeout policy (lax layer, owner decision
 * 2026-11-11; GitHub issue #155 item 6): 300 s by default, 600 s on the
 * biggest documents. The Python lanes export PERF_LOAD_TIMEOUT_MS from
 * perf/runner/load_timeouts.py (which also records the value on every
 * trial's `environment.load_timeout_ms`); a broken or missing value falls
 * back to the default. Values from 1 s upward are honoured as written. */
export const DEFAULT_LOAD_TIMEOUT_MS = 300_000;

/** The ready/navigation timeout in ms: PERF_LOAD_TIMEOUT_MS when it names a
 * usable duration, else the 300 s default. */
export function loadTimeoutMs(env = process.env) {
  const raw = Number(env.PERF_LOAD_TIMEOUT_MS);
  return Number.isFinite(raw) && raw >= 1000 ? raw : DEFAULT_LOAD_TIMEOUT_MS;
}
