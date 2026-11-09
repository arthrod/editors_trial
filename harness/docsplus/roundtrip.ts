/**
 * docs.plus DOCX round-trip harness.
 *
 * Drives the product's own conversion domain end to end:
 *   fixture .docx --mammoth--> HTML --parseDocumentHtml--> Tiptap JSON
 *                --renderDocumentHtml--> HTML --@turbodocx/html-to-docx--> .docx
 *
 * Run from the repo copy root so the bun workspace resolves:
 *   cd repo-copy && bun <harness>/roundtrip.ts <in.docx> <out.docx>
 *
 * The ONLY thing stubbed is the object-storage boundary that the domain
 * deliberately does not own: `uploadImage` is injected by the caller. It is
 * backed by a loopback HTTP server holding the real bytes in memory, so the
 * image genuinely travels the bridge (import -> rehost -> allowlist -> inline
 * -> word/media/) instead of being silently dropped by a fake URL.
 */
import { createServer } from 'node:http'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'

import { importDocx } from './repo-copy/apps/hocuspocus.server/src/modules/document-conversion/domain/docxImport'
import { exportDocx } from './repo-copy/apps/hocuspocus.server/src/modules/document-conversion/domain/docxExport'
import {
  parseDocumentHtml,
  renderDocumentHtml
} from './repo-copy/apps/hocuspocus.server/src/modules/document-conversion/domain/documentHtml'

const DOCX_STYLE_MAP = [
  "p[style-name='Title'] => h1:fresh",
  'p.Title => h1:fresh',
  "p[style-name='Subtitle'] => p:fresh",
  'p.Subtitle => p:fresh',
  "p[style-name='Quote'] => blockquote:fresh",
  "p[style-name='Intense Quote'] => blockquote:fresh",
  'p.Quote => blockquote:fresh',
  'u => u',
  'strike => s'
]

const PERF_ONLY = process.env.PERF_ONLY === '1'

const inPath = process.argv[2]
const outPath = process.argv[3]
if (!inPath || !outPath) {
  console.error('usage: bun roundtrip.ts <in.docx> <out.docx>')
  process.exit(2)
}

const HARNESS = dirname(new URL(import.meta.url).pathname)
const scratch = resolve(process.env.EVIDENCE_DIR || resolve(HARNESS, 'evidence'))
if (!PERF_ONLY) await mkdir(scratch, { recursive: true })

/** Loopback stand-in for the pad's object storage. */
const store = new Map<string, { bytes: Buffer; type: string }>()
let seq = 0

const server = createServer((req, res) => {
  const key = (req.url ?? '').split('?')[0]
  const hit = store.get(key)
  if (!hit) {
    res.writeHead(404, { 'content-type': 'text/plain' })
    res.end('not found')
    return
  }
  res.writeHead(200, { 'content-type': hit.type, 'content-length': hit.bytes.length })
  res.end(hit.bytes)
})

await new Promise<void>((resolveListen, rejectListen) => {
  server.once('error', rejectListen)
  server.listen(0, '127.0.0.1', () => resolveListen())
})
const address = server.address()
if (address === null || typeof address === 'string') throw new Error('no port')
const origin = `http://127.0.0.1:${address.port}`
console.log(`[stub] media origin = ${origin}`)

const buffer = await readFile(inPath)

const uploadImage = async (data: Buffer, contentType: string): Promise<string> => {
  const name = `media/${++seq}.png`
  store.set(`/${name}`, { bytes: data, type: contentType || 'image/png' })
  console.log(`[stub] uploadImage -> ${origin}/${name} (${data.length}B ${contentType})`)
  return `${origin}/${name}`
}

// --- 1. import -------------------------------------------------------------
const t0 = performance.now()
const importResult = await importDocx(buffer, {
  fallbackTitle: 'Complex Fixture',
  uploadImage
})
const t1 = performance.now()
console.log(`PERF model_ready_ms=${(t1 - t0).toFixed(6)}`)
const doc = importResult.content
console.log(`[import] title      = ${JSON.stringify(importResult.title)}`)
console.log(`[import] warnings   = ${importResult.warnings.length}`)
for (const w of importResult.warnings) console.log(`         - ${w.code}: ${w.message}`)
let rendered = ''
if (!PERF_ONLY) {
  await writeFile(resolve(scratch, 'import.tiptap.json'), JSON.stringify(doc, null, 2))

  // --- 2. intermediate HTML (what the converter actually sees) --------------
  rendered = await renderDocumentHtml(doc, importResult.title, origin, null)
  await writeFile(resolve(scratch, 'rendered.html'), rendered)
  console.log(`[render] html length = ${rendered.length}`)
}

// --- 3. export -------------------------------------------------------------
const tSave0 = performance.now()
const out = await exportDocx(doc, importResult.title, origin, null)
const tSave1 = performance.now()
console.log(`PERF save_ms=${(tSave1 - tSave0).toFixed(6)}`)
await writeFile(outPath, out)
console.log(`[export] wrote ${outPath} (${out.length}B)`)

// The product path ends at exportDocx. The mammoth scan below is harness
// evidence for the fidelity report. A bomb run must not let that scan decide
// the process status.
if (PERF_ONLY || process.env.EDITOR_CONFIG === 'suggested') {
  server.close()
  process.exit(0)
}

// --- 4. tracked-change evidence -------------------------------------------
// Re-run mammoth exactly as docxImport does, so the raw import HTML can be
// inspected for revision markup independently of the parsed Tiptap JSON.
// Resolved through the repo copy's own node_modules: this script lives outside
// the bun workspace, so a bare 'mammoth' specifier cannot be resolved.
const mammoth = (
  await import('./repo-copy/apps/hocuspocus.server/node_modules/mammoth')
).default as {
  convertToHtml: (
    input: { buffer: Buffer },
    options: { styleMap: string[] }
  ) => Promise<{ value: string; messages: unknown[] }>
}
const raw = await mammoth.convertToHtml({ buffer }, { styleMap: DOCX_STYLE_MAP })
await writeFile(resolve(scratch, 'mammoth.html'), raw.value)
const preTitle = parseDocumentHtml(raw.value)
await writeFile(resolve(scratch, 'mammoth.tiptap.json'), JSON.stringify(preTitle, null, 2))

const REVISION_PATTERNS = [
  'w:ins',
  'w:del',
  'delText',
  'moveFrom',
  'moveTo',
  'rPrChange',
  'pPrChange',
  '<ins',
  '<del',
  'tracked change',
  'author='
]
const scan = (label: string, text: string) => {
  const hits: Record<string, number> = {}
  for (const p of REVISION_PATTERNS) {
    const n = text.split(p).length - 1
    if (n > 0) hits[p] = n
  }
  console.log(`[evidence] ${label}: len=${text.length} hits=${JSON.stringify(hits)}`)
  return hits
}
scan('mammoth.html', raw.value)
scan('rendered.html', rendered)
scan('tiptap.json', JSON.stringify(doc))

const evidence = {
  origin,
  title: importResult.title,
  warnings: importResult.warnings,
  mammothHtmlLength: raw.value.length,
  renderedHtmlLength: rendered.length,
  mammothHtmlRevisionHits: scan('mammoth.html', raw.value),
  renderedHtmlRevisionHits: scan('rendered.html', rendered),
  tiptapRevisionHits: scan('tiptap.json', JSON.stringify(doc))
}
await writeFile(resolve(scratch, 'evidence.json'), JSON.stringify(evidence, null, 2))

server.close()
