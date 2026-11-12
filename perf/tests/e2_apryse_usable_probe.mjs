/**
 * Drive waitForUsableSurface against an Apryse-like shadow host.
 * Prints { immediate, refusal, lightDomDefault, shadowEditable, expr }.
 * lightDomDefault is the bare contenteditable query for #pageContainer1.
 * That node is inside the shadow root and is never contenteditable, so the
 * default stays false after the rendered flag flips.
 */
import { pathToFileURL } from 'node:url';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const { loadPlaywright } = await import(pathToFileURL(`${repo}/perf/runner/witness.mjs`).href);
const { usableExpression } = await import(pathToFileURL(`${repo}/perf/runner/edit_surface.mjs`).href);
const { waitForUsableSurface } = await import(pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href);

const url = process.argv[2];
if (!url) throw new Error('usage: node e2_apryse_usable_probe.mjs <url>');

const expr = usableExpression('apryse', '#pageContainer1');
const lightDomDefault =
  '(() => { const el = document.querySelector("#pageContainer1");'
  + ' return !!(el && el.isContentEditable && el.getBoundingClientRect().height > 0); })()';
const { chromium } = await loadPlaywright();
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(url, { waitUntil: 'load', timeout: 15000 });
  const evalExpr = (code) => page.evaluate((source) => {
    try {
      return Boolean(eval(source)); // eslint-disable-line no-eval
    } catch {
      return false;
    }
  }, code);
  const immediate = await evalExpr(expr);
  const refusal = await waitForUsableSurface(page, expr);
  const lightDom = await evalExpr(lightDomDefault);
  const shadowEditable = await page.evaluate(() => {
    const host = document.querySelector('apryse-webviewer');
    const el = host && host.shadowRoot && host.shadowRoot.querySelector('#pageContainer1');
    return Boolean(el && el.isContentEditable);
  });
  process.stdout.write(JSON.stringify({
    immediate,
    refusal,
    lightDomDefault: lightDom,
    shadowEditable,
    expr,
  }));
} finally {
  await browser.close();
}
