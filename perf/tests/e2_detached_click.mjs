/**
 * E2: a click whose target the editor replaces during pointerdown (react-docx
 * activates a paragraph by re-rendering it). Invoked from
 * test_e2_detached_click.py; prints one JSON line per case.
 *
 * The input lane judges such a detached target by its ancestors at the event,
 * but only on react-docx's page (window.__host.viewer.getController). An
 * outside review (2026-11-22) found the rule ran for every editor; every other
 * page must keep the old verdict (a detached target is not inside).
 */
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('../..', import.meta.url)).replace(/\/$/, '');
const require = createRequire(`${repo}/harness/ui/package.json`);
const { chromium } = require('playwright');
const { INSTALL_INPUT_TAP, pointerTargetInside, armInsideSelector } = await import(
  pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href
);

const PAGE = (reactDocx) => `<!doctype html><body style="margin:0">
<div id="ed" contenteditable="true" style="width:400px;height:200px;font:20px sans-serif">
  <p id="line"><span id="hit">click here</span></p>
</div>
<script>
  ${reactDocx ? 'window.__host = { viewer: { getController() { return {}; } } };' : ''}
  // Replace the clicked line during pointerdown, after the tap's capture
  // listener ran (bubble phase on the editor).
  document.getElementById('ed').addEventListener('pointerdown', () => {
    const old = document.getElementById('line');
    const fresh = document.createElement('p');
    fresh.id = 'line';
    fresh.innerHTML = '<span id="hit">click here</span>';
    old.replaceWith(fresh);
  });
</script></body>`;

const browser = await chromium.launch({ headless: true });
try {
  for (const reactDocx of [false, true]) {
    const page = await browser.newPage({ viewport: { width: 600, height: 400 } });
    await page.setContent(PAGE(reactDocx));
    await page.evaluate(INSTALL_INPUT_TAP);
    await page.mouse.click(20, 20);
    const verdict = await pointerTargetInside(page, '#ed');
    const recordedPath = await page.evaluate(() => Array.isArray(window.__perfCriteria.targetPath));
    console.log(JSON.stringify({ reactDocx, verdict, recordedPath }));
    await page.close();
  }
  // The selector matches the replaced element itself (CodeAnt on #283): the
  // path holds the detached copy, the matched parts the new one. A click on the
  // line is inside; a click in the editor below the line is not.
  for (const [where, y] of [['on_line', 20], ['below_line', 150]]) {
    const page = await browser.newPage({ viewport: { width: 600, height: 400 } });
    await page.setContent(PAGE(true));
    await page.evaluate(INSTALL_INPUT_TAP);
    if (armInsideSelector) await armInsideSelector(page, { editable: { selector: '#line' } });
    await page.mouse.click(20, y);
    const verdict = await pointerTargetInside(page, '#line');
    console.log(JSON.stringify({ reactDocx: `replaced_${where}`, verdict }));
    await page.close();
  }
} finally {
  await browser.close();
}
