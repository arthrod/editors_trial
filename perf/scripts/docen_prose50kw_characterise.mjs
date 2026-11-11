/**
 * Load prose-50kw in a production docen-host dist; capture tiptap console noise
 * and model paragraph count via window.__PERF_MODEL_TEXT__ / getJSON.
 *
 * Usage:
 *   DOCEN_DIST=/path/to/dist CORPUS=/path/prose-50kw.docx node perf/scripts/docen_prose50kw_characterise.mjs
 */
import fs from 'node:fs';
import { loadPlaywright } from '../runner/witness.mjs';

const url = process.env.URL || 'http://127.0.0.1:5314/';
if (!url) {
  console.error('URL required (StaticHost already serving production dist + corpus)');
  process.exit(2);
}

async function main() {
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  const consoleLines = [];
  page.on('console', (msg) => consoleLines.push(msg.text()));
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 180_000 });
  await page.waitForFunction(() => window.__DOCEN_READY__ === true, null, { timeout: 180_000 });
  const model = await page.evaluate(() => {
    const el = window.__DOCEN__;
    const text = typeof window.__PERF_MODEL_TEXT__ === 'function' ? window.__PERF_MODEL_TEXT__() : '';
    let topLevelBlocks = null;
    try {
      const json = el?.getJSON?.();
      topLevelBlocks = json?.content?.length ?? null;
    } catch {
      topLevelBlocks = null;
    }
    const paragraphBreaks = text.split(/\s{2,}|\n+/).filter((p) => p.trim()).length;
    return { text_len: text.length, paragraph_breaks: paragraphBreaks, top_level_blocks: topLevelBlocks, opening: text.slice(0, 120) };
  });
  const invalid = consoleLines.filter((line) => /Invalid content|Unknown node type/i.test(line));
  await browser.close();
  process.stdout.write(
    JSON.stringify(
      {
        invalid_content_lines: invalid,
        invalid_content_count: invalid.length,
        model,
        console_tail: consoleLines.slice(-20),
      },
      null,
      2,
    ),
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
