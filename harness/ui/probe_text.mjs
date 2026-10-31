import { chromium } from 'playwright';

const url = process.argv[2];
const b = await chromium.launch({ headless: true });
const ctx = await b.newContext({ viewport: { width: 1440, height: 1500 } });
const p = await ctx.newPage();
await p.goto(url, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(14000);
const info = await p.evaluate(() => {
  const txt = (document.body.innerText || '');
  return {
    bodyLen: txt.length,
    sample: txt.slice(0, 4000),
    hasTextBox: txt.includes('Text box content'),
    hasFallback: txt.includes('AlternateContent fallback text'),
    hasEquation: /mc\s*\^?\s*2|E = mc/.test(txt),
    hasStepOne: txt.includes('Step one'),
    hasCatA: txt.includes('Cat A'),
    hasOle: txt.includes('Text box'),
  };
});
console.log(JSON.stringify(info, null, 1));
await b.close();
