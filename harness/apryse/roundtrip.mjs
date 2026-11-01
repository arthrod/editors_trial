// Round trip through Apryse WebViewer's DOCX Editor: import -> export, in a
// real browser, through the product's own code path.
//
//   node roundtrip.mjs <in.docx> <out.docx> [--edit]
//
// Import: WebViewer opens the file with enableOfficeEditing (its office engine,
// in the browser). Export: Document.getFileData({ downloadType: 'office' }),
// the call WebViewer's own Download/Save uses for an office document.
//
// --edit types one character at the start of the body and deletes it again
// before exporting, so the export is produced from an edited document; a
// product may hand back the untouched source bytes when nothing was edited,
// and that would measure nothing. The driver reports whether the bytes out
// equal the bytes in, so a pass-through cannot hide.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { createServer } from 'vite';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(resolve(HERE, '../ui/package.json'));
const { chromium } = require('playwright');

const [input, output, ...flags] = process.argv.slice(2);
if (!input || !output) {
  console.error('usage: node roundtrip.mjs <in.docx> <out.docx> [--edit]');
  process.exit(2);
}
const EDIT = flags.includes('--edit');
const bytesIn = readFileSync(input);
const sha = (b) => createHash('sha256').update(b).digest('hex').slice(0, 16);

// The config is imported as a plain module (configFile: false), so Vite does
// not bundle it into node_modules/.vite-temp, which the sandbox cannot write.
const config = (await import('./vite.config.mjs')).default;
const server = await createServer({ ...config, configFile: false, root: HERE, logLevel: 'error' });
await server.listen();
const url = 'http://127.0.0.1:5210/';
// Inside build/run_bomb_sandbox.py the whole process tree already runs under a
// seatbelt profile, and Chromium's own sandbox cannot initialise inside one.
const browser = await chromium.launch({ chromiumSandbox: !process.env.APRYSE_NO_CHROME_SANDBOX });
let code = 1;
try {
  const page = await browser.newPage();
  const log = [];
  page.on('console', (m) => log.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => log.push(`[pageerror] ${e.message}`));
  // Every request that leaves the local host page is reported: a hostile
  // package must not make the editor reach the network, and neither should
  // the editor itself. The sandbox blocks DNS, so these show up as failures.
  page.on('request', (req) => {
    const u = new URL(req.url());
    if (!['127.0.0.1', 'localhost'].includes(u.hostname) && !u.protocol.startsWith('blob') && !u.protocol.startsWith('data')) {
      // The body is described, never printed: it may carry the license key.
      const body = req.postData() || '';
      let shape = `${body.length} chars`;
      try {
        const describe = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) =>
          [k, v && typeof v === 'object' ? describe(v) : `${typeof v}(${String(v).length})`]));
        shape += ` ${JSON.stringify(describe(JSON.parse(body)))}`;
      } catch { /* not JSON */ }
      const leaks = [/Chapter 1|Heading with/.test(body) && 'document text', body.includes('complex.docx') && 'file name']
        .filter(Boolean).join(', ') || 'no document text, no file name';
      console.log(`[outbound] ${req.method()} ${u.protocol}//${u.host}${u.pathname} body ${shape}; ${leaks}`);
    }
  });
  await page.route('**/sample.docx', (route) =>
    route.fulfill({
      status: 200,
      body: bytesIn,
      contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }));
  await page.goto(url);
  await page.waitForFunction(() => window.__apryse && window.__apryse.instance, null, { timeout: 120000 });
  const info = await page.evaluate(() => window.__apryse.loaded);
  console.log(`loaded: ${JSON.stringify(info)}`);
  if (EDIT) {
    // A user's edit: focus the body, type one character, delete it.
    await page.evaluate(async () => {
      const editor = window.__apryse.instance.Core.documentViewer.getDocument().getOfficeEditor();
      await editor.focusContent();
    });
    await page.keyboard.type('X');
    await page.waitForTimeout(500);
    await page.keyboard.press('Backspace');
    await page.waitForTimeout(1000);
    console.log('edited: typed and deleted one character');
  }
  const b64 = await page.evaluate(async () => {
    const doc = window.__apryse.instance.Core.documentViewer.getDocument();
    const data = await doc.getFileData({ downloadType: 'office' });
    const bytes = new Uint8Array(data);
    let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s);
  });
  const bytesOut = Buffer.from(b64, 'base64');
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
