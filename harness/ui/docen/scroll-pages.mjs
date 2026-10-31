/**
 * Helper for the Docen rendering study: load the corpus once, then capture
 * every page of the canvas so the constructs on page 3+ can be inspected.
 *
 * Docen renders the document into a <canvas> (LeaferJS stage) inside the
 * component's shadow root, so there is no light-DOM text for the driver's
 * --scroll-text to find. Scrolling therefore has to target the canvas
 * scroll container directly.
 */
import fs from 'node:fs';
import { chromium } from 'playwright';

const FIXTURE = '/Users/arthrod/temp/T/editors_trial/fixture/complex.docx';
const OUTDIR = '/Users/arthrod/temp/T/editors_trial/out/ui';
const URL = 'http://localhost:5202/document.html';

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1500 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(`[console] ${m.text()}`);
});

await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 45000 });
await page.waitForSelector('#file-input', { state: 'attached', timeout: 30000 });
await page.setInputFiles('#file-input', FIXTURE);
await page.waitForFunction(
  () => document.querySelector('docen-document')?.getAttribute('filename') === 'complex.docx',
  null,
  { timeout: 60000 },
);
await page.waitForTimeout(12000);

// --- map the scroll model -------------------------------------------------
const map = await page.evaluate(() => {
  const el = document.querySelector('docen-document');
  const root = el.shadowRoot;
  const all = Array.from(root.querySelectorAll('*'));
  const scrollables = all
    .filter((n) => n.scrollHeight > n.clientHeight + 4 && n.clientHeight > 100)
    .map((n) => ({
      tag: n.tagName,
      cls: n.className,
      scrollTop: n.scrollTop,
      scrollHeight: n.scrollHeight,
      clientHeight: n.clientHeight,
    }));
  // is the document text anywhere in the light DOM?
  const lightText = document.body.innerText || '';
  const shadowText = root.textContent || '';
  return {
    scrollables,
    lightDomHasCorpusText:
      lightText.includes('A sentence with a comment') ||
      lightText.includes('Text box content'),
    shadowHasCorpusText: shadowText.includes('A sentence with a comment'),
    lightDomLen: lightText.length,
  };
});
console.log(JSON.stringify(map, null, 2));

// --- capture every page ----------------------------------------------------
const pages = await page.evaluate(() => {
  const el = document.querySelector('docen-document');
  const root = el.shadowRoot;
  const all = Array.from(root.querySelectorAll('*'));
  const sc = all.filter((n) => n.scrollHeight > n.clientHeight + 4 && n.clientHeight > 100);
  const target = sc.sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
  const pages = root.querySelectorAll('.canvas-pages > *');
  return {
    scrollTag: target ? target.tagName + '.' + target.className : null,
    pageCount: pages.length,
    scrollHeight: target?.scrollHeight,
    clientHeight: target?.clientHeight,
  };
});
console.log(JSON.stringify(pages, null, 2));

for (let i = 0; i < pages.pageCount; i++) {
  const ok = await page.evaluate((idx) => {
    const el = document.querySelector('docen-document');
    const root = el.shadowRoot;
    const all = Array.from(root.querySelectorAll('*'));
    const sc = all.filter((n) => n.scrollHeight > n.clientHeight + 4 && n.clientHeight > 100);
    const target = sc.sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
    if (!target) return false;
    const per = target.scrollHeight / 6;
    target.scrollTop = Math.round(per * idx);
    return true;
  }, i);
  await page.waitForTimeout(2500);
  const png = `${OUTDIR}/docen_page${i + 1}.png`;
  await page.screenshot({ path: png });
  console.log(`page ${i + 1} -> ${png} (scroll ok=${ok})`);
}

console.log('errors:', JSON.stringify(errors.slice(0, 10), null, 2));
await browser.close();
