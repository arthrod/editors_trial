/**
 * DOM inspector for the GenOffice rendering study.
 *
 * Opens the running renderer, intercepts the document request the same way
 * shot.mjs does, and dumps concrete details (text, computed style, geometry)
 * for the constructs the brief asks about.
 *
 *   node inspect.mjs [--scroll <text>] [--shot <png>]
 */
import fs from 'node:fs'
import { chromium } from 'playwright'

const argv = process.argv.slice(2)
const opt = {}
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith('--')) {
    const k = argv[i].slice(2)
    const n = argv[i + 1]
    if (n === undefined || n.startsWith('--')) opt[k] = true
    else {
      opt[k] = n
      i++
    }
  }
}

const FIXTURE = '/Users/arthrod/temp/T/editors_trial/fixture/complex.docx'
const bytes = fs.readFileSync(FIXTURE)

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1500 } })
await context.route('**/*', async (route) => {
  const u = new URL(route.request().url())
  if (u.pathname === '/sample.docx') {
    await route.fulfill({
      status: 200,
      contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      body: bytes,
    })
  } else {
    await route.continue()
  }
})
const page = await context.newPage()
await page.goto('http://localhost:5201/', { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => (document.body.innerText || '').length > 200, undefined, {
  timeout: 60000,
})
await page.waitForTimeout(4000)

if (opt.scroll) {
  await page.evaluate((t) => {
    for (const n of document.querySelectorAll('*')) {
      if (n.children.length === 0 && (n.textContent || '').includes(t)) {
        n.scrollIntoView({ block: 'center' })
        return true
      }
    }
    return false
  }, opt.scroll)
  await page.waitForTimeout(1200)
}

const dump = await page.evaluate(() => {
  const info = (el) => {
    const cs = getComputedStyle(el)
    const r = el.getBoundingClientRect()
    return {
      text: (el.textContent || '').trim().slice(0, 90),
      cls: el.className && el.className.toString ? el.className.toString() : '',
      rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      color: cs.color,
      bg: cs.backgroundColor,
      strike: cs.textDecorationLine,
      underline: cs.textDecoration,
      stroke: cs.webkitTextStrokeWidth + ' ' + cs.webkitTextStrokeColor,
      display: cs.display,
      visibility: cs.visibility,
      textStrokeAttr: el.getAttribute('style') || '',
    }
  }
  const all = (sel) => Array.from(document.querySelectorAll(sel))
  const byText = (t) =>
    all('.doc-page *')
      .filter((e) => e.children.length === 0 && (e.textContent || '').includes(t))
      .map(info)

  return {
    ins: all('.doc-ins').map(info),
    del: all('.doc-del').map(info),
    rowRev: all('.row-rev-ins, .row-rev-del, tr.doc-del, tr.doc-ins').map(info),
    deletedRowText: byText('This row was deleted'),
    insertedRowText: byText('This row was inserted'),
    outline: all('[style*="text-stroke"], [data-doc-style*="textOutline"]').map(info),
    outlineText: byText('caps small'),
    capsText: byText('CAPS SMALL'),
    math: all('.doc-formula-math, .doc-formula, math').map(info),
    textbox: all('.doc-textbox').map(info),
    fallbackText: byText('AlternateContent fallback text'),
    textboxText: byText('Text box content'),
    smartartText: byText('SmartArt'),
    footnoteRef: all('.doc-note-ref').map(info),
    commentMark: all('.doc-comment').map(info),
    // every text run that mentions the deleted / inserted words
    delWords: all('.doc-page *')
      .filter((e) => e.children.length === 0 && /^(inserted text|deleted text)$/.test((e.textContent || '').trim()))
      .map(info),
    vertMerged: byText('vert merged'),
    verticalText: byText('vertical text'),
  }
})

console.log(JSON.stringify(dump, null, 1))
if (opt.shot) {
  await page.screenshot({ path: opt.shot })
  console.log('shot ->', opt.shot)
}
await browser.close()
