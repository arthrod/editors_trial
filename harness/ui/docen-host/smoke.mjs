/**
 * Smoke test for the docen warm/cold browser host.
 *
 *   node smoke.mjs            (from this directory)
 *
 * Starts `vite` on 127.0.0.1:5214, loads the host page with
 * /corpus.docx routed the way perf/runner/warm_cold_browser.mjs routes it,
 * waits for the ready signal, performs the probe's exact edit (click
 * `docen-document .canvas-pages > div:first-child`, type "x"), and checks that
 * the document grew and page 1's canvas repainted. Then reloads once to check
 * the warm path repeats.
 *
 * Corpus: /tmp/perf-run-logs/micro-paragraphs.docx — the warm/cold suite's own
 * fixture (perf/fixtures/generate.py: micro-paragraphs + correctness unicode).
 * Regenerate with:
 *   PYTHONPATH=. python3.13 -c "from perf.fixtures.generate import ..."
 * (see harness/ui/docen-host/README.md).
 *
 * Artifacts: /tmp/perf-run-logs/docen-smoke-{console.log,ready.png,after-typing.png,report.json}
 */
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const UI = path.resolve(HERE, '..')
const OUT = '/tmp/perf-run-logs'
const PORT = 5214
const HOST_URL = `http://127.0.0.1:${PORT}/`
const CORPUS = process.env.DOCEN_CORPUS || path.join(OUT, 'micro-paragraphs.docx')
const CORPUS_ROUTE = '/corpus.docx'
const READY_JS = 'window.__DOCEN_READY__ === true'
const EDIT_SELECTOR = 'docen-document .canvas-pages > div:first-child'
const EDITS = 4

fs.mkdirSync(OUT, { recursive: true })
if (!fs.existsSync(CORPUS)) {
  console.error(`missing corpus ${CORPUS}`)
  process.exit(2)
}
const corpusBytes = fs.readFileSync(CORPUS)
const consoleLines = []
const log = (...args) => {
  const line = args.map(String).join(' ')
  consoleLines.push(line)
  console.log(line)
}

async function portIsFree() {
  try {
    await fetch(HOST_URL, { signal: AbortSignal.timeout(1000) })
    return false
  } catch {
    return true
  }
}

function startServer() {
  const vite = path.join(HERE, 'node_modules/vite/bin/vite.js')
  const proc = spawn(process.execPath, [vite, '--port', String(PORT), '--strictPort', '--host', '127.0.0.1'], {
    cwd: HERE,
    stdio: ['ignore', 'pipe', 'pipe']
  })
  proc.stdout.on('data', (b) => fs.appendFileSync(path.join(OUT, 'docen-host-server.log'), b))
  proc.stderr.on('data', (b) => fs.appendFileSync(path.join(OUT, 'docen-host-server.log'), b))
  return proc
}

async function waitForServer(timeoutMs = 60_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const res = await fetch(HOST_URL, { signal: AbortSignal.timeout(1000) })
      if (res.status < 500) return Date.now() - started
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 250))
  }
  throw new Error('dev server did not answer on ' + HOST_URL)
}

async function stopServer(proc) {
  if (!proc || proc.exitCode !== null) return
  proc.kill('SIGTERM')
  await new Promise((resolve) => {
    const timer = setTimeout(() => {
      proc.kill('SIGKILL')
      resolve()
    }, 10_000)
    proc.once('exit', () => {
      clearTimeout(timer)
      resolve()
    })
  })
}

const failures = []
const check = (ok, message) => {
  log(`${ok ? 'PASS' : 'FAIL'} ${message}`)
  if (!ok) failures.push(message)
}

if (!(await portIsFree())) {
  console.error(`port ${PORT} is already in use — refusing to kill someone else's process`)
  process.exit(2)
}

