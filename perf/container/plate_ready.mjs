import { createRequire } from 'node:module';
const require = createRequire(new URL('../../harness/ui/package.json', import.meta.url));
const { chromium } = require('playwright');
const [url, selector, readyJs] = process.argv.slice(2);
if (!selector && !readyJs) throw new Error('missing_readiness_gate');
const browser = await chromium.launch({headless: true});
try {
  const page = await browser.newPage();
  await page.goto(url);
  if (selector) await page.locator(selector).waitFor({timeout: 120000});
  if (readyJs) await page.waitForFunction(readyJs, null, {timeout: 120000});
  console.log(JSON.stringify({editor: 'plate', production: true, ready_selector: selector, ready_js: readyJs, reached: true}));
} finally { await browser.close(); }
