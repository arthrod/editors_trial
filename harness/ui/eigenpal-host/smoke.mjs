// Single smoke open for the eigenpal DOCX editor host.
//
// Mirrors what perf/runner/warm_cold_browser.mjs does for one cold pair:
//   navigate -> wait for the ready predicate -> click the edit selector -> type one char.
// It also records the diagnostics that justify the two selectors.
//
// Usage (repo root):
//   node harness/ui/eigenpal-host/smoke.mjs
// Env:
//   EIGENPAL_URL   default http://127.0.0.1:5218/?perfE2e=1&fixture=corpus.docx&reviewRail=0
//   EIGENPAL_DOCX  default repos/eigenpal-docx-editor/examples/vite/public/sample.docx
//   OUT_DIR        default /tmp/perf-run-logs

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '../../..');

const URL_ = process.env.EIGENPAL_URL || 'http://127.0.0.1:5218/?perfE2e=1&fixture=corpus.docx&reviewRail=0';
const DOCX =
  process.env.EIGENPAL_DOCX ||
  path.join(repoRoot, 'repos/eigenpal-docx-editor/examples/vite/public/sample.docx');
const OUT = process.env.OUT_DIR || '/tmp/perf-run-logs';
const CORPUS_ROUTE = '/corpus.docx';

// Same predicate as the repo's own browser bench (e2e/edit-browser-bench-harness.ts): the
// editor instance exists, the shaped font measurer is in use (not the fixed fallback), a
// materialised page is visibly laid out, and no progressive-open marker is still pending.
const READY_JS = `window.__DOCX_EDITOR_E2E__?.ready() === true && window.__DOCX_EDITOR_E2E__?.fontMeasurer() === 'shaped' && (() => { const p = document.querySelector('.docx-page[data-materialized="true"]'); if (!p) return false; const r = p.getBoundingClientRect(); return getComputedStyle(p).visibility === 'visible' && r.width > 0 && r.height > 0 && !document.querySelector('[data-docx-opening-preview], [data-docx-layout-pending]'); })()`;
const EDIT_SELECTOR = '.docx-page-content [data-paragraph-id][data-start]';

const bytes = fs.readFileSync(DOCX);
fs.mkdirSync(OUT, { recursive: true });

const consoleLines = [];
const pageErrors = [];

const browser = await chromium.launch({
  headless: true,
  args: ['--font-render-hinting=none', '--disable-lcd-text'],
});
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await context.route('**/*', async (route) => {
  const u = new URL(route.request().url());
  if (u.pathname === CORPUS_ROUTE) {
    await route.fulfill({
      status: 200,
      contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      body: bytes,
    });
    return;
  }
  await route.continue();
});
const page = await context.newPage();
page.on('console', (m) => consoleLines.push(`${m.type()}: ${m.text()}`));
page.on('pageerror', (e) => pageErrors.push(String(e)));

const t0 = Date.now();
await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 120_000 });
const navigationMs = Date.now() - t0;

const readyStart = Date.now();
await page.waitForFunction(READY_JS, undefined, { timeout: 120_000 });
const readyMs = Date.now() - readyStart;

