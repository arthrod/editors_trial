// One-open smoke for the Apryse browser perf host.
//
//   cd harness/apryse && node smoke_perf.mjs
//
// It assumes the host server is already listening (the warm/cold runner starts
// it with the command in PERF.md) and does what the probe does, once:
// navigate, wait for the ready signal, click the edit surface, type one
// character, and check that the document changed. Nothing is timed as a
// measurement; this only proves the host is usable.
//
// Evidence is written to /tmp/perf-run-logs/ by default:
//   apryse-perf-smoke.json   timings, console log, page errors, before/after
//   apryse-perf-smoke.png    the page after the edit
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(resolve(HERE, '../ui/package.json'));
const { chromium } = require('playwright');

const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf('--' + name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback;
};

const URL_ = arg('url', 'http://127.0.0.1:5213/perf.html');
const CORPUS = resolve(arg('corpus', resolve(HERE, '../../fixture/complex.docx')));
const OUTDIR = arg('outdir', '/tmp/perf-run-logs');
const WAIT_AFTER_READY = Number(arg('wait-after-ready', '500')); // the registry's wait_after_ready
const READY_JS = "window.__aprysePerf && window.__aprysePerf.state === 'rendered'";
const EDIT_SELECTOR = '#pageContainer1';

const corpus = readFileSync(CORPUS);
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
// Same interception the probe does: the page's /corpus.docx is this file.
await context.route('**/*', async (route) => {
  const u = new URL(route.request().url());
  if (u.pathname === '/corpus.docx') {
    return route.fulfill({
      status: 200,
      contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      body: corpus,
    });
  }
  return route.continue();
});

const page = await context.newPage();
const console_ = [];
page.on('console', (m) => console_.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => console_.push(`[pageerror] ${e.message}`));

const inkOfPageCanvases = () =>
  page.evaluate(() => {
    const root = document.querySelector('#viewer apryse-webviewer').shadowRoot;
    let total = 0;
    for (const canvas of root.querySelectorAll('.pageContainer canvas')) {
      if (canvas.getBoundingClientRect().width < 200) continue;
      const ctx = canvas.getContext('2d');
      if (!ctx) continue;
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 0; i < data.length; i += 4) if (data[i + 3] > 0 && data[i] < 200) total += 1;
    }
    return total;
  });

let code = 1;
try {
  const t0 = Date.now();
  await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 120000 });
  const navigationMs = Date.now() - t0;
  // Identical to warm_cold_browser.mjs waitForReady(): the expression is
  // eval'd in the page, so the registry's ready_js is what is exercised here.
  await page.waitForFunction((expr) => Boolean(eval(expr)), READY_JS, { timeout: 120_000 });
  const readyMs = Date.now() - t0;
  if (WAIT_AFTER_READY > 0) await page.waitForTimeout(WAIT_AFTER_READY); // same settle the probe takes before clicking
  const editStartMs = Date.now() - t0;
  const state = await page.evaluate(() => ({
    state: window.__aprysePerf.state,
    paint: window.__aprysePerf.paint,
    pageCount: window.__aprysePerf.pageCount,
    overlaysNeutralised: window.__aprysePerf.overlaysNeutralised,
    errors: window.__aprysePerf.errors,
  }));
  const bodyBefore = await page.evaluate(() => window.__aprysePerf.bodyText());
  const inkBefore = await inkOfPageCanvases();
  await page.screenshot({ path: resolve(OUTDIR, 'apryse-perf-smoke-before.png') });

  const editT0 = Date.now();
  await page.locator(EDIT_SELECTOR).first().click({ timeout: 30_000 });
  await page.keyboard.type('x', { delay: 12 });
  const editMs = Date.now() - editT0;
  await page.waitForTimeout(1200);
  const bodyAfter = await page.evaluate(() => window.__aprysePerf.bodyText());
  const inkAfter = await inkOfPageCanvases();
  await page.screenshot({ path: resolve(OUTDIR, 'apryse-perf-smoke.png') });

  const typed = bodyAfter.length !== bodyBefore.length || bodyAfter !== bodyBefore;
  const repainted = inkAfter !== inkBefore;
  const report = {
    url: URL_,
    corpus: CORPUS,
    corpus_bytes: corpus.length,
    ready_js: READY_JS,
    edit_selector: EDIT_SELECTOR,
    navigation_ms: navigationMs,
    ready_ms: readyMs,
    wait_after_ready_ms: WAIT_AFTER_READY,
    edit_start_ms: editStartMs,
    edit_ms: editMs,
    state,
    body_len_before: bodyBefore.length,
    body_len_after: bodyAfter.length,
    canvas_ink_before: inkBefore,
    canvas_ink_after: inkAfter,
    typed_changed_document: typed,
    page_repainted: repainted,
    screenshot: resolve(OUTDIR, 'apryse-perf-smoke.png'),
    console: console_,
    ok: typed && repainted && state.state === 'rendered',
  };
  mkdirSync(OUTDIR, { recursive: true });
  writeFileSync(resolve(OUTDIR, 'apryse-perf-smoke.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ ...report, console: undefined, console_lines: console_.length }, null, 2));
  code = report.ok ? 0 : 1;
  if (!report.ok) console.error('smoke failed: typed=' + typed + ' repainted=' + repainted + ' state=' + state.state);
} catch (err) {
  console.error('smoke error:', err && err.stack ? err.stack : err);
  mkdirSync(OUTDIR, { recursive: true });
  writeFileSync(
    resolve(OUTDIR, 'apryse-perf-smoke.json'),
    JSON.stringify({ url: URL_, corpus: CORPUS, error: String(err), console: console_ }, null, 2),
  );
} finally {
  await browser.close();
}
process.exit(code);
