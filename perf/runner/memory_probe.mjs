/**
 * Phase-gated browser probe for the C17/C19 memory criteria.
 *
 * The runner owns the sampling clock: this probe drives the page, announces
 * each phase on stdout, and then blocks until the runner writes a line on
 * stdin. That keeps "sample at ready / after the burst / at quiescence" in the
 * Python process-tree sampler instead of guessing from timestamps.
 *
 * Protocol, one line per message:
 *   PHASE <name> <json>      probe is parked at <name>; waits for one stdin line
 *   RESULT <json>            probe finished; process exits 0
 *   ERROR <message>          probe failed; process exits 1
 *
 * Usage (from the repo root, with the editor's dev server already listening):
 *   node perf/runner/memory_probe.mjs \
 *     --url http://127.0.0.1:5208/ \
 *     --corpus /abs/fixture.docx --corpus-route /corpus.docx \
 *     --ready-selector '.status-ok' --edit-selector '[contenteditable="true"]' \
 *     --burst 12 --burst-text abcdefghij --quiescence-ms 2000 --reopen true
 */
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { startChromeTrace, stopChromeTrace } from './chrome_trace.mjs';
import { LANE_LOAD_TIMEOUT_MS, LANE_POLL_BOUND_MS, runLaneEditBurst } from './lane_edit_burst.mjs';
import { loadTimeoutMs } from './load_timeout.mjs';

// Ready/navigation wait follows the workload policy (300 s default, 600 s on prose-250kw).
const loadTimeout = loadTimeoutMs();

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '../..');
const uiRoot = path.resolve(repoRoot, 'harness/ui');

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (!a.startsWith('--')) continue;
  const key = a.slice(2);
  const next = argv[i + 1];
  if (next === undefined || next.startsWith('--')) {
    opt[key] = true;
  } else {
    opt[key] = next;
    i++;
  }
}

const url = opt.url;
const corpusFile = opt.corpus;
const corpusRoute = opt['corpus-route'] || '/corpus.docx';
const readySelector = opt['ready-selector'] || '';
const readyJs = opt['ready-js'] || '';
const waitAfterReadyMs = Number(opt['wait-after-ready'] || 0);
const editSelector = opt['edit-selector'] || '';
const editorId = typeof opt.editor === 'string' ? opt.editor : '';
const errorJs = opt['error-js'] || '';
const MEMORY_EDIT_POLL_CAP_MS = 90_000;
const pollBoundMs = Math.min(
  Number(opt['poll-bound-ms'] || LANE_POLL_BOUND_MS),
  MEMORY_EDIT_POLL_CAP_MS,
);
const burst = Math.max(0, Number(opt.burst || 0));
const burstText = opt['burst-text'] || 'abcdefghij';
const quiescenceMs = Math.max(0, Number(opt['quiescence-ms'] || 2000));
const reopen = opt.reopen === 'true' || opt.reopen === true;
const viewport = { width: 1280, height: 900 };

if (!url || !corpusFile) {
  process.stderr.write('memory_probe: --url and --corpus are required\n');
  process.exit(2);
}

const corpusBytes = fs.readFileSync(corpusFile);

const queue = [];
let waiter = null;
const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.on('line', (line) => {
  const trimmed = line.trim();
  if (waiter) {
    const resolve = waiter;
    waiter = null;
    resolve(trimmed);
    return;
  }
  queue.push(trimmed);
});

function nextCommand() {
  if (queue.length > 0) return Promise.resolve(queue.shift());
  return new Promise((resolve) => {
    waiter = resolve;
  });
}

async function phase(name, payload = {}) {
  process.stdout.write(`PHASE ${name} ${JSON.stringify(payload)}\n`);
  await nextCommand();
}

async function loadPlaywright() {
  const spec = path.join(uiRoot, 'node_modules/playwright/index.mjs');
  return import(pathToFileURL(spec).href);
}

function launchedBrowserPid(browserContext) {
  const viaPublic = typeof browserContext.browser === 'function' ? browserContext.browser() : null;
  const publicProc = viaPublic && typeof viaPublic.process === 'function' ? viaPublic.process() : null;
  if (publicProc && Number.isInteger(publicProc.pid) && publicProc.pid > 0) return publicProc.pid;
  // Playwright 1.64 hides ChildProcess on the client Browser. The in-process
  // connection still points at the server browser this call launched.
  const connection = browserContext._connection;
  const impl = connection && typeof connection.toImpl === 'function' ? connection.toImpl(browserContext) : null;
  const serverBrowser = impl && impl._browser;
  const proc = serverBrowser && serverBrowser.options && serverBrowser.options.browserProcess
    ? serverBrowser.options.browserProcess.process
    : null;
  if (proc && Number.isInteger(proc.pid) && proc.pid > 0) return proc.pid;
  return null;
}

