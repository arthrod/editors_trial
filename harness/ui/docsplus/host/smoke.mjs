/**
 * Single smoke open of the docs.plus perf host.
 *
 * Mirrors what perf/runner/warm_cold_browser.mjs does — navigate, wait for the
 * ready signal, click the edit surface, type one character — and records the
 * console, page errors, failed requests, a screenshot and a JSON summary.
 *
 *   node smoke.mjs [--url http://127.0.0.1:5215/editor] [--out /tmp/perf-run-logs]
 *
 * Playwright is loaded from harness/ui/node_modules (the same copy the perf
 * probe uses), so this resolves from any cwd.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const uiRoot = path.resolve(here, '../..')

const argv = process.argv.slice(2)
const opt = {}
for (let i = 0; i < argv.length; i += 1) {
  if (!argv[i].startsWith('--')) continue
  opt[argv[i].slice(2)] = argv[i + 1]
}

const url = opt.url || 'http://127.0.0.1:5215/editor'
const outDir = opt.out || '/tmp/perf-run-logs'
const readyJs = opt['ready-js'] || 'window.__DOCSPLUS_READY__ === true'
const readySelector = opt['ready-selector'] || '#perf-status[data-state="ready"]'
const editSelector = opt['edit-selector'] || '.tiptap__editor .ProseMirror'
const checkReload = opt.reload === 'true' || opt.reload === true
const corpusFile = opt.corpus || path.resolve(here, '../../../../fixture/complex.docx')
const corpusRoute = opt['corpus-route'] || '/corpus.docx'

fs.mkdirSync(outDir, { recursive: true })

const { chromium } = await import(
  pathToFileURL(path.join(uiRoot, 'node_modules/playwright/index.mjs')).href
)

const log = []
const pageErrors = []
const failedRequests = []
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
const page = await context.newPage()

// The perf probe fulfils the corpus route itself; assert that this host's page
// really loads the document from that intercepted response and not from disk.
let intercepted = 0
if (opt.intercept !== 'false') {
  const bytes = fs.readFileSync(corpusFile)
  await context.route('**/*', async (route) => {
    const requestUrl = new URL(route.request().url())
    if (requestUrl.pathname === corpusRoute) {
      intercepted += 1
      await route.fulfill({
        status: 200,
        contentType:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: bytes,
      })
      return
    }
    await route.continue()
  })
}

page.on('console', (m) => log.push(`[${m.type()}] ${m.text()}`))
page.on('pageerror', (e) => pageErrors.push(String(e)))
page.on('requestfailed', (r) =>
  failedRequests.push(`${r.url()} ${r.failure() ? r.failure().errorText : '?'}`)
)

const result = { url, ready_js: readyJs, edit_selector: editSelector, ok: false }
const started = Date.now()

try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  result.navigation_ms = Date.now() - started

  await page.waitForFunction(
    (expr) => {
      try {
        return Boolean(eval(expr)) // eslint-disable-line no-eval
      } catch {
        return false
      }
    },
    readyJs,
    { timeout: 120_000 }
  )
  result.ready_ms = Date.now() - started

  const info = await page.evaluate(() => window.__DOCSPLUS_INFO__ || null)
  result.info = info

  const badge = await page.locator('#perf-status').evaluate((el) => ({
    state: el.getAttribute('data-state'),
    text: el.textContent,
    visible: Boolean(el.getBoundingClientRect().width && el.getBoundingClientRect().height),
  }))
  result.badge = badge

  const before = await page.evaluate(() => window._editor.getText().length)
  result.intercepted_corpus_requests = intercepted
  result.ready_selector_visible = await page
    .locator(readySelector)
    .isVisible()
    .catch(() => false)
  const target = page.locator(editSelector).first()
  await target.click({ timeout: 30_000 })
  await page.keyboard.type('x', { delay: 12 })
  const paint = await page.evaluate(async () => {
    const t = performance.now()
    await new Promise((r) => requestAnimationFrame(() => r(null)))
    await new Promise((r) => requestAnimationFrame(() => r(null)))
    return performance.now() - t
  })
  const after = await page.evaluate(() => window._editor.getText().length)
  result.edit = { text_before: before, text_after: after, inserted: after - before, paint_ms: paint }

  await page.waitForTimeout(500)
  result.still_rendered = await page.evaluate(() => {
    const root = document.querySelector('.tiptap__editor')
    return {
      editor_visible: Boolean(root && root.getBoundingClientRect().height > 200),
      paragraphs: root ? root.querySelectorAll('p').length : 0,
      images: root ? root.querySelectorAll('img').length : 0,
      tables: root ? root.querySelectorAll('table').length : 0,
      text_length: window._editor.getText().length,
    }
  })

  result.screenshot = path.join(outDir, 'docsplus-smoke.png')
  await page.screenshot({ path: result.screenshot })
  result.ok = result.edit.inserted === 1 && result.still_rendered.paragraphs > 0

  // The perf probe reloads in the same context and waits for the same signal.
  if (checkReload && result.ok) {
    const reloadStart = Date.now()
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 120_000 })
    await page.waitForFunction(
      (expr) => {
        try {
          return Boolean(eval(expr)) // eslint-disable-line no-eval
        } catch {
          return false
        }
      },
      readyJs,
      { timeout: 120_000 }
    )
    result.reload = {
      ready_ms: Date.now() - reloadStart,
      info: await page.evaluate(() => window.__DOCSPLUS_INFO__ || null),
      rendered: await page.evaluate(() => {
        const root = document.querySelector('.tiptap__editor')
        return {
          paragraphs: root ? root.querySelectorAll('p').length : 0,
          images: root ? root.querySelectorAll('img').length : 0,
          badges: document.querySelectorAll('#perf-status').length,
        }
      }),
    }
    result.reload.screenshot = path.join(outDir, 'docsplus-smoke-reload.png')
    await page.screenshot({ path: result.reload.screenshot })
  }
} catch (error) {
  result.error = error instanceof Error ? error.message : String(error)
  result.screenshot = path.join(outDir, 'docsplus-smoke-failure.png')
  await page.screenshot({ path: result.screenshot }).catch(() => {})
} finally {
  fs.writeFileSync(
    path.join(outDir, 'docsplus-smoke-console.log'),
    [
      `# url ${url}`,
      `# started ${new Date().toISOString()}`,
      '## console',
      ...log,
      '## pageerrors',
      ...pageErrors,
      '## failed requests',
      ...failedRequests,
    ].join('\n') + '\n'
  )
}

fs.writeFileSync(path.join(outDir, 'docsplus-smoke.json'), JSON.stringify(result, null, 2))
console.log(JSON.stringify(result, null, 2))
console.log(`console log: ${path.join(outDir, 'docsplus-smoke-console.log')}`)

await browser.close()
process.exit(result.ok ? 0 : 1)