const server = startServer()
let browser
// A crash inside a Playwright route handler would otherwise leave the dev
// server behind (it is a plain child of this process, not a process group).
const cleanupOnExit = () => {
  if (server.exitCode === null) server.kill('SIGKILL')
}
process.on('uncaughtException', (error) => {
  console.error('[smoke] uncaught', error)
  cleanupOnExit()
  process.exit(1)
})
process.on('exit', cleanupOnExit)
try {
  const bootMs = await waitForServer()
  log(`[smoke] dev server answered after ${bootMs} ms`)
  fs.writeFileSync(path.join(OUT, 'docen-host-server.log'), '')

  const { chromium } = await import(pathToFileURL(path.join(UI, 'node_modules/playwright/index.mjs')).href)
  browser = await chromium.launch({ headless: true, args: ['--font-render-hinting=none', '--disable-lcd-text'] })
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url())
    if (u.pathname === CORPUS_ROUTE) {
      return route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: corpusBytes
      })
    }
    return route.continue()
  })
  const page = await context.newPage()
  page.on('console', (m) => log(`[console:${m.type()}] ${m.text().slice(0, 500)}`))
  page.on('pageerror', (e) => log(`[pageerror] ${String(e).slice(0, 800)}`))
  page.on('requestfailed', (r) => log(`[requestfailed] ${r.url().slice(0, 160)} ${r.failure()?.errorText ?? ''}`))
  page.on('response', (r) => {
    if (r.status() >= 400) log(`[http ${r.status()}] ${r.url().slice(0, 160)}`)
  })

  const state = () =>
    page.evaluate(() => {
      const el = document.querySelector('docen-document')
      const editor = el?.getEditor?.()
      const sel = editor?.state?.selection ?? null
      let text = ''
      const walk = (n) => {
        if (!n) return
        if (n.type === 'text' && n.text) text += n.text
        if (Array.isArray(n.content)) n.content.forEach(walk)
      }
      walk(el.getJSON())
      const canvas = el.shadowRoot?.querySelector('.canvas-pages > div canvas') ?? null
      let bitmap = null
      try {
        bitmap = canvas ? canvas.toDataURL().slice(-48) : null
      } catch {
        bitmap = 'TAINTED'
      }
      return {
        ready: window.__DOCEN_READY__ === true,
        editable: editor?.isEditable ?? null,
        selection: sel ? { type: sel.constructor.name, from: sel.from, to: sel.to } : null,
        textLength: text.length,
        text: text.slice(0, 120),
        canvas: canvas ? { width: canvas.width, height: canvas.height } : null,
        bitmap,
        pageFrames: el.shadowRoot?.querySelectorAll('.canvas-pages > div').length ?? 0,
        bridgeFocused: el.shadowRoot?.activeElement?.dataset?.docenBridgeInput === 'true'
      }
    })

  async function editOnce(label) {
    const before = await state()
    // Exactly what warm_cold_browser.mjs does: click the edit selector, then
    // type one character through the keyboard.
    await page.locator(EDIT_SELECTOR).first().click({ timeout: 30_000 })
    await page.keyboard.type('x', { delay: 12 })
    await page.waitForTimeout(80)
    let after = await state()
    const started = Date.now()
    while (Date.now() - started < 5_000 && after.textLength === before.textLength) {
      await page.waitForTimeout(50)
      after = await state()
    }
    log(`[smoke] ${label}: selection ${JSON.stringify(before.selection)} -> ${JSON.stringify(after.selection)}, text ${before.textLength} -> ${after.textLength}, bitmap ${before.bitmap} -> ${after.bitmap}`)
    check(after.textLength === before.textLength + 1, `${label}: typing inserted exactly one character`)
    check(after.bitmap !== before.bitmap, `${label}: page 1 canvas repainted`)
    check(after.bridgeFocused, `${label}: the edit click focused the bridge textarea`)
    return after
  }

  const navT0 = Date.now()
  await page.goto(HOST_URL, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await page.waitForFunction(READY_JS, null, { timeout: 120_000 })
  await page.waitForSelector('#host[data-ready="1"]', { state: 'visible', timeout: 30_000 })
  check(true, 'ready selector #host[data-ready="1"] is visible')
  const readyMs = Date.now() - navT0
  log(`[smoke] ready after ${readyMs} ms`)

  const opened = await state()
  log(`[smoke] opened: ${JSON.stringify(opened)}`)
  check(opened.ready, 'ready signal fired')
  check(opened.editable === true, 'editor reports isEditable === true for the warm/cold corpus')
  check(opened.canvas !== null && opened.canvas.width > 0, 'page 1 canvas has a non-zero bitmap')
  check(opened.pageFrames > 0, 'page frames were laid out')
  await page.screenshot({ path: path.join(OUT, 'docen-smoke-ready.png') })

  let last = opened
  for (let i = 1; i <= EDITS; i++) last = await editOnce(`cold edit ${i}`)
  await page.screenshot({ path: path.join(OUT, 'docen-smoke-after-typing.png') })
  check(last.canvas !== null && last.canvas.width > 0, 'page 1 still renders after typing')

  // C10 path: adversarial_c10_scroll.mjs scrolls the largest light-DOM
  // overflow:auto|scroll box; the host mirrors that into the shadow scroller.
  const scroll = await page.evaluate(() => {
    const proxy = document.querySelector('#scroll-proxy')
    const el = document.querySelector('docen-document')
    const area = el.shadowRoot.querySelector('docen-document-area')
    const before = area.scrollTop
    proxy.scrollTop = Math.round((proxy.scrollHeight - proxy.clientHeight) * 0.5)
    proxy.dispatchEvent(new Event('scroll', { bubbles: true }))
    return {
      before,
      areaAfter: area.scrollTop,
      proxyTop: proxy.scrollTop,
      proxyScrollHeight: proxy.scrollHeight,
      proxyClientHeight: proxy.clientHeight
    }
  })
  log(`[smoke] scroll proxy: ${JSON.stringify(scroll)}`)
  check(scroll.proxyScrollHeight - scroll.proxyClientHeight >= 200, 'scroll proxy exposes >= 200px of scroll range')
  check(scroll.areaAfter > scroll.before, 'scroll proxy drives the real docen-document-area scroller')
  await page.screenshot({ path: path.join(OUT, 'docen-smoke-scrolled.png') })

  // Warm path: reload in the same context and repeat one edit.
  const reloadT0 = Date.now()
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 120_000 })
  await page.waitForFunction(READY_JS, null, { timeout: 120_000 })
  const reloadMs = Date.now() - reloadT0
  log(`[smoke] ready after reload in ${reloadMs} ms`)
  await editOnce('warm edit 1')

  const report = {
    url: HOST_URL,
    corpus: CORPUS,
    corpus_sha256: (await import('node:crypto')).createHash('sha256').update(corpusBytes).digest('hex'),
    ready_ms: readyMs,
    reload_ready_ms: reloadMs,
    edits: EDITS + 1,
    checks_failed: failures,
    state_after: await state()
  }
  fs.writeFileSync(path.join(OUT, 'docen-smoke-report.json'), JSON.stringify(report, null, 2))
} catch (error) {
  failures.push(String(error && error.stack ? error.stack : error))
  log('[smoke] ERROR ' + String(error && error.stack ? error.stack : error))
} finally {
  if (browser) await browser.close().catch(() => {})
  await stopServer(server)
  fs.writeFileSync(path.join(OUT, 'docen-smoke-console.log'), consoleLines.join('\n') + '\n')
}

if (failures.length > 0) {
  console.error(`\nSMOKE FAILED (${failures.length}):\n- ${failures.join('\n- ')}`)
  process.exit(1)
}
console.log('\nSMOKE PASSED')