async function waitForReady(page, timeoutMs = loadTimeout) {
  if (readyJs) {
    await page.waitForFunction(
      (expr) => {
        const editorError = window.__DOCX_ERROR__;
        if (typeof editorError === 'string' && editorError) throw new Error(editorError);
        try {
          // eslint-disable-next-line no-eval
          return Boolean(eval(expr));
        } catch {
          return false;
        }
      },
      readyJs,
      { timeout: timeoutMs },
    );
  } else if (readySelector) {
    await page.waitForSelector(readySelector, { timeout: timeoutMs, state: 'visible' });
  }
  if (errorJs) {
    const loadError = await page.evaluate((expr) => {
      try {
        const value = eval(expr);
        return typeof value === 'string' && value ? value : null;
      } catch {
        return null;
      }
    }, errorJs);
    if (loadError) throw new Error(loadError);
  }
  if (waitAfterReadyMs > 0) await page.waitForTimeout(waitAfterReadyMs);
}

async function routeCorpus(context) {
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === corpusRoute) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: corpusBytes,
      });
      return;
    }
    await route.continue();
  });
}

async function openEditor(browser, traceLabel = 'C17-first') {
  const context = await browser.newContext({ viewport });
  await routeCorpus(context);
  const page = await context.newPage();
  const trace = await startChromeTrace(browser, page, traceLabel);
  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: loadTimeout });
  await waitForReady(page, loadTimeout);
  return { context, page, readyMs: Date.now() - t0, trace };
}

async function closeSession(browser, session) {
  await stopChromeTrace(browser, session.trace);
  await session.context.close();
}

async function main() {
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  let browserPid = null;
  const result = {
    driver: 'playwright',
    url,
    corpus_route: corpusRoute,
    burst: { iterations: burst, text: burstText, method: 'keyboard.type' },
    quiescence_ms: quiescenceMs,
    reopen,
    load_timeout_ms: loadTimeout,
    ready_ms: null,
    edit_effective: null,
    edit_error: null,
    typed_chars: 0,
    reopen_ready_ms: null,
    reopen_error: null,
  };

  try {
    const first = await openEditor(browser);
    browserPid = launchedBrowserPid(first.context);
    if (!browserPid) {
      throw new Error('could not read launched browser pid');
    }
    result.ready_ms = first.readyMs;
    await phase('ready', { ready_ms: first.readyMs, browser_pid: browserPid });

    let editOracle = null;
    if (burst > 0 && editSelector && editorId) {
      try {
        const burstResult = await runLaneEditBurst(first.page, null, {
          editorId,
          selector: editSelector,
          text: burstText,
          repetitions: burst,
          pollBoundMs,
        });
        editOracle = burstResult.oracle;
        result.edit_effective = burstResult.edit_effective === true;
        result.edit_error = burstResult.edit_error;
        result.typed_chars = burst * burstText.length;
      } catch (err) {
        result.edit_error = String(err.message || err).slice(0, 400);
        result.edit_effective = false;
      }
    } else if (burst > 0 && editSelector) {
      result.edit_error = 'memory_probe: --editor is required for edit verification';
      result.edit_effective = false;
    }
    await phase('edited', {
      browser_pid: browserPid,
      edit_effective: result.edit_effective,
      typed_chars: result.typed_chars,
      edit_error: result.edit_error,
      edit_oracle: editOracle,
    });

    await first.page.waitForTimeout(quiescenceMs);
    await phase('quiescent', { browser_pid: browserPid, idle_ms: quiescenceMs });

    if (!reopen) {
      await closeSession(browser, first);
      await browser.close();
      process.stdout.write(`RESULT ${JSON.stringify(result)}\n`);
      return;
    }

    await closeSession(browser, first);
    await phase('closed', { browser_pid: browserPid, context_closed: true });

    try {
      const second = await openEditor(browser, 'C17-reopen');
      result.reopen_ready_ms = second.readyMs;
      await phase('reopened', { browser_pid: browserPid, reopen_ready_ms: second.readyMs });
      await closeSession(browser, second);
    } catch (err) {
      result.reopen_error = String(err.message || err).slice(0, 400);
      await phase('reopened', {
        browser_pid: browserPid,
        reopen_ready_ms: null,
        reopen_error: result.reopen_error,
      });
    }

    await browser.close();
    process.stdout.write(`RESULT ${JSON.stringify(result)}\n`);
  } catch (err) {
    process.stdout.write(`ERROR ${String(err.message || err).slice(0, 800)}\n`);
    try {
      await browser.close();
    } catch {
      /* the browser may already be gone */
    }
    process.exitCode = 1;
  } finally {
    rl.close();
  }
}

main();
