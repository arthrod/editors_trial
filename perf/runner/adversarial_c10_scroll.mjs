/**
 * Scroll the largest vertical scroll container and measure time until next paint.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(here, '../../harness/ui');
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

const url = opt.url;
const corpusFile = opt.corpus;
const corpusRoute = opt['corpus-route'] || '/corpus.docx';
const sampleRoute = opt['sample-route'] || corpusRoute;
const readySelector = opt['ready-selector'] || '.status-ok';
const readyJs = opt['ready-js'] || '';
const readyText = opt['ready-text'] || '';
const pairs = Math.max(1, Number(opt.pairs || 3));
const waitAfterReadyMs = Number(opt['wait-after-ready'] || 0);

const corpusBytes = fs.readFileSync(corpusFile);

async function loadPlaywright() {
  return import(pathToFileURL(path.join(uiRoot, 'node_modules/playwright/index.mjs')).href);
}

async function waitForReady(page) {
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
      ({ text }) => (document.body.innerText || '').includes(text),
      { text: readyText },
      { timeout: 120_000 },
    );
  } else {
    await page.waitForSelector(readySelector, { timeout: 120_000, state: 'visible' });
  }
  if (waitAfterReadyMs > 0) await page.waitForTimeout(waitAfterReadyMs);
}

async function scrollFrameMs(page) {
  const t0 = Date.now();
  await page.evaluate(() => {
    const cands = Array.from(document.querySelectorAll('*')).filter((el) => {
      if (el.scrollHeight - el.clientHeight < 200) return false;
      const s = getComputedStyle(el);
      return /auto|scroll/.test(s.overflowY) && el.clientHeight > 200;
    });
    cands.sort((a, b) => b.scrollHeight - a.scrollHeight);
    if (!cands.length) return;
    const el = cands[0];
    el.scrollTop = Math.round((el.scrollHeight - el.clientHeight) * 0.5);
    el.dispatchEvent(new Event('scroll', { bubbles: true }));
  });
  await page.evaluate(async () => {
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    await new Promise((r) => requestAnimationFrame(() => r(null)));
  });
  return Date.now() - t0;
}

async function onePair(page) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  await waitForReady(page);
  return scrollFrameMs(page);
}

async function routeCorpus(context) {
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === corpusRoute || u.pathname === sampleRoute) {
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

const { chromium } = await loadPlaywright();
const samples = [];
for (let i = 0; i < pairs; i++) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await routeCorpus(context);
  const page = await context.newPage();
  samples.push(await onePair(page));
  await browser.close();
}

process.stdout.write(JSON.stringify({ scroll_frame_ms: samples }));
