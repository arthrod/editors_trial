/**
 * Exploration helper (not a deliverable): logs into Fidus Writer and dumps
 * the DOM structure of the pages we need, so we can pick stable selectors.
 *
 *   node explore.mjs <step>
 *     step = login | overview | editor
 */
import { chromium } from 'playwright';

const BASE = process.env.FIDUS_BASE || 'http://localhost:5209';
const step = process.argv[2] || 'overview';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on('pageerror', (e) => console.log('PAGEERROR', String(e)));
page.on('console', (m) => {
  if (m.type() === 'error') console.log('CONSOLE-ERR', m.text().slice(0, 300));
});

await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
await page.fill('#id-login', 'corpus');
await page.fill('#id-password', 'corpus-pass-2026');
await Promise.all([
  page.waitForNavigation({ timeout: 30000 }).catch(() => {}),
  page.click('button[type=submit], input[type=submit], .fw-button:has-text("LOG IN")'),
]);
await page.waitForTimeout(3000);
console.log('AFTER LOGIN url=', page.url());
console.log('TITLE=', await page.title());

if (step === 'login') {
  console.log((await page.locator('body').innerText()).slice(0, 2000));
  await browser.close();
  process.exit(0);
}

// overview page
await page.goto(BASE + '/documents/overview/', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(3000);
console.log('OVERVIEW url=', page.url());
console.log('--- body text ---');
console.log((await page.locator('body').innerText()).slice(0, 3000));

const btns = await page.evaluate(() =>
  Array.from(document.querySelectorAll('button,a,[role=button]'))
    .map((b) => ({
      tag: b.tagName,
      id: b.id,
      cls: String(b.className).slice(0, 50),
      text: (b.innerText || b.getAttribute('aria-label') || b.title || '').trim().slice(0, 45),
    }))
    .filter((b) => b.text)
);
console.log('BUTTONS:', JSON.stringify(btns, null, 1).slice(0, 4000));

const inputs = await page.evaluate(() =>
  Array.from(document.querySelectorAll('input')).map((i) => ({
    type: i.type,
    accept: i.accept,
    id: i.id,
    cls: String(i.className).slice(0, 40),
  }))
);
console.log('INPUTS:', JSON.stringify(inputs, null, 1));

if (step === 'overview') {
  await browser.close();
  process.exit(0);
}

// editor step: open first document link
const link = await page.$('a[href*="/editor/"]');
if (link) {
  await link.click();
  await page.waitForTimeout(8000);
  console.log('EDITOR url=', page.url());
  console.log('--- editor body text (first 2500) ---');
  console.log((await page.locator('body').innerText()).slice(0, 2500));
  const einputs = await page.evaluate(() =>
    Array.from(document.querySelectorAll('input')).map((i) => ({
      type: i.type, accept: i.accept, id: i.id,
      cls: String(i.className).slice(0, 40),
      visible: i.offsetParent !== null,
    }))
  );
  console.log('EDITOR INPUTS:', JSON.stringify(einputs, null, 1));
}
await browser.close();
