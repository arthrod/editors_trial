import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(here, '../../harness/ui');

const opt = {};
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (!a.startsWith('--')) continue;
  const key = a.slice(2);
  const next = process.argv[i + 1];
  if (next && !next.startsWith('--')) {
    opt[key] = next;
    i++;
  } else opt[key] = true;
}

async function loadPlaywright() {
  return import(pathToFileURL(path.join(uiRoot, 'node_modules/playwright/index.mjs')).href);
}

const { chromium } = await loadPlaywright();
const corpus = fs.readFileSync(opt.corpus);
const readySelector = opt['ready-selector'] || '#editor';
const markNames = [
  'docxodus-model-ready',
  'superdoc-model-ready',
  'genoffice-model-ready',
  'plate-import-done',
  'canvas-model-import-done',
];
const samples = [];
for (let i = 0; i < Number(opt.pairs || 3); i++) {
  const t0 = Date.now();
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext();
  await ctx.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname.endsWith('.docx')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: corpus,
      });
      return;
    }
    await route.continue();
  });
  const page = await ctx.newPage();
  await page.goto(opt.url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  try {
    await page.waitForFunction(
      (names) => names.some((n) => performance.getEntriesByName(n).length > 0),
      markNames,
      { timeout: 120_000 },
    );
  } catch {
    await page.waitForSelector(readySelector, { timeout: 120_000 });
  }
  const load_ms = Date.now() - t0;
  const closeT0 = Date.now();
  await browser.close();
  samples.push({ load_ms, unload_ms: Date.now() - closeT0 });
}
process.stdout.write(JSON.stringify({ samples }));
