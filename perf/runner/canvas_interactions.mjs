/** Canvas-editor interaction probes (C07–C10). */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(here, '../../harness/ui');

const DEFAULT_EDIT = '#editor canvas';
const SCROLL_TARGET = '#editor';

function parseArgv(argv) {
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
  return opt;
}

async function loadPlaywright() {
  return import(pathToFileURL(path.join(uiRoot, 'node_modules/playwright/index.mjs')).href);
}

async function nextPaintMs(page) {
  return page.evaluate(async () => {
    const t0 = performance.now();
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    return performance.now() - t0;
  });
}

async function loadSession(opt) {
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    permissions: ['clipboard-read', 'clipboard-write'],
  });
  const corpusBytes = fs.readFileSync(opt.corpus);
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname.endsWith('.docx') || u.pathname === (opt['corpus-route'] || '/sample.docx')) {
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
  await page.goto(opt.url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  await page.waitForFunction(() => window.__DOCX_IMPORTED__ === true, { timeout: 120_000 });
  const waitMs = Number(opt['wait-after-ready'] || 0);
  if (waitMs > 0) await page.waitForTimeout(waitMs);
  return { browser, page };
}

async function probeC07(page, editSelector) {
  const t0 = Date.now();
  await page.locator(editSelector).first().click({ timeout: 30_000, position: { x: 40, y: 40 } });
  await page.keyboard.press('ArrowRight');
  const paint = await nextPaintMs(page);
  return [Date.now() - t0, paint];
}

async function probeC08(page, editSelector) {
  await page.evaluate(() => navigator.clipboard.writeText('perf-canvas-paste'));
  const t0 = Date.now();
  await page.locator(editSelector).first().click({ position: { x: 60, y: 60 } });
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyV');
  await page.keyboard.up('Control');
  const paint = await nextPaintMs(page);
  return [Date.now() - t0, paint];
}

async function probeC09(page, editSelector) {
  await page.locator(editSelector).first().click({ position: { x: 50, y: 50 } });
  await page.keyboard.type('z', { delay: 5 });
  const t0 = Date.now();
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyZ');
  await page.keyboard.up('Control');
  const paint = await nextPaintMs(page);
  return [Date.now() - t0, paint];
}

async function probeC10(page) {
  const t0 = Date.now();
  await page.locator(SCROLL_TARGET).evaluate((el) => {
    el.scrollTop = Math.min(600, Math.max(0, el.scrollHeight - el.clientHeight));
  });
  await nextPaintMs(page);
  const paint = await nextPaintMs(page);
  return [Date.now() - t0, paint];
}

const CRITERION = {
  c07: (page, sel) => probeC07(page, sel),
  c08: (page, sel) => probeC08(page, sel),
  c09: (page, sel) => probeC09(page, sel),
  c10: (page) => probeC10(page),
};

export async function runCanvasCriterion(opt) {
  const criterion = String(opt.criterion || 'c10').toLowerCase();
  const editSelector = opt['edit-selector'] || DEFAULT_EDIT;
  const fn = CRITERION[criterion];
  if (!fn) throw new Error(`unknown canvas criterion ${criterion}`);
  const { browser, page } = await loadSession(opt);
  try {
    const row =
      criterion === 'c10' ? await fn(page) : await fn(page, editSelector);
    const selector = criterion === 'c10' ? SCROLL_TARGET : editSelector;
    return { criterion, outcome: 'measured', samples_ms: row, selector };
  } finally {
    await browser.close();
  }
}

async function main() {
  const opt = parseArgv(process.argv.slice(2));
  const pairs = Math.max(3, Number(opt.pairs || 3));
  const all = [];
  let selector = null;
  for (let i = 0; i < pairs; i++) {
    const row = await runCanvasCriterion(opt);
    selector = row.selector;
    all.push(...row.samples_ms);
  }
  process.stdout.write(
    JSON.stringify({
      criterion: opt.criterion,
      outcome: 'measured',
      samples_ms: all,
      pairs,
      selector,
    }),
  );
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
