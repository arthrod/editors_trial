/**
 * A/B check: does the component's setShowMarks(false) actually repaint the
 * canvas (drop the ↵/→ marks)?  Loads the corpus, crops the same text band
 * with marks on and after the toggle, and reports whether the pixels differ.
 */
import fs from 'node:fs';
import { chromium } from 'playwright';

const FIXTURE = '/Users/arthrod/temp/T/editors_trial/fixture/complex.docx';
const URL = 'http://localhost:5202/document.html';

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1400 } });
const page = await context.newPage();
await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 45000 });
await page.waitForSelector('#file-input', { state: 'attached', timeout: 30000 });
await page.setInputFiles('#file-input', FIXTURE);
await page.waitForFunction(
  () => document.querySelector('docen-document')?.getAttribute('filename') === 'complex.docx',
  null,
  { timeout: 60000 },
);
await page.waitForTimeout(12000);

const clip = { x: 500, y: 335, width: 240, height: 40 };
const on = await page.screenshot({ clip });
await page.evaluate(() => document.querySelector('docen-document')?.setShowMarks(false));
await page.waitForTimeout(6000);
const off = await page.screenshot({ clip });

fs.writeFileSync('/tmp/marks_on.png', on);
fs.writeFileSync('/tmp/marks_off.png', off);
console.log('identical bytes:', Buffer.compare(on, off) === 0);
console.log('on bytes', on.length, 'off bytes', off.length);
console.log(
  'stage flag now:',
  await page.evaluate(() => {
    const el = document.querySelector('docen-document');
    return { attr: el?.hasAttribute('show-marks'), get: el?.getShowMarks?.() };
  }),
);
await browser.close();
