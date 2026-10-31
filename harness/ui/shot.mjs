/**
 * Shared browser driver for the rendering study.
 *
 * Two ways to get the corpus into the editor under test:
 *
 *   --serve-as <path> --file <docx>
 *       The app is asked to open /path (e.g. /sample.docx).  The request is
 *       intercepted and the corpus bytes are returned instead.  Nothing in
 *       the read-only repo/ tree is touched.
 *
 *   --file <docx> [--file-selector <css>]
 *       The app has a file input; Playwright sets it directly.  Falls back to
 *       the first input[type=file] on the page.
 *
 * usage:
 *   node shot.mjs --name <slug> --url <url> [--serve-as <path> --file <docx>]
 *                  [--file <docx>] [--file-selector <css>]
 *                  [--wait <ms>] [--wait-for <text>] [--click <css> ...]
 *                  [--viewport <WxH>] [--full-page] [--probe <js-file>]
 *                  [--outdir <dir>]
 *
 * Writes <outdir>/<name>.png and <outdir>/<name>.json (console log, errors,
 * probe result, measured geometry).
 */
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a.startsWith('--')) {
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith('--')) {
      opt[key] = true;
    } else {
      opt[key] = next;
      i++;
    }
  }
}

const name = opt.name || 'shot';
const url = opt.url;
if (!url) {
  console.error('--url is required');
  process.exit(2);
}
const outdir = opt.outdir || path.resolve('shots');
fs.mkdirSync(outdir, { recursive: true });

const [vw, vh] = (opt.viewport || '1440x900').split('x').map(Number);
const waitMs = Number(opt.wait || 6000);
const fullPage = !!opt['full-page'];

const consoleLog = [];
const pageErrors = [];
const failedRequests = [];

const browser = await chromium.launch({
  headless: true,
  args: ['--font-render-hinting=none', '--disable-lcd-text'],
});
const context = await browser.newContext({
  viewport: { width: vw, height: vh },
  deviceScaleFactor: Number(opt.dpr || 1),
});
const page = await context.newPage();

page.on('console', (m) => {
  consoleLog.push(`[${m.type()}] ${m.text()}`);
});
page.on('pageerror', (e) => pageErrors.push(String(e && e.stack ? e.stack : e)));
page.on('requestfailed', (r) => {
  failedRequests.push(`${r.method()} ${r.url()} :: ${r.failure()?.errorText}`);
});

// ---- intercept the document request and serve the corpus instead ----------
if (opt['serve-as'] && opt.file) {
  const bytes = fs.readFileSync(opt.file);
  const routePath = opt['serve-as'];
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === routePath) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: bytes,
      });
    } else {
      await route.continue();
    }
  });
}

let probe = null;
let navFailed = null;
try {
  const res = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  consoleLog.push(`[nav] ${res && res.status()} ${url}`);
  if (!res || res.status() >= 400) navFailed = `HTTP ${res && res.status()}`;
} catch (e) {
  consoleLog.push(`[nav-error] ${e.message}`);
  navFailed = e.message.split('\n')[0];
}

// ---- optional clicks ------------------------------------------------------
for (const c of [].concat(opt.click || [])) {
  if (c === true) continue;
  try {
    await page.waitForSelector(c, { timeout: 15000 });
    await page.click(c, { timeout: 10000 });
    consoleLog.push(`[click] ${c}`);
    await page.waitForTimeout(1200);
  } catch (e) {
    consoleLog.push(`[click-error] ${c} :: ${e.message}`);
  }
}

