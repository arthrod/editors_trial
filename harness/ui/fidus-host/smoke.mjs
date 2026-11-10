/**
 * One smoke test for the fidus-host perf target: the same calls the warm/cold
 * probe makes (perf/runner/warm_cold_browser.mjs), nothing more —
 *
 *   goto(url) -> waitForSelector(ready, visible) -> click(edit) -> type("x")
 *
 * and then the check the probe cannot make: the editor still holds the
 * document's text after the keystroke, plus one more character.
 *
 * usage: node harness/ui/fidus-host/smoke.mjs [--url http://localhost:5219/]
 *                                             [--corpus fixture/complex.docx]
 *                                             [--out /tmp/perf-run-logs]
 */
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../../..');

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (!a.startsWith('--')) continue;
  const key = a.slice(2);
  const next = argv[i + 1];
  if (next === undefined || next.startsWith('--')) opt[key] = true;
  else {
    opt[key] = next;
    i++;
  }
}

const URL_ = opt.url || 'http://localhost:5219/';
const CORPUS = path.resolve(here, opt.corpus || path.join(repo, 'fixture/complex.docx'));
const OUT = opt.out || '/tmp/perf-run-logs';
const READY = opt['ready-selector'] || 'html[data-fidus-host-ready="1"]';
const EDIT = opt['edit-selector'] || '#document-editable .ProseMirror';
const CORPUS_ROUTE = opt['corpus-route'] || '/corpus.docx';
fs.mkdirSync(OUT, { recursive: true });

const consoleLog = [];
const pageErrors = [];
const failures = [];
const corpusBytes = fs.readFileSync(CORPUS);

const browser = await chromium.launch({ headless: true, args: ['--font-render-hinting=none', '--disable-lcd-text'] });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });

// The perf harness fulfils this path itself; do the same so the smoke uses the
// corpus the runner would serve, not the proxy's fallback copy.
await context.route('**/*', async (route) => {
  if (new URL(route.request().url()).pathname === CORPUS_ROUTE) {
    await route.fulfill({
      status: 200,
      contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      body: corpusBytes,
    });
    return;
  }
  await route.continue();
});

const page = await context.newPage();
page.on('console', (m) => consoleLog.push({ type: m.type(), text: m.text() }));
page.on('pageerror', (e) => pageErrors.push(String(e)));

const t0 = Date.now();
await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 120000 });
const navigationMs = Date.now() - t0;

let readyMs = null;
try {
  await page.waitForSelector(READY, { timeout: 180000, state: 'visible' });
  readyMs = Date.now() - t0;
} catch (e) {
  failures.push('ready selector never appeared: ' + String(e).split('\n')[0]);
}

const landed = page.url();
const before = await page.evaluate((sel) => {
  const el = document.querySelector(sel);
  return el ? { text: el.innerText, editable: el.getAttribute('contenteditable') } : null;
}, EDIT);

let editMs = null;
if (readyMs !== null) {
  try {
    const t1 = Date.now();
    await page.locator(EDIT).first().click({ timeout: 30000 });
    await page.keyboard.type('x', { delay: 12 });
    editMs = Date.now() - t1;
  } catch (e) {
    failures.push('edit failed: ' + String(e).split('\n')[0]);
  }
}

await page.waitForTimeout(700);

const after = await page.evaluate((sel) => {
  const el = document.querySelector(sel);
  return el
    ? {
        text: el.innerText,
        editable: el.getAttribute('contenteditable'),
        pmCount: document.querySelectorAll('.ProseMirror').length,
        coverActive: !!document.querySelector('#wait.active'),
        ready: document.documentElement.getAttribute('data-fidus-host-ready'),
        error: document.documentElement.getAttribute('data-fidus-host-error'),
      }
    : null;
}, EDIT);

const title = await page.title();
await page.screenshot({ path: path.join(OUT, 'fidus_host_smoke.png'), fullPage: false });

const checks = {
  ready_flag: after && after.ready === '1',
  editor_is_editable: !!(after && after.editable === 'true'),
  document_text_present: !!(after && /Chapter 1/.test(after.text) && /mixed formatting/.test(after.text)),
  text_survived_edit: !!(before && after && after.text.includes('Chapter 1')),
  keystroke_inserted: !!(before && after && after.text.length === before.text.length + 1),
  cover_gone: !!(after && after.coverActive === false),
  no_boot_error: !(after && after.error),
};
for (const [k, v] of Object.entries(checks)) if (!v) failures.push('check failed: ' + k);

const result = {
  url: URL_,
  landed_url: landed,
  ready_selector: READY,
  edit_selector: EDIT,
  corpus: CORPUS,
  navigation_ms: navigationMs,
  ready_ms: readyMs,
  edit_ms: editMs,
  title,
  checks,
  before: before && { len: before.text.length, head: before.text.slice(0, 120), editable: before.editable },
  after: after && {
    len: after.text.length,
    head: after.text.slice(0, 120),
    tail: after.text.slice(-120),
    editable: after.editable,
    pmCount: after.pmCount,
    coverActive: after.coverActive,
    ready: after.ready,
    error: after.error,
  },
  boot_log: consoleLog.filter((m) => m.text.startsWith('[fidus-host]')).map((m) => m.text),
  console_errors: consoleLog.filter((m) => m.type === 'error').map((m) => m.text.slice(0, 300)),
  page_errors: pageErrors.map((e) => e.slice(0, 300)),
  failures,
  verdict: failures.length === 0 ? 'PASS' : 'FAIL',
};

fs.writeFileSync(path.join(OUT, 'fidus_host_smoke.json'), JSON.stringify({ ...result, console: consoleLog }, null, 2));
await browser.close();

console.log(JSON.stringify(result, null, 2));
process.exit(failures.length === 0 ? 0 : 1);
