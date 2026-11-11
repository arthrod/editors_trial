/**
 * Optional Chromium timeline trace when PERF_CHROME_PROFILE_DIR or
 * PERF_CHROME_TRACE_PATH is set (diagnostic repetitions only).
 */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const CATEGORIES = [
  'devtools.timeline',
  'disabled-by-default-devtools.timeline',
  'disabled-by-default-devtools.timeline.frame',
  'v8.execute',
  'disabled-by-default-v8.cpu_profiler',
  'blink.user_timing',
  'loading',
  'latencyInfo',
  'toplevel',
];

export function tracingRequested() {
  return Boolean(process.env.PERF_CHROME_PROFILE_DIR || process.env.PERF_CHROME_TRACE_PATH);
}

export function tracePathFor(criterion) {
  const direct = process.env.PERF_CHROME_TRACE_PATH;
  if (direct) return direct;
  const dir = process.env.PERF_CHROME_PROFILE_DIR;
  if (!dir) return null;
  return path.join(dir, `trace-${criterion}.json.gz`);
}

/**
 * @returns {Promise<{raw: string, gz: string}|null>}
 */
export async function startChromeTrace(browser, page, criterion) {
  const gz = tracePathFor(criterion);
  if (!gz || typeof browser?.startTracing !== 'function') return null;
  fs.mkdirSync(path.dirname(gz), { recursive: true });
  const raw = gz.endsWith('.gz') ? gz.slice(0, -3) : `${gz}.raw`;
  await browser.startTracing(page, { path: raw, screenshots: false, categories: CATEGORIES });
  return { raw, gz };
}

/**
 * @param {{raw: string, gz: string}|null} handle
 */
export async function stopChromeTrace(browser, handle) {
  if (!handle || typeof browser?.stopTracing !== 'function') return null;
  await browser.stopTracing();
  const data = fs.readFileSync(handle.raw);
  fs.writeFileSync(handle.gz, zlib.gzipSync(data));
  try {
    fs.unlinkSync(handle.raw);
  } catch {
    /* already gone */
  }
  return handle.gz;
}
