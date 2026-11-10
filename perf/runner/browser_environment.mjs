// Untimed rendering provenance and B1 readiness smoke. Uses the installed harness driver.
import { createRequire } from 'node:module';
const require = createRequire(new URL('../../harness/ui/package.json', import.meta.url));
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true, args: ['--font-render-hinting=none', '--disable-lcd-text'] });
try {
  const page = await browser.newPage();
  if (process.argv[2]) {
    await page.goto(process.argv[2]);
    await page.locator('#ready').waitFor({ timeout: 500 });
  }
  const renderer = await page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl');
    if (!gl) return { renderer: null, renderer_reason: 'WebGL unavailable' };
    const extension = gl.getExtension('WEBGL_debug_renderer_info');
    return { renderer: extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
             vendor: extension ? gl.getParameter(extension.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR) };
  });
  console.log(JSON.stringify({ headless: true, browser_version: browser.version(), ...renderer }));
} finally {
  await browser.close();
}
