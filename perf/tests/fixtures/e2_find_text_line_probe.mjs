// E2: exercise prepareEditSurface/placeCaret against a fake host page and
// print JSON. Usage: node e2_find_text_line_probe.mjs <url> <editorId> [timeoutMs]
import { prepareEditSurface, placeCaret, editSurface } from '../../runner/edit_surface.mjs';
import { chromium } from '../../../harness/ui/node_modules/playwright/index.mjs';

const [url, editorId = 'superdoc', timeoutMs = '3000'] = process.argv.slice(2);
const browser = await chromium.launch({ headless: true });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
const prepare = await prepareEditSurface(page, editorId, { timeoutMs: Number(timeoutMs) });
let place = null;
try {
  const placed = await placeCaret(page, editorId, editSurface(editorId).root, { focusTimeoutMs: 1200 });
  place = { point: placed.point, focused: placed.focused, input_editable: placed.input_editable };
} catch (error) {
  place = { error: String(error && error.message ? error.message : error) };
}
console.log(JSON.stringify({ prepare, place }));
await browser.close();
