/**
 * Read-only exploration of the running docs.plus /editor playground.
 * Dumps the auth store state (isVisitor gate), the toolbar controls, and
 * whether the doc-settings popover can be opened.
 */
import { chromium } from 'playwright'

const url = process.argv[2] || 'http://127.0.0.1:5205/editor'

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => {
  if (m.type() === 'error' || m.type() === 'warning') console.log(`[console:${m.type()}] ${m.text()}`)
})

await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 })
await page.waitForFunction(() => !!window._editor, { timeout: 60000 })
await page.waitForTimeout(3000)

const state = await page.evaluate(() => {
  const auth = window._authStore?.getState?.() ?? null
  const store = window._store?.getState?.() ?? null
  const settings = store?.settings ?? null
  return {
    auth: auth && {
      loading: auth.loading,
      sessionId: auth.session?.id ?? null,
      profileId: auth.profile?.id ?? null,
      profileError: auth.profileError
    },
    // exactly what components/auth/isVisitor.ts computes
    isVisitor: auth ? !auth.loading && !(auth.profile?.id ?? auth.session?.id) : 'no authStore',
    settingsKeys: settings ? Object.keys(settings) : null,
    metadata: settings?.metadata ?? null,
    editorLoading: settings?.editor?.loading,
    providerSyncing: settings?.editor?.providerSyncing,
    isAuthServiceAvailable: settings?.isAuthServiceAvailable,
    editorName: window._editor?.constructor?.name,
    editorSchemaNodes: window._editor
      ? Object.keys(window._editor.schema.nodes).sort()
      : null,
    toolbarButtons: Array.from(document.querySelectorAll('.tiptap__toolbar button')).map((b) => ({
      label: b.getAttribute('aria-label'),
      testid: b.getAttribute('data-testid')
    })),
    bodyTextHead: document.body.innerText.slice(0, 400)
  }
})
console.log(JSON.stringify(state, null, 2))
console.log('pageErrors:', errors.slice(0, 5))
await browser.close()
