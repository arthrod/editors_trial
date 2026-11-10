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

async function waitForReady(page, timeoutMs = 120_000) {
  if (readyJs) {
    await page.waitForFunction(
      (expr) => {
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

function bodyTextLength(page) {
  return page.evaluate(() => (document.body?.innerText || '').length);
}

async function openEditor(browser) {
  const context = await browser.newContext({ viewport });
  await routeCorpus(context);
  const page = await context.newPage();
  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  await waitForReady(page);
  return { context, page, readyMs: Date.now() - t0 };
}

async function main() {
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  const result = {
    driver: 'playwright',
    url,
    corpus_route: corpusRoute,
    burst: { iterations: burst, text: burstText, method: 'keyboard.type' },
    quiescence_ms: quiescenceMs,
    reopen,
    ready_ms: null,
    edit_effective: null,
    edit_error: null,
    typed_chars: 0,
    reopen_ready_ms: null,
    reopen_error: null,
  };

  try {
    const first = await openEditor(browser);
    result.ready_ms = first.readyMs;
    await phase('ready', { ready_ms: first.readyMs });

    const before = await bodyTextLength(first.page);
    if (burst > 0 && editSelector) {
      try {
        await first.page.locator(editSelector).first().click({ timeout: 30_000 });
        for (let i = 0; i < burst; i++) {
          await first.page.keyboard.type(burstText, { delay: 0 });
          result.typed_chars += burstText.length;
        }
        await first.page.evaluate(() => new Promise((r) => requestAnimationFrame(() => r(null))));
      } catch (err) {
        result.edit_error = String(err.message || err).slice(0, 400);
      }
    }
    const after = await bodyTextLength(first.page);
    result.edit_effective = after > before;
    await phase('edited', {
      edit_effective: result.edit_effective,
      text_length_before: before,
      text_length_after: after,
      typed_chars: result.typed_chars,
      edit_error: result.edit_error,
    });

    await first.page.waitForTimeout(quiescenceMs);
    await phase('quiescent', { idle_ms: quiescenceMs });

    if (!reopen) {
      await first.context.close();
      await browser.close();
      process.stdout.write(`RESULT ${JSON.stringify(result)}\n`);
      return;
    }

    await first.context.close();
    await phase('closed', { context_closed: true });

    try {
      const second = await openEditor(browser);
      result.reopen_ready_ms = second.readyMs;
      await phase('reopened', { reopen_ready_ms: second.readyMs });
      await second.context.close();
    } catch (err) {
      result.reopen_error = String(err.message || err).slice(0, 400);
      await phase('reopened', { reopen_ready_ms: null, reopen_error: result.reopen_error });
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
