import Editor from '@hufe921/canvas-editor'
import docxPlugin from '@hufe921/canvas-editor-plugin-docx'

const container = document.querySelector<HTMLDivElement>('#editor')!
const editor = new Editor(
  container,
  { header: [], main: [{ value: '\n' }], footer: [] },
  {
    width: 794,
    height: 1123,
    margins: [100, 120, 100, 120]
  }
)

docxPlugin(editor)

const command = editor.command as typeof editor.command & {
  executeImportDocx(options: { arrayBuffer: ArrayBuffer }): Promise<void>
  executeExportDocx(options: {
    fileName: string
    download?: boolean
  }): Promise<Blob>
}

const page = window as Window & {
  editor: Editor
  __docxReady?: boolean
  __docxError?: string
}
page.editor = editor

document.getElementById('download')!.addEventListener('click', () => {
  void command.executeExportDocx({ fileName: 'document' })
})

function fitPage() {
  const options = command.getValue()?.options as { width?: number } | undefined
  const pageWidth = Number(options?.width) || 794
  const available = Math.max(280, document.documentElement.clientWidth - 16)
  const scale = Math.min(1, available / pageWidth)
  command.executePageScale(Number(scale.toFixed(3)))
}

window.addEventListener('resize', () => {
  if (page.__docxReady) fitPage()
})

async function openDocument() {
  const response = await fetch('./document.docx')
  if (!response.ok) {
    throw new Error(`failed to fetch document.docx: ${response.status}`)
  }
  const arrayBuffer = await response.arrayBuffer()
  await command.executeImportDocx({ arrayBuffer })
  fitPage()
  page.__docxReady = true
}

openDocument().catch((error: unknown) => {
  const message = error instanceof Error ? error.stack || error.message : String(error)
  page.__docxError = message
  console.error(error)
})

// canvas-editor paints on <canvas>, so the page has no DOM text. Expose the document's text,
// read back through the editor's own API, for the demo verifier.
;(window as Window & { __demoText?: () => string }).__demoText = () => {
  const out: string[] = []
  const walk = (node: unknown): void => {
    if (Array.isArray(node)) return node.forEach(walk)
    if (!node || typeof node !== 'object') return
    const o = node as Record<string, unknown>
    if (typeof o.value === 'string') out.push(o.value)
    for (const k of ['valueList', 'trList', 'tdList']) if (o[k]) walk(o[k])
  }
  const data = command.getValue().data as Record<string, unknown>
  for (const zone of ['header', 'main', 'footer']) walk(data[zone])
  return out.join('').replace(/\n/g, ' ')
}
