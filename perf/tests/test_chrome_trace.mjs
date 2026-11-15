/**
 * Minimal Chromium trace smoke (needs harness Playwright + installed browsers).
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadPlaywright } from '../runner/witness.mjs';
import { startChromeTrace, stopChromeTrace, tracePathFor } from '../runner/chrome_trace.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'chrome-trace-'));
process.env.PERF_CHROME_PROFILE_DIR = scratch;
process.env.PERF_CHROME_TRACE_PATH = '';

const { chromium } = await loadPlaywright();
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setContent('<html><body><h1>trace</h1></body></html>');
const handle = await startChromeTrace(browser, page, 'smoke');
assert.ok(handle);
const ended = await stopChromeTrace(browser, handle);
assert.equal(ended, tracePathFor('smoke'));
assert.ok(fs.existsSync(ended));
await browser.close();
