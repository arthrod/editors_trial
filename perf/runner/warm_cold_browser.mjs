/**
 * Paired warm/cold browser probes for the perf harness.
 *
 * Usage (from repo root, with a dev server already listening):
 *   node perf/runner/warm_cold_browser.mjs \
 *     --driver playwright \
 *     --url http://127.0.0.1:5208/ \
 *     --corpus /abs/fixture.docx \
 *     --corpus-route /corpus.docx \
 *     --ready-selector ".status-ok" \
 *     --edit-selector "[data-slate-editor='true']" \
 *     --pairs 3
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
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

const driver = opt.driver || 'playwright';
const url = opt.url;
const corpusFile = opt.corpus;
const corpusRoute = opt['corpus-route'] || '/corpus.docx';
const readySelector = opt['ready-selector'] || '.status-ok';
const readyText = opt['ready-text'] || '';
const readyJs = opt['ready-js'] || '';
const editSelector = opt['edit-selector'] || '[contenteditable="true"]';
const preEditClick = opt['pre-edit-click'] || '';
const skipEdit = opt['skip-edit'] === 'true' || opt['skip-edit'] === true;
const pairs = Math.max(1, Number(opt.pairs || 3));
const sampleRoute = opt['sample-route'] || corpusRoute;
const waitAfterReadyMs = Number(opt['wait-after-ready'] || 0);

if (!url || !corpusFile) {
  console.error('warm_cold_browser: --url and --corpus are required');
  process.exit(2);
}

const corpusBytes = fs.readFileSync(corpusFile);

async function nextPaintMs(page) {
  return page.evaluate(async () => {
    const t0 = performance.now();
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    return performance.now() - t0;
  });
}

const MODEL_MARKS = [
  'docxodus-model-ready',
  'superdoc-model-ready',
  'genoffice-model-ready',
  'plate-import-done',
  'canvas-model-import-done',
];
const USABLE_MARKS = [
  'docxodus-first-usable',
  'superdoc-first-usable',
  'genoffice-first-usable',
  'plate-first-usable',
  'canvas-first-usable',
];

async function waitForMark(page, names, timeoutMs = 120_000) {
  await page.waitForFunction(
    (list) => list.some((n) => performance.getEntriesByName(n).length > 0),
    names,
    { timeout: timeoutMs },
  );
  return page.evaluate((list) => {
    for (const n of list) {
      const e = performance.getEntriesByName(n)[0];
      if (e) return e.startTime;
    }
    return null;
  }, names);
}

async function readModelAndUsableMs(page, selector) {
  let modelMs = await waitForMark(page, MODEL_MARKS).catch(() => null);
  const waitMs = await waitForReady(page, selector);
  let usableMs = await waitForMark(page, USABLE_MARKS).catch(() => null);
  if (usableMs == null) usableMs = waitMs;
  if (modelMs == null) {
    const hook = await page
      .evaluate(() => window.__GENOFFICE_PERF__?.modelReadyMs ?? null)
      .catch(() => null);
    if (hook != null) modelMs = hook;
  }
  if (modelMs == null && usableMs != null) modelMs = usableMs;
  return { model_ready_browser_ms: modelMs, first_usable_ms: usableMs };
}

async function waitForReady(page, selector, timeoutMs = 120_000) {
  const t0 = Date.now();
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
  } else if (readyText) {
    await page.waitForFunction(
      ({ sel, text }) => {
        const el = document.querySelector(sel);
        return Boolean(el && el.textContent && el.textContent.includes(text));
      },
      { sel: selector, text: readyText },
      { timeout: timeoutMs },
    );
  } else {
    await page.waitForSelector(selector, { timeout: timeoutMs, state: 'visible' });
  }
  if (waitAfterReadyMs > 0) {
    await page.waitForTimeout(waitAfterReadyMs);
  }
  return Date.now() - t0;
}

async function performEdit(page, selector) {
  const t0 = Date.now();
  if (preEditClick) {
    await page.click(preEditClick, { timeout: 30_000 });
    await page.waitForTimeout(400);
  }
  const target = page.locator(selector).first();
  await target.click({ timeout: 30_000 });
  await page.keyboard.type('x', { delay: 12 });
  const paint = await nextPaintMs(page);
  return { edit_ms: Date.now() - t0, paint_ms: paint };
}

async function routeCorpus(context, routePath, bytes) {
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === routePath || u.pathname === sampleRoute) {
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

async function loadPlaywright() {
  const spec = path.join(uiRoot, 'node_modules/playwright/index.mjs');
  return import(pathToFileURL(spec).href);
}

async function loadPuppeteer() {
  const spec = path.join(uiRoot, 'node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js');
  return import(pathToFileURL(spec).href);
}

async function runPlaywrightPair() {
  const { chromium } = await loadPlaywright();
  const launchT0 = Date.now();
  const browser = await chromium.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  const browserLaunchMs = Date.now() - launchT0;

  const coldContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await routeCorpus(coldContext, corpusRoute, corpusBytes);
  const coldPage = await coldContext.newPage();

  const navT0 = Date.now();
  await coldPage.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  const documentNavigationMs = Date.now() - navT0;

  const { model_ready_browser_ms: modelReadyMs, first_usable_ms: firstUsableMs } =
    await readModelAndUsableMs(coldPage, readySelector);
  let coldEdit = { edit_ms: null, paint_ms: null };
  let warmEdit = { edit_ms: null, paint_ms: null };
  const warmBurst = [];
  const coldBurst = [];
  if (!skipEdit) {
    coldEdit = await performEdit(coldPage, editSelector);
    for (let i = 0; i < 3; i++) {
      coldBurst.push((await performEdit(coldPage, editSelector)).edit_ms);
    }
  }

  const reloadT0 = Date.now();
  await coldPage.reload({ waitUntil: 'domcontentloaded', timeout: 120_000 });
  await readModelAndUsableMs(coldPage, readySelector);
  const documentReloadSameContextMs = Date.now() - reloadT0;

  if (!skipEdit) {
    warmEdit = await performEdit(coldPage, editSelector);
    for (let i = 0; i < 3; i++) {
      warmBurst.push((await performEdit(coldPage, editSelector)).edit_ms);
    }
  }

  await coldContext.close();
  await browser.close();

  return {
    browser_launch_only_ms: browserLaunchMs,
    document_navigation_only_ms: documentNavigationMs,
    model_ready_browser_ms: modelReadyMs,
    document_reload_same_context_ms: documentReloadSameContextMs,
    cold: {
      first_usable_ms: firstUsableMs,
      model_ready_browser_ms: modelReadyMs,
      single_edit_ms: coldEdit.edit_ms,
      presented_frame_ms: coldEdit.paint_ms,
      sustained_typing_median_ms:
        coldBurst.length > 0 ? coldBurst.sort((a, b) => a - b)[Math.floor(coldBurst.length / 2)] : null,
    },
    warm: {
      single_edit_ms: warmEdit.edit_ms,
      presented_frame_ms: warmEdit.paint_ms,
      sustained_typing_median_ms: warmBurst.sort((a, b) => a - b)[1],
    },
  };
}

async function runPuppeteerPair() {
  const puppeteer = await loadPuppeteer();
  const launchT0 = Date.now();
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  const browserLaunchMs = Date.now() - launchT0;
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  await page.setRequestInterception(true);
  page.on('request', (req) => {
    const u = new URL(req.url());
    if (u.pathname === corpusRoute || u.pathname === sampleRoute) {
      req.respond({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: corpusBytes,
      });
      return;
    }
    req.continue();
  });

  const navT0 = Date.now();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  const documentNavigationMs = Date.now() - navT0;

  await page.waitForSelector(readySelector, { visible: true, timeout: 120_000 });
  const modelReadyMs = Date.now() - navT0;

  const coldEditT0 = Date.now();
  await page.click(editSelector);
  await page.keyboard.type('x', { delay: 12 });
  const coldEditMs = Date.now() - coldEditT0;

  const reloadT0 = Date.now();
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 120_000 });
  await page.waitForSelector(readySelector, { visible: true, timeout: 120_000 });
  const documentReloadSameContextMs = Date.now() - reloadT0;

  const warmEditT0 = Date.now();
  await page.click(editSelector);
  await page.keyboard.type('x', { delay: 12 });
  const warmEditMs = Date.now() - warmEditT0;

  await browser.close();

  return {
    browser_launch_only_ms: browserLaunchMs,
    document_navigation_only_ms: documentNavigationMs,
    model_ready_browser_ms: modelReadyMs,
    document_reload_same_context_ms: documentReloadSameContextMs,
    cold: {
      first_usable_ms: modelReadyMs,
      model_ready_browser_ms: modelReadyMs,
      single_edit_ms: coldEditMs,
    },
    warm: {
      single_edit_ms: warmEditMs,
    },
  };
}

async function coldOnlyFreshContext() {
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await routeCorpus(context, corpusRoute, corpusBytes);
  const page = await context.newPage();
  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  await waitForReady(page, readySelector);
  const ms = Date.now() - t0;
  await browser.close();
  return ms;
}

const collected = [];
for (let i = 0; i < pairs; i++) {
  if (driver === 'puppeteer') {
    collected.push(await runPuppeteerPair());
  } else {
    collected.push(await runPlaywrightPair());
  }
}

let freshContextMedians = [];
if (opt['fresh-context-probe'] !== 'false') {
  const freshSamples = [];
  for (let i = 0; i < Math.min(pairs, 3); i++) {
    freshSamples.push(await coldOnlyFreshContext());
  }
  freshContextMedians = freshSamples;
}

const result = {
  driver,
  url,
  corpus_route: corpusRoute,
  ready_selector: readySelector,
  edit_selector: editSelector,
  pairs: collected,
  fresh_context_load_ms: freshContextMedians,
};

process.stdout.write(JSON.stringify(result));