// ---- optionally drive a file input ---------------------------------------
if (opt.file && !opt['serve-as']) {
  let sel = opt['file-selector'];
  if (!sel && opt['file-accept']) {
    // wait for the app to mount its file inputs first
    try {
      await page.waitForSelector('input[type=file]', { timeout: 25000 });
    } catch { /* fall through to the generic selector */ }
    // pick the first input whose accept attribute mentions the wanted type,
    // e.g. "docx" -> the DOCX opener rather than the inline-image uploader
    try {
      sel = await page.evaluate((needle) => {
        const ins = Array.from(document.querySelectorAll('input[type=file]'));
        const hit = ins.find((i) => (i.getAttribute('accept') || '').toLowerCase().includes(needle));
        if (!hit) return null;
        hit.setAttribute('data-harness-target', '1');
        return 'input[data-harness-target="1"]';
      }, String(opt['file-accept']).toLowerCase());
      consoleLog.push(`[file-accept] ${opt['file-accept']} -> ${sel || 'no match'}`);
    } catch (e) {
      consoleLog.push(`[file-accept-error] ${e.message}`);
    }
  }
  sel = sel || 'input[type=file]';
  try {
    // the input is usually hidden behind a styled button, so wait for it to be
    // ATTACHED rather than visible
    await page.waitForSelector(sel, { state: 'attached', timeout: 20000 });
    await page.setInputFiles(sel, path.resolve(opt.file));
    consoleLog.push(`[file-input] set ${sel} <- ${opt.file}`);
  } catch (e) {
    consoleLog.push(`[file-input-error] ${e.message}`);
  }
}

// ---- wait for readiness ---------------------------------------------------
if (opt['wait-for']) {
  try {
    await page.waitForFunction(
      (t) => document.body && document.body.innerText.includes(t),
      opt['wait-for'],
      { timeout: 45000 }
    );
    consoleLog.push(`[wait-for] matched "${opt['wait-for']}"`);
  } catch (e) {
    consoleLog.push(`[wait-for-error] ${e.message}`);
  }
}
await page.waitForTimeout(waitMs);

// ---- optional scroll to a piece of text -----------------------------------
// The corpus puts its interesting constructs on page 3 (the table, the
// comment, the picture, the chart).  Scrolling the text into view is more
// reliable than guessing pixel offsets, because every editor has a different
// page/scroll model.
if (opt['scroll-text']) {
  const target = String(opt['scroll-text']);
  try {
    const ok = await page.evaluate((t) => {
      const needle = t.toLowerCase();
      let best = null;
      let bestLen = Infinity;
      for (const n of document.querySelectorAll('body *')) {
        // innerText, not textContent: an editor that splits a phrase across
        // two spans still shows the phrase to the reader, but no single
        // element's textContent contains it.
        const txt = (n.innerText || '').toLowerCase();
        if (!txt.includes(needle)) continue;
        if (txt.length < bestLen) { best = n; bestLen = txt.length; }
      }
      if (!best) return false;
      best.scrollIntoView({ block: 'center', inline: 'center' });
      return true;
    }, target);
    consoleLog.push(`[scroll-text] "${target}" -> ${ok ? 'found' : 'NOT FOUND'}`);
    await page.waitForTimeout(1500);
  } catch (e) {
    consoleLog.push(`[scroll-text-error] ${e.message}`);
  }
}

// ---- optional probe --------------------------------------------------------
if (opt.probe && fs.existsSync(opt.probe)) {
  const mod = await import(path.resolve(opt.probe));
  try {
    probe = await mod.probe(page);
  } catch (e) {
    probe = { error: String(e && e.stack ? e.stack : e) };
  }
}

const png = path.join(outdir, `${name}.png`);
await page.screenshot({ path: png, fullPage });

const meta = {
  name,
  url,
  viewport: [vw, vh],
  fullPage,
  title: await page.title().catch(() => ''),
  finalUrl: page.url(),
  consoleLog: consoleLog.slice(-60),
  pageErrors,
  failedRequests: failedRequests.slice(-30),
  probe,
};
fs.writeFileSync(path.join(outdir, `${name}.json`), JSON.stringify(meta, null, 2));

if (navFailed) {
  console.error(`FAILED ${name}: navigation to ${url} failed - ${navFailed}`);
  console.error('  no screenshot was written; the server is probably down.');
  await browser.close();
  process.exit(3);
}
console.log(`OK ${name} -> ${png}`);
if (pageErrors.length) console.log(`  pageErrors: ${pageErrors.length}`);
await browser.close();
