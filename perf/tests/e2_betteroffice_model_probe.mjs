/**
 * Read a BetterOffice-shaped fake host through every shared model reader.
 * Prints the readers' results as JSON.
 */
import { pathToFileURL, fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('../..', import.meta.url)).replace(/\/$/, '');
const { loadPlaywright } = await import(pathToFileURL(`${repo}/perf/runner/witness.mjs`).href);
const surface = await import(pathToFileURL(`${repo}/perf/runner/edit_surface.mjs`).href);
const { READ_SURFACE_STATE } = await import(pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href);
const { LIST_MODEL_PARAGRAPHS } = await import(pathToFileURL(`${repo}/perf/runner/lane_edit_burst.mjs`).href);

const url = process.argv[2];
const { chromium } = await loadPlaywright();
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const out = { usable: {} };
  for (const ready of ['1', '0']) {
    await page.goto(`${url}?ready=${ready}`, { waitUntil: 'load', timeout: 15000 });
    const expr = surface.usableExpression('betteroffice', '[data-docx-pages-host] canvas[data-page-index]');
    out.usable[ready] = await page.evaluate((code) => Boolean(eval(code)), expr); // eslint-disable-line no-eval
  }
  await page.goto(`${url}?ready=1`, { waitUntil: 'load', timeout: 15000 });
  out.document_text = await page.evaluate(surface.READ_EDITOR_DOCUMENT_TEXT, surface.documentTextSurface('betteroffice'));
  out.model_document = await page.evaluate(surface.READ_MODEL_DOCUMENT_TEXT, 'betteroffice');
  out.at_caret = await page.evaluate(surface.READ_MODEL_AT_CARET, 'betteroffice');
  out.state = await page.evaluate(READ_SURFACE_STATE, surface.editSurface('betteroffice'));
  out.paragraphs = await page.evaluate(async (src) => (0, eval)(src)('betteroffice'), LIST_MODEL_PARAGRAPHS.toString()); // eslint-disable-line no-eval
  out.canvas_usable = surface.usableExpression('canvas', '#editor canvas');
  out.docen_usable = surface.usableExpression('docen', 'docen-document');
  process.stdout.write(JSON.stringify(out));
} finally {
  await browser.close();
}
