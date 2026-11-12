/**
 * Drive waitForUsableSurface against a Folio-like host fixture.
 * Prints { immediate, refusal } as JSON. immediate is the expression at load,
 * before the wait's poll interval, so a shell that gains blocks later is
 * still observed while it has none.
 */
import { pathToFileURL } from 'node:url';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const { loadPlaywright } = await import(pathToFileURL(`${repo}/perf/runner/witness.mjs`).href);
const { usableExpression } = await import(pathToFileURL(`${repo}/perf/runner/edit_surface.mjs`).href);
const { waitForUsableSurface } = await import(pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href);

const url = process.argv[2];
if (!url) throw new Error('usage: node e2_folio_usable_probe.mjs <url>');

const expr = usableExpression('folio', '[data-page-number]');
const { chromium } = await loadPlaywright();
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(url, { waitUntil: 'load', timeout: 15000 });
  const immediate = await page.evaluate((code) => {
    try {
      return Boolean(eval(code)); // eslint-disable-line no-eval
    } catch {
      return false;
    }
  }, expr);
  const refusal = await waitForUsableSurface(page, expr);
  process.stdout.write(JSON.stringify({ immediate, refusal }));
} finally {
  await browser.close();
}
