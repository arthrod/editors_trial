import { chromium } from 'playwright';

const url = process.argv[2];
const b = await chromium.launch({ headless: true });
const ctx = await b.newContext({ viewport: { width: 1440, height: 1000 } });
const p = await ctx.newPage();
await p.goto(url, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(6000);
console.log('URL:', p.url());
console.log('TITLE:', await p.title());
const text = await p.evaluate(() => (document.body.innerText || '').slice(0, 3000));
console.log('TEXT:\n' + text);
const links = await p.evaluate(() =>
  Array.from(document.querySelectorAll('a,button'))
    .map((a) => `${a.tagName}[${(a.getAttribute('href') || '').slice(0, 60)}] ${(a.innerText || '').trim().slice(0, 50)}`)
    .filter((x) => x.split('] ')[1])
);
console.log('LINKS:\n' + links.join('\n'));
await b.close();
