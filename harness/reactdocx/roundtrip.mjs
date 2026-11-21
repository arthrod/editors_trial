// Round trip through react-docx (@extend-ai/react-docx): import -> export, in
// a real browser, through the editor's own code path.
//
//   node roundtrip.mjs <in.docx> <out.docx>
//
// Import: createDocxViewer(element, { file, mode: 'edit' }), the package's
// framework-free entry (its Rust/WASM parser, in its import worker).
// Export: controller.getDocxBytes(), which the package documents as "the same
// bytes" its own Export button downloads.
//
// Why a browser: the editor's export first rasterises any picture it cannot
// write back from the source (prepareImagePaintBoundsForExport, on a canvas),
// and only then serialises. That step is not exported from the package, and
// the three calls the package documents for Node (parseDocx -> buildDocModel
// -> serializeDocx) stop on the trial's corpus where the editor does not; see
// headless.mjs, which runs exactly those three calls and prints what happens.
//
// The driver reports whether the bytes out equal the bytes in, so a
// pass-through cannot hide.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { createServer } from 'vite';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(resolve(HERE, '../ui/package.json'));
const { chromium } = require('playwright');

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error('usage: node roundtrip.mjs <in.docx> <out.docx>');
  process.exit(2);
}
const bytesIn = readFileSync(input);
const sha = (b) => createHash('sha256').update(b).digest('hex').slice(0, 16);

// The config is imported as a plain module (configFile: false), so Vite does
// not bundle it into node_modules/.vite-temp, which the sandbox cannot write.
const config = (await import('./vite.config.mjs')).default;
const server = await createServer({ ...config, configFile: false, root: HERE, logLevel: 'error' });
await server.listen();
const url = 'http://127.0.0.1:5231/';
// Inside build/run_bomb_sandbox.py the whole process tree already runs under a
// seatbelt profile, and Chromium's own sandbox cannot initialise inside one.
const browser = await chromium.launch({ chromiumSandbox: !process.env.REACTDOCX_NO_CHROME_SANDBOX });
let code = 1;
try {
  const page = await browser.newPage();
  const log = [];
  page.on('console', (m) => log.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => log.push(`[pageerror] ${e.message}`));
  // Every request that leaves the local host page is reported.
  page.on('request', (req) => {
    const u = new URL(req.url());
    if (!['127.0.0.1', 'localhost'].includes(u.hostname) && !u.protocol.startsWith('blob') && !u.protocol.startsWith('data')) {
      console.log(`[outbound] ${req.method()} ${u.protocol}//${u.host}${u.pathname}`);
    }
  });
  await page.route('**/sample.docx', (route) =>
    route.fulfill({
      status: 200,
      body: bytesIn,
      contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }));
  await page.goto(url);
  await page.waitForFunction(() => window.__reactdocx, null, { timeout: 120000 });
  let info;
  try {
    info = await page.evaluate(() => window.__reactdocx.loaded);
  } catch (e) {
    console.log(`import FAILED in the editor: ${e.message}`);
    for (const line of log.slice(-20)) console.log(line);
    throw e;
  }
  console.log(`loaded: ${JSON.stringify(info)}`);
  console.log(`PERF model_ready_ms=${info.model_ready_ms.toFixed(6)}`);
  const saved = await page.evaluate(async () => {
    const controller = window.__reactdocx.viewer.getController();
    const t0 = performance.now();
    let data;
    try {
      data = await controller.getDocxBytes();
    } catch (e) {
      return { error: e instanceof Error ? e.message : String(e) };
    }
    const save_ms = performance.now() - t0;
    const bytes = new Uint8Array(data);
    let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return { b64: btoa(s), save_ms };
  });
  if (saved.error) {
    console.log(`export FAILED in the editor (controller.getDocxBytes): ${saved.error}`);
    for (const line of log.filter((l) => /error|warn/i.test(l)).slice(0, 20)) console.log(line);
    throw new Error(saved.error);
  }
  console.log(`PERF save_ms=${saved.save_ms.toFixed(6)}`);
  const bytesOut = Buffer.from(saved.b64, 'base64');
  mkdirSync(dirname(resolve(output)), { recursive: true });
  writeFileSync(output, bytesOut);
  const same = Buffer.compare(bytesIn, bytesOut) === 0;
  console.log(`in  ${bytesIn.length} bytes sha ${sha(bytesIn)}`);
  console.log(`out ${bytesOut.length} bytes sha ${sha(bytesOut)}${same ? '  IDENTICAL TO INPUT (pass-through)' : ''}`);
  for (const line of log.filter((l) => /error|warn/i.test(l)).slice(0, 20)) console.log(line);
  code = 0;
} finally {
  await browser.close();
  await server.close();
}
process.exit(code);