const before = await page.evaluate(() => {
  const pages = document.querySelectorAll('.docx-page');
  const materialized = document.querySelectorAll('.docx-page[data-materialized="true"]');
  const layer = document.querySelector('.docx-pages');
  const content = document.querySelector('.docx-page-content');
  const candidates = {
    pageContent: document.querySelectorAll('.docx-page-content').length,
    paragraphFragment: document.querySelectorAll('.docx-paragraph-fragment').length,
    dataParagraphId: document.querySelectorAll('[data-paragraph-id]').length,
    dataStart: document.querySelectorAll('[data-start]').length,
    fragmentWithStart: document.querySelectorAll('.docx-paragraph-fragment[data-start]').length,
    pageContentFragmentWithStart: document.querySelectorAll(
      '.docx-paragraph-fragment[data-start]'
    ).length,
    runWithStart: document.querySelectorAll('.docx-page-content [data-paragraph-id][data-start]')
      .length,
    contentEditable: document.querySelectorAll('[contenteditable="true"]').length,
  };
  const scrollers = Array.from(document.querySelectorAll('*'))
    .filter((el) => el.scrollHeight - el.clientHeight >= 200 && el.clientHeight > 200)
    .map((el) => ({
      cls: el.className && typeof el.className === 'string' ? el.className.slice(0, 80) : el.tagName,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      overflowY: getComputedStyle(el).overflowY,
    }))
    .sort((a, b) => b.scrollHeight - a.scrollHeight)
    .slice(0, 3);
  return {
    pageCount: pages.length,
    materializedCount: materialized.length,
    candidates,
    scrollers,
    contentOuterHtmlHead: content ? content.outerHTML.slice(0, 1500) : '',
    pagesTextLength: layer ? layer.textContent.length : 0,
    pagesTextHead: layer ? layer.textContent.slice(0, 200) : '',
    readyApi: window.__DOCX_EDITOR_E2E__?.ready() === true,
    fontMeasurer: window.__DOCX_EDITOR_E2E__?.fontMeasurer() ?? null,
  };
});

const editT0 = Date.now();
try {
  await page.locator(EDIT_SELECTOR).first().click({ timeout: 30_000 });
} catch (error) {
  fs.writeFileSync(
    path.join(OUT, 'eigenpal-host-smoke.json'),
    JSON.stringify(
      { url: URL_, before, console: consoleLines, page_errors: pageErrors, click_error: String(error) },
      null,
      2
    ) + '\n'
  );
  await page.screenshot({ path: path.join(OUT, 'eigenpal-host-smoke-fail.png') });
  throw error;
}
const caret = await page.evaluate(() => {
  const sel = document.getSelection();
  return {
    inPages: Boolean(sel && sel.anchorNode && document.querySelector('.docx-pages')?.contains(sel.anchorNode)),
    anchorTag: sel?.anchorNode?.nodeName ?? null,
  };
});
await page.keyboard.type('x', { delay: 12 });
const paintMs = await page.evaluate(async () => {
  const t = performance.now();
  await new Promise((r) => requestAnimationFrame(() => r(null)));
  await new Promise((r) => requestAnimationFrame(() => r(null)));
  return performance.now() - t;
});
const editMs = Date.now() - editT0;

const after = await page.evaluate(() => {
  const layer = document.querySelector('.docx-pages');
  return {
    pagesTextLength: layer ? layer.textContent.length : 0,
    pagesTextHead: layer ? layer.textContent.slice(0, 120) : '',
    pageCount: document.querySelectorAll('.docx-page').length,
    materializedCount: document.querySelectorAll('.docx-page[data-materialized="true"]').length,
    canUndo: window.__DOCX_EDITOR_E2E__ ? window.__DOCX_EDITOR_E2E__.canUndo() : null,
    layoutPending: Boolean(document.querySelector('[data-docx-layout-pending]')),
  };
});

const shot = path.join(OUT, 'eigenpal-host-smoke.png');
await page.screenshot({ path: shot, fullPage: false });

const summary = {
  url: URL_,
  corpus_route: CORPUS_ROUTE,
  docx: path.relative(repoRoot, DOCX),
  ready_js: READY_JS,
  edit_selector: EDIT_SELECTOR,
  navigation_ms: navigationMs,
  ready_ms: readyMs,
  before,
  caret,
  edit_ms: editMs,
  presented_frame_ms: paintMs,
  after,
  text_delta: after.pagesTextLength - before.pagesTextLength,
  console: consoleLines,
  page_errors: pageErrors,
  screenshot: shot,
};
fs.writeFileSync(path.join(OUT, 'eigenpal-host-smoke.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify(summary, null, 2));

await context.close();
await browser.close();
