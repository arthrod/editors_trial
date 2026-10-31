import './style.css'
import Editor from '@hufe921/canvas-editor'
import docxPlugin from './docx-plugin'

const params = new URLSearchParams(window.location.search)
const DOC_URL = params.get('src') || '/sample.docx'
// Canvas-Editor paints its text into <canvas>, so the driver's DOM-based
// --scroll-text cannot find it. Two canvas-native ways to reach a spot:
//   ?scroll=<text>  -> the editor's own search API (highlight + scroll to match)
//   ?page=<n>       -> scroll the editor's scroll container to page n
const SCROLL_TEXT = params.get('scroll')
const PAGE_NO = params.get('page')

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

async function scrollToPage(n: number) {
  const editorEl = document.querySelector<HTMLDivElement>('#editor')
  if (!editorEl) return false
  const canvases = editorEl.querySelectorAll('.ce-page-container > canvas')
  const target = canvases[n - 1] as HTMLElement | undefined
  if (!target) return false
  const editorRect = editorEl.getBoundingClientRect()
  const targetRect = target.getBoundingClientRect()
  const delta = targetRect.top - editorRect.top
  editorEl.scrollTop +=
    delta - (editorEl.clientHeight - targetRect.height) / 2
  await sleep(400)
  return true
}

async function boot() {
  const container = document.querySelector<HTMLDivElement>('#editor')!
  const instance = new Editor(container, { main: [] })
  instance.use(docxPlugin)
  Reflect.set(window, '__CANVAS_EDITOR_INSTANCE__', instance)
  instance.listener.pageSizeChange = (payload: number) => {
    Reflect.set(window, '__PAGE_SIZE__', payload)
  }
  console.log('[host] editor instance ready, version =', instance.version)

  // Wait one frame so the container has a measurable width before the
  // document is imported and laid out.
  await new Promise(r => requestAnimationFrame(() => r(null)))

  const res = await fetch(DOC_URL)
  if (!res.ok) throw new Error(`[host] fetch ${DOC_URL} -> ${res.status}`)
  const arrayBuffer = await res.arrayBuffer()
  console.log('[host] fetched', DOC_URL, arrayBuffer.byteLength, 'bytes')

  // Capture the model the DOCX importer hands to the editor, BEFORE the
  // editor lays it out. This is what tells a plugin defect apart from an
  // editor-core defect.
  const command = instance.command as unknown as {
    executeSetValue: (data: unknown) => void
    executeImportDocx: (o: { arrayBuffer: ArrayBuffer }) => Promise<void>
  }
  const originalSetValue = command.executeSetValue.bind(instance.command)
  command.executeSetValue = (data: unknown) => {
    Reflect.set(window, '__SET_VALUE_DATA__', data)
    return originalSetValue(data)
  }

  await command.executeImportDocx({ arrayBuffer })

  console.log('[host] docx imported')
  Reflect.set(window, '__DOCX_IMPORTED__', true)

  // --- navigate to the requested spot ------------------------------------
  if (SCROLL_TEXT) {
    const cmd = instance.command as unknown as {
      executeSearch: (p: string, o?: object) => void
      executeSearchNavigateNext: () => void
      getSearchNavigateInfo: () => { index: number; count: number } | null
    }
    cmd.executeSearch(SCROLL_TEXT, { isIgnoreCase: true })
    cmd.executeSearchNavigateNext()
    await sleep(600)
    const info = cmd.getSearchNavigateInfo()
    console.log(
      '[host] search for',
      JSON.stringify(SCROLL_TEXT),
      '-> matches =',
      info ? info.count : 0,
      'current =',
      info ? info.index : 0
    )
    Reflect.set(window, '__SEARCH_INFO__', info)
  }
  if (PAGE_NO) {
    const ok = await scrollToPage(Number(PAGE_NO))
    console.log('[host] scrolled to page', PAGE_NO, 'ok =', ok)
  }
}

boot().catch(e => {
  console.error('[host] boot failed', e)
  Reflect.set(window, '__DOCX_ERROR__', String(e && (e as Error).stack ? (e as Error).stack : e))
})
