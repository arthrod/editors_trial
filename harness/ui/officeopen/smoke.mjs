/**
 * Smoke for the office-open browser perf host.
 *
 *   cd harness/ui/officeopen && node smoke.mjs [--port 5212]
 *
 * Starts server.mjs, opens the host in Chromium (Playwright from
 * harness/ui/node_modules), waits for the ready signal, types one character
 * into the host input probe, and confirms the document still renders.
 * Evidence goes to /tmp/perf-run-logs/. This is a functional smoke: it reports
 * one page-load time for information, never a benchmark sample.
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(here, '..');
const OUT_DIR = '/tmp/perf-run-logs';

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  if (!argv[i].startsWith('--')) continue;
  const key = argv[i].slice(2);
  const next = argv[i + 1];
  if (next === undefined || next.startsWith('--')) opt[key] = true;
  else {
    opt[key] = next;
    i++;
  }
}
const port = Number(opt.port || 5212);
const url = `http://127.0.0.1:${port}/`;

if (!fs.existsSync(path.join(here, 'corpus.docx'))) {
  console.error('missing corpus.docx — run: PYTHONPATH=. python3 make_corpus.py');
  process.exit(2);
}

fs.mkdirSync(OUT_DIR, { recursive: true });
const consolePath = path.join(OUT_DIR, 'officeopen-console.log');
const serverPath = path.join(OUT_DIR, 'officeopen-server.log');
const shotPath = path.join(OUT_DIR, 'officeopen-after-typing.png');
const fullShotPath = path.join(OUT_DIR, 'officeopen-fullpage.png');
const jsonPath = path.join(OUT_DIR, 'officeopen-smoke.json');

const serverOut = [];
const server = spawn(process.execPath, ['server.mjs'], {
  cwd: here,
  env: { ...process.env, PORT: String(port) },
  stdio: ['ignore', 'pipe', 'pipe'],
});
server.stdout.on('data', (b) => serverOut.push(b.toString()));
server.stderr.on('data', (b) => serverOut.push(b.toString()));

async function waitForServer(timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (server.exitCode !== null) throw new Error(`server exited ${server.exitCode}`);
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error('server did not answer in time');
}

const evidence = { url, port, steps: [], assertions: {}, console: [], page_errors: [] };
let failure = null;
let browser = null;

try {
  await waitForServer();
  evidence.steps.push({ step: 'server_up', server_log: serverPath });
  evidence.corpus_route_bytes = (await fetch(new URL('/corpus.docx', url))).headers.get(
    'content-length'
  );

  const { chromium } = await import(
    pathToFileURL(path.join(uiRoot, 'node_modules/playwright/index.mjs')).href
  );
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  page.on('console', (m) => evidence.console.push(`${m.type()}: ${m.text()}`));
  page.on('pageerror', (e) => evidence.page_errors.push(String(e)));
  page.on('requestfailed', (r) =>
    evidence.console.push(`requestfailed: ${r.url()} ${r.failure()?.errorText || ''}`)
  );

  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  await page.waitForSelector('#status.status-ok', { state: 'visible', timeout: 120_000 });
  await page.waitForFunction(() => window.__OFFICEOPEN_READY__ === true, null, {
    timeout: 120_000,
  });
  evidence.ready_ms = Date.now() - t0;
  evidence.steps.push({ step: 'ready', ready_ms: evidence.ready_ms });

  const before = await page.evaluate(() => ({
    status: document.querySelector('#status').textContent,
    status_class: document.querySelector('#status').className,
    pages: document.querySelectorAll('.doc .page').length,
    paragraphs: document.querySelectorAll('.doc .para').length,
    tables: document.querySelectorAll('.doc .doc-table').length,
    probe_editable: document.querySelector('#input-probe')?.isContentEditable,
    probe_text: document.querySelector('#input-probe')?.textContent,
    timings: window.__OFFICEOPEN_TIMINGS__,
    body_scroll: document.body.scrollHeight,
    viewport: innerHeight,
  }));
  evidence.before_typing = before;
  evidence.assertions.ready_selector = before.status_class.includes('status-ok');
  evidence.assertions.document_rendered = before.pages >= 1 && before.paragraphs >= 1;
  evidence.assertions.probe_editable = before.probe_editable === true;

  const editT0 = Date.now();
  await page.locator('#input-probe').first().click({ timeout: 30_000 });
  await page.keyboard.type('x', { delay: 12 });
  await page.waitForTimeout(200);
  evidence.typing_ms = Date.now() - editT0;
  evidence.steps.push({ step: 'typed_one_char', ms: evidence.typing_ms });

  const after = await page.evaluate(() => ({
    probe_text: document.querySelector('#input-probe')?.textContent,
    ready: window.__OFFICEOPEN_READY__ === true,
    pages: document.querySelectorAll('.doc .page').length,
    paragraphs: document.querySelectorAll('.doc .para').length,
    status: document.querySelector('#status').textContent,
    error: window.__OFFICEOPEN_ERROR__ || null,
  }));
  evidence.after_typing = after;
  evidence.assertions.probe_received_key = (after.probe_text || '').includes('x');
  evidence.assertions.document_still_rendered =
    after.pages === before.pages && after.paragraphs === before.paragraphs && after.ready;

  // The C10 probe picks the largest overflow-y:auto|scroll element; record
  // which element it would choose (no scroll timing here).
  evidence.scroll_container = await page.evaluate(() => {
    const cands = Array.from(document.querySelectorAll('*')).filter((el) => {
      if (el.scrollHeight - el.clientHeight < 200) return false;
      const s = getComputedStyle(el);
      return /auto|scroll/.test(s.overflowY) && el.clientHeight > 200;
    });
    cands.sort((a, b) => b.scrollHeight - a.scrollHeight);
    const el = cands[0];
    return el
      ? {
          tag: el.tagName.toLowerCase(),
          id: el.id || null,
          clientHeight: el.clientHeight,
          scrollHeight: el.scrollHeight,
        }
      : null;
  });
  evidence.assertions.scroll_container_found = Boolean(evidence.scroll_container);

  await page.screenshot({ path: shotPath });
  await page.screenshot({ path: fullShotPath, fullPage: true });
  evidence.screenshots = { viewport: shotPath, full_page: fullShotPath };

  const failed = Object.entries(evidence.assertions).filter(([, ok]) => !ok);
  if (failed.length) throw new Error(`assertions failed: ${failed.map(([k]) => k).join(', ')}`);
} catch (e) {
  failure = String(e && e.stack ? e.stack : e);
} finally {
  if (browser) await browser.close().catch(() => {});
  server.kill('SIGTERM');
  await new Promise((r) => setTimeout(r, 300));
  if (server.exitCode === null) server.kill('SIGKILL');
}

fs.writeFileSync(serverPath, serverOut.join(''));
fs.writeFileSync(consolePath, evidence.console.join('\n') + '\n');
evidence.console_path = consolePath;
evidence.server_log = serverPath;
if (failure) evidence.failure = failure;
fs.writeFileSync(jsonPath, JSON.stringify(evidence, null, 2) + '\n');

console.log(
  JSON.stringify(
    {
      ok: !failure,
      ready_ms: evidence.ready_ms,
      pages: evidence.before_typing?.pages,
      paragraphs: evidence.before_typing?.paragraphs,
      probe_text: evidence.after_typing?.probe_text,
      assertions: evidence.assertions,
      scroll_container: evidence.scroll_container,
      console_errors: evidence.console.filter((l) => l.startsWith('error:')).length,
      screenshots: evidence.screenshots,
      evidence: jsonPath,
      failure: failure || undefined,
    },
    null,
    2
  )
);
process.exit(failure ? 1 : 0);
