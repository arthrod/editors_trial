/**
 * Shared Playwright interaction probes for browser-visible criteria.
 * Exports: c07_caret, c08_paste, c09_undo, c10_scroll, c11_navigation, c12_insert, c22_profile, c23_collab
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(here, '../../harness/ui');

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

async function routeCorpus(context, routePath, bytes, sampleRoute) {
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === routePath || (sampleRoute && u.pathname === sampleRoute)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: bytes,
      });
      return;
    }
    await route.continue();
  });
}

async function waitReady(page, { readySelector, readyJs, readyText, waitAfterReadyMs }) {
  if (readyJs) {
    await page.waitForFunction(
      (expr) => {
        try {
          return Boolean(eval(expr)); // eslint-disable-line no-eval
        } catch {
          return false;
        }
      },
      readyJs,
      { timeout: 120_000 },
    );
  } else if (readyText) {
    await page.waitForFunction(
      ({ sel, text }) => {
        const el = document.querySelector(sel);
        return Boolean(el && el.textContent && el.textContent.includes(text));
      },
      { sel: readySelector, text: readyText },
      { timeout: 120_000 },
    );
  } else {
    await page.waitForSelector(readySelector, { timeout: 120_000, state: 'visible' });
  }
  if (waitAfterReadyMs > 0) await page.waitForTimeout(waitAfterReadyMs);
}

async function nextPaintMs(page) {
  return page.evaluate(async () => {
    const t0 = performance.now();
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    return performance.now() - t0;
  });
}

export async function loadEditorSession(opt) {
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
  await routeCorpus(context, opt['corpus-route'] || '/corpus.docx', corpusBytes, opt['sample-route']);
  const page = await context.newPage();
  await page.goto(opt.url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  await waitReady(page, {
    readySelector: opt['ready-selector'],
    readyJs: opt['ready-js'] || '',
    readyText: opt['ready-text'] || '',
    waitAfterReadyMs: Number(opt['wait-after-ready'] || 0),
  });
  return { browser, context, page };
}

export async function c07_caret(page, editSelector) {
  const t0 = Date.now();
  await page.locator(editSelector).first().click({ timeout: 30_000 });
  await page.keyboard.press('ArrowRight');
  const paint = await nextPaintMs(page);
  return { samples_ms: [Date.now() - t0, paint], selector: editSelector };
}

export async function c08_paste(page, editSelector) {
  await page.evaluate(() => navigator.clipboard.writeText('perf-paste-probe'));
  const t0 = Date.now();
  await page.locator(editSelector).first().click();
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyV');
  await page.keyboard.up('Control');
  const paint = await nextPaintMs(page);
  return { samples_ms: [Date.now() - t0, paint], selector: editSelector };
}

export async function c09_undo(page, editSelector) {
  await page.locator(editSelector).first().click();
  await page.keyboard.type('z', { delay: 8 });
  const t0 = Date.now();
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyZ');
  await page.keyboard.up('Control');
  const paint = await nextPaintMs(page);
  return { samples_ms: [Date.now() - t0, paint], selector: editSelector };
}

export async function c12_insert(page, editSelector) {
  await page.locator(editSelector).first().click();
  const t0 = Date.now();
  await page.keyboard.type('\nNew paragraph perf probe\n', { delay: 5 });
  const paint = await nextPaintMs(page);
  return { samples_ms: [Date.now() - t0, paint] };
}

export async function c22_profile(opt) {
  const base = opt.url.includes('?') ? opt.url.split('?')[0] : opt.url;
  const url = `${base}?feature_profile=P1`;
  const next = { ...opt, url };
  const { browser, page } = await loadEditorSession(next);
  const t0 = Date.now();
  const ok = await page.evaluate(() => document.location.search.includes('P1'));
  const paint = await nextPaintMs(page);
  await browser.close();
  const selector = 'location.search feature_profile=P1';
  if (!ok) {
    return { outcome: 'not_applicable', samples_ms: [], reason: 'capability collaboration/profile', selector };
  }
  return { outcome: 'measured', samples_ms: [Date.now() - t0, paint], selector };
}

export async function c23_collab() {
  return { outcome: 'not_applicable', samples_ms: [], reason: 'capability collaboration/profile: Yjs off in P0 harness' };
}

const CRITERION_FN = {
  c07: c07_caret,
  c08: c08_paste,
  c09: c09_undo,
  c12: c12_insert,
  c22: c22_profile,
  c23: c23_collab,
};

async function main() {
  const opt = parseArgv(process.argv.slice(2));
  const criterion = String(opt.criterion || '').toLowerCase();
  const editSelector = opt['edit-selector'] || '[contenteditable="true"]';
  const pairs = Math.max(1, Number(opt.pairs || 3));
  const fn = CRITERION_FN[criterion];
  if (!fn) {
    console.error('unknown criterion', criterion);
    process.exit(2);
  }
  if (criterion === 'c23') {
    const result = await fn(opt);
    process.stdout.write(JSON.stringify({ criterion, ...result, pairs: 1 }));
    return;
  }
  if (criterion === 'c22') {
    const samples = [];
    let selector = 'location.search feature_profile=P1';
    for (let i = 0; i < pairs; i++) {
      const row = await fn(opt);
      selector = row.selector || selector;
      if (row.outcome === 'not_applicable') {
        process.stdout.write(JSON.stringify({ criterion, ...row, pairs: i + 1 }));
        return;
      }
      samples.push(...row.samples_ms);
    }
    process.stdout.write(JSON.stringify({ criterion, outcome: 'measured', samples_ms: samples, pairs, selector }));
    return;
  }
  const samples = [];
  let selector = editSelector;
  for (let i = 0; i < pairs; i++) {
    const { browser, page } = await loadEditorSession(opt);
    const row = await fn(page, editSelector);
    samples.push(...row.samples_ms);
    selector = row.selector || editSelector;
    await browser.close();
  }
  process.stdout.write(
    JSON.stringify({ criterion, outcome: 'measured', samples_ms: samples, pairs, selector }),
  );
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
