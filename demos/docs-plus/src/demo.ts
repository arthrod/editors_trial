/**
 * The demo page.
 *
 * It does exactly what the product does when a Word file is opened on the pad:
 *
 *   ./document.docx -> importDocx()  (mammoth -> HTML -> Tiptap JSON)
 *                   -> Tiptap editor (docs.plus schema)
 *                   -> exportDocx() (Tiptap JSON -> HTML -> .docx)
 *
 * `importDocx` and `exportDocx` are the product's own modules, imported
 * unchanged from the checkout; only the platform edges (mammoth's browser
 * entry, the DOM, `node:zlib`) are shimmed.
 */
import { Buffer } from 'buffer'

import { exportDocx } from '../../src/apps/hocuspocus.server/src/modules/document-conversion/domain/docxExport'
import { importDocx } from '../../src/apps/hocuspocus.server/src/modules/document-conversion/domain/docxImport'
import { zipInflateSize } from '../../src/apps/hocuspocus.server/src/modules/document-conversion/domain/zipInflateSize'
import { MAX_INFLATED_IMPORT_BYTES } from '../../src/apps/hocuspocus.server/src/modules/document-conversion/types'

import { createEditor } from './editor'
import { MEDIA_MANIFEST } from './generated/media-manifest'
import { hashBytes } from '../shared/media-hash.mjs'

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const FALLBACK_TITLE = 'Complex Fixture'

const toUint8Array = (value: unknown): Uint8Array => {
  if (value instanceof Uint8Array) return value
  if (ArrayBuffer.isView(value)) {
    const view = value as ArrayBufferView
    return new Uint8Array(view.buffer, view.byteOffset, view.byteLength)
  }
  if (value instanceof ArrayBuffer) return new Uint8Array(value)
  return new Uint8Array(value as ArrayLike<number>)
}

const status = document.getElementById('status') as HTMLElement
const editorHost = document.getElementById('editor') as HTMLElement
const downloadButton = document.getElementById('download-docx') as HTMLAnchorElement
const titleLabel = document.getElementById('doc-title') as HTMLElement

const setStatus = (text: string): void => {
  status.textContent = text
  status.dataset.state = text.startsWith('Could not') ? 'error' : 'loading'
}

/**
 * The folder the demo is served from, with a trailing slash.
 *
 * `document.baseURI` is the page URL; when the host mounts the demo without a
 * trailing slash the last path segment is the file name, not the folder.
 */
const siteBase = (): string => {
  const url = new URL(document.baseURI)
  if (!url.pathname.endsWith('/')) url.pathname = url.pathname.replace(/[^/]*$/, '')
  return url.href
}

/** Same-folder base URL: the demo's own origin and mount point. */
const baseUrl = (): string => siteBase()

/**
 * The pad re-hosts imported images on its media route; the static demo ships
 * the document's media next to it and returns the same-folder URL. The domain
 * refuses anything that is not a readable image URL.
 */
const uploadImage = async (data: Buffer, contentType: string): Promise<string> => {
  const bytes = toUint8Array(data)
  const file = MEDIA_MANIFEST[hashBytes(bytes)]
  if (!file) {
    throw new Error(`Image (${contentType}) is not part of the bundled media set`)
  }
  return new URL(file, siteBase()).href
}

const readDocument = async (): Promise<Uint8Array> => {
  const response = await fetch(new URL('document.docx', siteBase()).href)
  if (!response.ok) throw new Error(`Could not load document.docx (${response.status})`)
  return new Uint8Array(await response.arrayBuffer())
}

const download = (bytes: Uint8Array, fileName: string): void => {
  const blob = new Blob([bytes], { type: DOCX_MIME })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.rel = 'noopener'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 30_000)
}

const run = async (): Promise<void> => {
  setStatus('Loading document.docx…')
  const bytes = await readDocument()
  const buffer = Buffer.from(bytes)

  // The pad's import endpoint refuses a zip that unpacks past its budget
  // before mammoth ever sees it. The demo keeps that guard.
  const inflated = zipInflateSize(buffer, MAX_INFLATED_IMPORT_BYTES)
  if (inflated !== null && inflated > MAX_INFLATED_IMPORT_BYTES) {
    throw new Error('document.docx unpacks to more than the import limit')
  }

  setStatus('Importing with mammoth…')
  const result = await importDocx(buffer, {
    fallbackTitle: FALLBACK_TITLE,
    uploadImage
  })

  for (const warning of result.warnings) {
    console.warn(`[docs.plus import] ${warning.code}: ${warning.message}`)
  }

  const editor = createEditor(editorHost, result.content)
  titleLabel.textContent = result.title
  titleLabel.title = result.title
  document.title = `${result.title} — docs.plus`

  downloadButton.addEventListener('click', (event) => {
    event.preventDefault()
    downloadButton.dataset.busy = 'true'
    setStatus('Exporting .docx…')
    exportDocx(editor.getJSON(), result.title, baseUrl(), null)
      .then((output) => {
        download(toUint8Array(output), 'document.docx')
        setStatus('Exported document.docx')
      })
      .catch((error: unknown) => {
        console.error('[docs.plus export]', error)
        setStatus(`Could not export: ${error instanceof Error ? error.message : String(error)}`)
      })
      .finally(() => {
        delete downloadButton.dataset.busy
      })
  })

  setStatus('Ready')

  const scope = globalThis as unknown as Record<string, unknown>
  scope.__docsPlusDemo = {
    title: result.title,
    warnings: result.warnings,
    text: editor.getText(),
    json: editor.getJSON(),
    editor,
    inflatedBytes: inflated,
    exportDocx: () => exportDocx(editor.getJSON(), result.title, baseUrl(), null)
  }
  document.body.dataset.ready = 'true'
}

run().catch((error: unknown) => {
  console.error('[docs.plus demo]', error)
  setStatus(`Could not open the document: ${error instanceof Error ? error.message : String(error)}`)
  document.body.dataset.ready = 'error'
})
