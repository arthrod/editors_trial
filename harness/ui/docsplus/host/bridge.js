/**
 * Bridge injected into docs.plus's own /editor page by serve.mjs.
 *
 * The product has no "open a DOCX from a URL" entry point: a DOCX arrives as an
 * upload, is converted by the server (mammoth + parseDocumentHtml), and the
 * result replaces the pad. This bridge performs exactly that, without the
 * eight toolbar clicks, and then publishes a ready signal that only fires once
 * the document is in the editor and painted:
 *
 *   GET  <corpusRoute>                     -> the DOCX bytes
 *   POST <rest>/documents/harness/import   -> the product's own import endpoint
 *   editor.commands.setContent(content)    -> what applyImportedContent() does
 *
 * Signals:
 *   window.__DOCSPLUS_READY__ === true   set after the document has painted
 *   #perf-status[data-state="ready"]     the same moment, visible on screen
 *   window.__DOCSPLUS_INFO__             title, warnings, counts, timings
 *   window.__DOCSPLUS_ERROR__            set instead of READY when it fails
 *
 * The UI staging panel ("Replace document") is bypassed, so
 * commitImportedImageSizes() does not run; the corpus carries explicit image
 * extents, so the pictures arrive sized.
 */

const config = window.__PERF_HOST__ || {
  rest: 'http://127.0.0.1:4210/api',
  corpusRoute: '/corpus.docx',
}

const t0 = performance.now()
const timings = {}

const badge = document.createElement('div')
badge.id = 'perf-status'
badge.dataset.state = 'booting'
badge.textContent = 'perf: booting'
Object.assign(badge.style, {
  position: 'fixed',
  right: '8px',
  bottom: '8px',
  zIndex: '2147483647',
  padding: '2px 6px',
  borderRadius: '4px',
  font: '11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace',
  background: '#111',
  color: '#ddd',
  opacity: '0.85',
  pointerEvents: 'none',
})
const mountBadge = () => {
  if (!badge.isConnected && document.body) document.body.appendChild(badge)
}
mountBadge()

const setState = (state, text) => {
  mountBadge()
  badge.dataset.state = state
  badge.textContent = text
}

const fail = (stage, error) => {
  const message = `${stage}: ${error && error.message ? error.message : String(error)}`
  window.__DOCSPLUS_ERROR__ = message
  setState('error', `perf: error — ${message}`.slice(0, 160))
  console.error('[perf-host]', message)
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function waitFor(predicate, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const value = predicate()
    if (value) return value
    await sleep(50)
  }
  throw new Error(`timed out waiting for ${label}`)
}

const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve(null)))

async function waitForPaint(count = 2) {
  for (let i = 0; i < count; i += 1) await nextFrame()
}

/** All <img> in the editor decoded (or errored) — the corpus has pictures. */
async function waitForImages(root) {
  const images = Array.from(root.querySelectorAll('img'))
  if (images.length === 0) return 0
  await Promise.all(
    images.map((img) =>
      (img.complete
        ? Promise.resolve()
        : new Promise((resolve) => {
            img.addEventListener('load', resolve, { once: true })
            img.addEventListener('error', resolve, { once: true })
          })
      ).then(() => (typeof img.decode === 'function' ? img.decode().catch(() => {}) : null))
    )
  )
  return images.length
}

async function run() {
  const editor = await waitFor(() => {
    const candidate = window._editor
    return candidate && !candidate.isDestroyed && candidate.view && candidate.view.dom ? candidate : null
  }, 120000, 'window._editor')
  timings.editor_mounted = performance.now() - t0
  setState('importing', 'perf: importing corpus')

  const response = await fetch(config.corpusRoute, { cache: 'no-store' })
  if (!response.ok) throw new Error(`GET ${config.corpusRoute} -> ${response.status}`)
  const bytes = await response.blob()
  timings.corpus_fetched = performance.now() - t0

  const form = new FormData()
  form.append('documentFile', new File([bytes], 'corpus.docx', { type: bytes.type }))
  const imported = await fetch(`${config.rest}/documents/harness/import`, {
    method: 'POST',
    body: form,
  })
  if (!imported.ok) throw new Error(`POST import -> ${imported.status}`)
  const payload = await imported.json()
  if (!payload || !payload.success) throw new Error('import rejected by the endpoint')
  const { content, title, warnings } = payload.data
  timings.imported = performance.now() - t0

  // Same call applyImportedContent() makes once the user confirms.
  window._editor.commands.setContent(content)
  timings.applied = performance.now() - t0

  await waitFor(() => {
    const el = document.querySelector('.tiptap__editor')
    return el && el.querySelector('.ProseMirror') && window._editor.getText().length > 0
  }, 30000, 'rendered document')

  const editorRoot = document.querySelector('.tiptap__editor')
  // Fonts settle before the gate: a late face swap would otherwise reflow the
  // page after "ready" and land inside the probe's first-edit measurement.
  if (document.fonts && document.fonts.ready) await document.fonts.ready.catch(() => {})
  const images = await waitForImages(editorRoot)
  await waitForPaint(2)

  setState('ready', `perf: ready — ${window._editor.getText().length} chars`)
  await waitForPaint(1)

  timings.ready = performance.now() - t0
  window.__DOCSPLUS_INFO__ = {
    title,
    warnings: Array.isArray(warnings) ? warnings.length : 0,
    text_length: window._editor.getText().length,
    images,
    timings,
  }
  window.__DOCSPLUS_READY__ = true
  console.log('[perf-host] ready', JSON.stringify(window.__DOCSPLUS_INFO__))
}

if (new URLSearchParams(location.search).get('perf') === '0') {
  setState('idle', 'perf: bridge disabled')
} else {
  run().catch((error) => fail('load', error))
}
