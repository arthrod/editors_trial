import { chromium } from 'playwright';
const url = process.argv[2];
const b = await chromium.launch({ headless: true });
const p = await b.newPage();
await p.goto(url, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(5000);
const inputs = await p.evaluate(() =>
  Array.from(document.querySelectorAll('input')).map((i) => ({
    type: i.type,
    accept: i.accept,
    id: i.id,
    cls: String(i.className).slice(0, 60),
    parentText: (i.parentElement?.innerText || '').slice(0, 70),
    visible: i.offsetParent !== null,
  }))
);
console.log('INPUTS:', JSON.stringify(inputs, null, 1));
const btns = await p.evaluate(() =>
  Array.from(document.querySelectorAll('button,[role=button]'))
    .map((b) => (b.innerText || b.getAttribute('aria-label') || b.title || '').trim().slice(0, 40))
    .filter(Boolean)
);
console.log('BUTTONS:', JSON.stringify([...new Set(btns)].slice(0, 50), null, 1));
await b.close();
