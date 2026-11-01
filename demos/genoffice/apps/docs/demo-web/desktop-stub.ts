type Handler = (...args: unknown[]) => void
const menu = new Set<Handler>()

function download(data: ArrayBuffer, name: string) {
  const url = URL.createObjectURL(
    new Blob([data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }),
  )
  const a = Object.assign(document.createElement('a'), { href: url, download: name.endsWith('.docx') ? name : `${name}.docx` })
  document.body.append(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

const PATH = '/demo/document.docx'
const saved = { ok: true, path: PATH }

const known: Record<string, unknown> = {
  getLanguage: async () => 'en',
  getSystemLocale: async () => 'en-US',
  getTheme: async () => 'light',
  getDocumentTheme: async () => 'follow',
  getAuthorName: async () => 'Demo',
  getRecentFiles: async () => [],
  consumePendingOpenDocx: async () => ({
    path: PATH,
    name: 'document.docx',
    dataUrl: new URL('./document.docx', location.href).href,
    hash: 'demo',
  }),
  consumeNewBlankDoc: async () => false,
  consumeAiDocContent: async () => null,
  confirmDocumentReplace: async () => true,
  convertAltChunkHtml: async () => null,
  saveDocx: async (_path: string, data: ArrayBuffer) => (download(data, 'document.docx'), saved),
  saveDocxAs: async (name: string, data: ArrayBuffer) => (download(data, name || 'document.docx'), saved),
  saveDocxNew: async (name: string, data: ArrayBuffer) => (download(data, name || 'document.docx'), saved),
  writeRecoveryCopy: async () => ({ ok: true }),
  onMenuCommand: (h: Handler) => (menu.add(h), () => menu.delete(h)),
}

// Any other member: on*/subscriptions return an unsubscribe, the rest resolve to undefined.
;(window as unknown as { desktop: unknown }).desktop = new Proxy(known, {
  get(target, key: string) {
    if (key in target) return target[key]
    if (/^on[A-Z]/.test(key)) return () => () => {}
    return () => Promise.resolve(undefined)
  },
})

document.getElementById('demo-download')?.addEventListener('click', () => {
  for (const h of menu) h('save-as')
})

// The Genspark AI panel needs the desktop app's model connection, which a browser page does not
// have: start with it closed, through the app's own remembered setting (the user can still open it).
if (localStorage.getItem('aidocs.showAi') === null) localStorage.setItem('aidocs.showAi', '0')
