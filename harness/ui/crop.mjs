/**
 * Crop helper for the rendering study: writes a zoomed crop of a PNG so the
 * captured regions can be inspected closely.  Uses the Playwright already
 * installed in harness/ui (run it from that directory).
 *
 *   node crop.mjs <src.png> <out.png> <x> <y> <w> <h> <scale> <srcW> <srcH>
 */
import fs from 'node:fs'
import { chromium } from 'playwright'

const [, , src, out, X, Y, W, H, S, SW, SH] = process.argv
const x = Number(X)
const y = Number(Y)
const w = Number(W)
const h = Number(H)
const scale = Number(S)
const srcW = Number(SW)
const srcH = Number(SH)

const b64 = fs.readFileSync(src).toString('base64')
const browser = await chromium.launch()
const page = await browser.newPage({
  viewport: { width: Math.round(w * scale), height: Math.round(h * scale) },
})
await page.setContent(
  `<body style="margin:0;overflow:hidden;background:#fff">
     <img src="data:image/png;base64,${b64}"
          style="position:absolute;left:${-x * scale}px;top:${-y * scale}px;
                 width:${srcW * scale}px;height:${srcH * scale}px;
                 image-rendering:pixelated">
   </body>`,
)
await page.waitForTimeout(300)
await page.screenshot({ path: out })
await browser.close()
console.log(`OK ${out}`)
