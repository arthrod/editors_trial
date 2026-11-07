/** Canvas-editor interaction probes (C07, C10). */
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

export async function runCanvasCriterion(opt) {
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const corpusBytes = fs.readFileSync(opt.corpus);
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname.endsWith('.docx')) {
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
  const samples = [];
  const criterion = String(opt.criterion || 'c10').toLowerCase();
  if (criterion === 'c07') {
    const t0 = Date.now();
    await page.click('#editor canvas', { timeout: 30_000 });
    await page.keyboard.press('ArrowRight');
    samples.push(Date.now() - t0);
  } else {
    const t0 = Date.now();
    await page.mouse.wheel(0, 600);
    await page.evaluate(async () => {
      await new Promise((r) => requestAnimationFrame(() => r(null)));
      await new Promise((r) => requestAnimationFrame(() => r(null)));
    });
    samples.push(Date.now() - t0);
  }
  await browser.close();
  return { criterion, outcome: 'measured', samples_ms: samples };
}

async function main() {
  const opt = parseArgv(process.argv.slice(2));
  const pairs = Math.max(1, Number(opt.pairs || 3));
  const all = [];
  for (let i = 0; i < pairs; i++) {
    const row = await runCanvasCriterion(opt);
    all.push(...row.samples_ms);
  }
  process.stdout.write(JSON.stringify({ ...opt, outcome: 'measured', samples_ms: all, pairs }));
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
