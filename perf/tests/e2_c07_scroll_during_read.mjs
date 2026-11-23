/**
 * E2 C07: a scroll away and back while the caret is read must make the read
 * unstable (CodeRabbit on #287). Comparing only the click's scroll delta on
 * both sides of the read missed it: both ends equal, but the caret came from
 * another viewport. Invoked from test_e2_c07_scroll_during_read.py; prints JSON.
 */
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('../..', import.meta.url)).replace(/\/$/, '');
const require = createRequire(`${repo}/harness/ui/package.json`);
const { chromium } = require('playwright');
const { RECORD_CLICK_SCROLL, readStateWithClickScroll } = await import(
  pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href
);

const PAGE = `<!doctype html><body style="margin:0">
<div id="sc" style="height:300px;overflow:auto"><div style="height:2000px;position:relative">
  <div id="ln" style="position:absolute;top:290px;height:20px;width:200px;background:#000"></div>
</div></div></body>`;

const browser = await chromium.launch({ headless: true });
const out = {};
try {
  for (const mode of ['still', 'away_and_back', 'away']) {
    const page = await browser.newPage();
    await page.setContent(PAGE);
    await page.evaluate(RECORD_CLICK_SCROLL, { x: 100, y: 295 });
    const readState = async () => {
      if (mode === 'still') return page.evaluate(() => 'caret');
      return page.evaluate(async (back) => {
        const sc = document.getElementById('sc');
        sc.scrollTop += 50;
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        if (back) sc.scrollTop -= 50;
        return 'caret';
      }, mode === 'away_and_back');
    };
    const r = await readStateWithClickScroll(page, readState);
    out[mode] = { stable: r.stable, scrolled: r.scrolled };
    await page.close();
  }
} finally {
  await browser.close();
}
process.stdout.write(JSON.stringify(out));
