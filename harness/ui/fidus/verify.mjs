/**
 * Read-only verification pass against an already-imported Fidus document.
 *   node verify.mjs <docPath>          e.g. node verify.mjs /document/4
 */
import { chromium } from 'playwright';

const BASE = process.env.FIDUS_BASE || 'http://localhost:5209';
const DOC = process.argv[2] || '/document/4';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1500 } });
page.on('pageerror', (e) => console.log('PAGEERROR', String(e).split('\n')[0]));

await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
await page.locator('#id-login').waitFor({ state: 'visible', timeout: 20000 });
await page.fill('#id-login', 'corpus');
await page.fill('#id-password', 'corpus-pass-2026');
await Promise.all([
  page.waitForNavigation({ timeout: 30000 }).catch(() => {}),
  page.click('button[type=submit], input[type=submit], .fw-button:has-text("LOG IN")'),
]);
await page.waitForTimeout(2000);

await page.goto(BASE + DOC, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(9000);
await page.evaluate(() => {
  const w = document.getElementById('wait');
  if (w) { w.classList.remove('active'); w.classList.remove('full'); }
});
await page.waitForTimeout(1500);

const out = await page.evaluate(() => {
  const vis = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
  };
  const findText = (t) => {
    const hits = [];
    for (const n of document.querySelectorAll('body *')) {
      const own = Array.from(n.childNodes).filter((c) => c.nodeType === 3).map((c) => c.textContent).join('');
      if (own.includes(t)) hits.push({ tag: n.tagName, cls: String(n.className).slice(0, 50), visible: vis(n), txt: own.slice(0, 80) });
    }
    return hits;
  };
  const marginBoxes = Array.from(document.querySelectorAll('.margin-box, .marginbox, [class*=margin-box]')).map((e) => ({
    cls: String(e.className).slice(0, 70),
    visible: vis(e),
    text: (e.innerText || '').trim().slice(0, 120),
  }));
  const comments = Array.from(document.querySelectorAll('[class*=comment]')).map((e) => ({
    cls: String(e.className).slice(0, 60),
    visible: vis(e),
    text: (e.innerText || '').trim().slice(0, 100),
  }));
  const tracks = Array.from(document.querySelectorAll('[class*=track]')).map((e) => ({
    cls: String(e.className).slice(0, 60),
    visible: vis(e),
    text: (e.innerText || '').trim().slice(0, 100),
  }));
  const figs = Array.from(document.querySelectorAll('figure')).map((f) => {
    const img = f.querySelector('img');
    const r = f.getBoundingClientRect();
    return {
      visible: vis(f), w: Math.round(r.width), h: Math.round(r.height),
      imgSrc: img ? img.getAttribute('src') : null,
      imgNatural: img ? img.naturalWidth + 'x' + img.naturalHeight : null,
      imgRendered: img ? Math.round(img.getBoundingClientRect().width) + 'x' + Math.round(img.getBoundingClientRect().height) : null,
      imgVisible: img ? vis(img) : null,
    };
  });
  const inlineImgs = Array.from(document.querySelectorAll('img')).filter((i) => !String(i.className).includes('separator')).map((i) => ({
    src: i.getAttribute('src'), natural: i.naturalWidth + 'x' + i.naturalHeight,
    rendered: Math.round(i.getBoundingClientRect().width) + 'x' + Math.round(i.getBoundingClientRect().height),
    visible: vis(i),
  }));
  return {
    bodyHasCommentBody: (document.body.innerText || '').includes('This is a comment body.'),
    bodyHasInsertedText: (document.body.innerText || '').includes('inserted text'),
    bodyHasDeletedRow: (document.body.innerText || '').includes('This row was deleted'),
    bodyHasTableCells: (document.body.innerText || '').includes('Header A'),
    bodyHasTextBox: (document.body.innerText || '').includes('Text box content'),
    bodyHasFallback: (document.body.innerText || '').includes('AlternateContent fallback text'),
    bodyHasCatA: (document.body.innerText || '').includes('Cat A'),
    bodyHasSeries1: (document.body.innerText || '').includes('Series 1'),
    textBoxHits: findText('Text box content'),
    insertedHits: findText('inserted text'),
    commentBodyHits: findText('This is a comment body.'),
    marginBoxes, comments, tracks, figs, inlineImgs,
    tableCount: document.querySelectorAll('table').length,
    svgCount: document.querySelectorAll('svg').length,
    canvasCount: document.querySelectorAll('canvas').length,
    mathCount: document.querySelectorAll('math, .katex').length,
  };
});
console.log(JSON.stringify(out, null, 1));
await browser.close();
