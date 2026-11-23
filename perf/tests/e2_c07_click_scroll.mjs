/**
 * E2 C07: a click on a line the window's bottom edge cuts makes the editor
 * scroll that line into view (BetterOffice, 18 px). The caret then sits on the
 * clicked line, but in viewport coordinates it no longer matches the line box
 * read before the click. Owner's decision (2026-11-22): judge the caret
 * against where the clicked line ends up after the click's own scroll.
 * Invoked from test_e2_c07_click_scroll.py; prints one JSON line per case.
 */
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('../..', import.meta.url)).replace(/\/$/, '');
const require = createRequire(`${repo}/harness/ui/package.json`);
const { chromium } = require('playwright');
const { RECORD_CLICK_SCROLL, caretOnClickedLine } = await import(
  pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href
);

// A 300 px scroller; the line at y 290..310 is cut by its bottom edge. A
// pointerdown on it scrolls the scroller by `scrollBy` px, as BetterOffice does.
const PAGE = (scrollBy) => `<!doctype html><body style="margin:0">
<div id="sc" style="height:300px;overflow:auto"><div style="height:2000px;position:relative">
  <div id="ln" style="position:absolute;top:290px;height:20px;width:200px;background:#000"></div>
</div></div>
<script>
  document.getElementById('ln').addEventListener('pointerdown', () => {
    document.getElementById('sc').scrollTop += ${scrollBy};
  });
</script></body>`;
// The document itself scrolls (no inner scroller): the window's scroll must be counted once.
const WINDOW_PAGE = (scrollBy) => `<!doctype html><body style="margin:0"><div style="height:3000px;position:relative">
  <div id="ln" style="position:absolute;top:290px;height:20px;width:200px;background:#000"></div></div>
<script>
  document.getElementById('ln').addEventListener('pointerdown', () => { window.scrollBy(0, ${scrollBy}); });
</script></body>`;

const LINE = { top: 288, bottom: 312 };
const browser = await chromium.launch({ headless: true });
try {
  for (const [mode, scrollBy] of [['scroller', 0], ['scroller', 18], ['window', 18]]) {
    const page = await browser.newPage({ viewport: { width: 600, height: mode === 'window' ? 300 : 400 } });
    await page.setContent(mode === 'window' ? WINDOW_PAGE(scrollBy) : PAGE(scrollBy));
    const recorder = await page.evaluateHandle(RECORD_CLICK_SCROLL, { x: 50, y: 295 });
    await page.mouse.click(50, 295);
    const scrolled = await recorder.evaluate((r) => r.delta());
    // The caret the editor shows on the clicked line, after the scroll.
    const lineNow = await page.evaluate(() => {
      const r = document.getElementById('ln').getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, height: r.height };
    });
    console.log(JSON.stringify({
      mode,
      scrollBy,
      scrolled,
      onLine: caretOnClickedLine(lineNow, LINE, scrolled),
      // A caret on another line (40 px below) is still refused.
      offLine: caretOnClickedLine({ top: lineNow.top + 40, bottom: lineNow.bottom + 40, height: 20 }, LINE, scrolled),
      // A caret left at the line's old place (inside the box read before the click, outside the moved line).
      staleCaret: caretOnClickedLine({ top: 300, bottom: 310, height: 10 }, LINE, scrolled),
    }));
    await page.close();
  }
} finally {
  await browser.close();
}
