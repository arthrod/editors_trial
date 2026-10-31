/**
 * docs.plus probe — loads fixture/complex.docx into the running docs.plus
 * editor through the product's OWN import path and reports what it renders.
 *
 * The path exercised here is docs.plus's own, end to end:
 *   toolbar "Document settings" -> "Import & export" -> "Choose file…"
 *   -> apps/webapp/src/components/TipTap/toolbar/desktop/ImportExportSection.tsx
 *      pickFile() creates input[accept=".docx,.md"], convert(file) calls
 *      importDocument() (apps/webapp/src/api/documents/importDocument.ts)
 *      -> POST ${NEXT_PUBLIC_RESTAPI_URL}/documents/:id/import
 *      -> repo domain importDocx() (mammoth + parseDocumentHtml)
 *      -> staged preview -> "Replace document"
 *      -> applyImportedContent() -> editor.commands.setContent(...)
 *
 * The one thing the driver cannot do on its own is satisfy the
 * `isVisitor()` gate in pickFile(). We use the product's own playground
 * escape hatch for that — window._authStore / window._store, the same hooks
 * the repo's own Cypress specs use (apps/webapp/cypress/support/hyperlinkPicker.ts).
 * It changes who the UI thinks you are; it does not change how the document renders.
 *
 * Env:
 *   DOCSPLUS_FIXTURE     path to the .docx (default: the study fixture)
 *   DOCSPLUS_SCROLL_TEXT scroll the editor to the first element holding this text
 *   DOCSPLUS_SCROLL_TOP  '1' to scroll the editor back to the top first
 */
import path from 'node:path'

const FIXTURE =
  process.env.DOCSPLUS_FIXTURE || '/Users/arthrod/temp/T/editors_trial/fixture/complex.docx'
const SCROLL_TEXT = process.env.DOCSPLUS_SCROLL_TEXT || ''
const SCROLL_TOP = process.env.DOCSPLUS_SCROLL_TOP === '1'

/** Textual probes: what the corpus contains in Word vs what the UI shows. */
const MARKERS = [
  'fixture image',
  'Cat A',
  'Series 1',
  'Text box content',
  'AlternateContent fallback text',
  'This row was deleted',
  'This row was inserted',
  'Commented',
  'This is a comment body',
  'This is the footnote body',
  'This is the endnote body',
  'OLE',
  'SmartArt',
  'diagram',
  'equation',
  'Chapter 1'
]

export async function probe(page) {
  const report = { fixture: FIXTURE, steps: [] }
  const step = (name, detail) => {
    report.steps.push({ name, ...detail })
  }

  // ---- 0. wait for the playground to publish its escape hatches -----------
  await page.waitForFunction(() => !!window._editor && !!window._authStore && !!window._store, {
    timeout: 90000
  })

  // ---- 1. identity: satisfy isVisitor() through the product's own hook -----
  const seeded = await page.evaluate(() => {
    if (!window._authStore || !window._store) return { ok: false, reason: 'playground hooks missing' }
    window._authStore.getState().setProfile({ id: 'harness-user', username: 'harness' })
    window._store.getState().setWorkspaceSetting('metadata', {
      documentId: 'harness-doc',
      slug: 'complex-fixture',
      title: 'Complex Fixture',
      description: '',
      keywords: []
    })
    const a = window._authStore.getState()
    return {
      ok: true,
      loading: a.loading,
      profileId: a.profile?.id ?? null,
      isVisitor: !a.loading && !(a.profile?.id ?? a.session?.id)
    }
  })
  step('seed-auth', seeded)
  if (!seeded.ok) return report

  // ---- 2. toolbar: Document settings -> Import & export -------------------
  await page.click('button[aria-label="Document settings"]', { timeout: 20000 })
  await page.waitForTimeout(800)
  step('open-document-settings', { ok: true })

  // daisyUI's collapse hides the radio over the title, so the radio itself is
  // the clickable thing; clicking it checks the group and opens the section.
  const opened = await page
    .click('input[name="gear-accordion"][aria-label="Import & export"]', { timeout: 15000 })
    .then(() => true)
    .catch(async (e) => {
      await page.click('.collapse-title:has-text("Import & export")', { force: true, timeout: 10000 })
      return `forced: ${e.message.slice(0, 80)}`
    })
  await page.waitForTimeout(800)
  step('expand-import-export', { opened })

  // ---- 3. "Choose file…" creates the hidden input -------------------------
  // pickFile() builds input[accept=".docx,.md"], appends it to <body> and
  // calls input.click(). Playwright intercepts the native chooser; the app's
  // own 'cancel' handler removes the input again, so the file has to be handed
  // over through the filechooser event rather than by finding the input later.
  const chooserPromise = page.waitForEvent('filechooser', { timeout: 20000 })
  await page.click('button:has-text("Choose file…")', { timeout: 15000 })
  const chooser = await chooserPromise
  await chooser.setFiles(path.resolve(FIXTURE))
  step('pick-file', { ok: true, acceptsMultiple: chooser.isMultiple() })

  // the panel must reach the staged state before "Replace document" exists
  const staged = await page
    .waitForSelector('button:has-text("Replace document")', { timeout: 60000 })
    .then(async (el) => {
      const panel = await el.evaluateHandle((n) => n.closest('.rounded-box')?.innerText ?? '')
      return { ok: true, panel: String(await panel.jsonValue()) }
    })
    .catch((e) => ({ ok: false, error: e.message }))
  step('staged', staged)

  // ---- 5. apply ------------------------------------------------------------
  await page.click('button:has-text("Replace document")', { timeout: 15000 })
  await page
    .waitForFunction(
      () => {
        const ed = window._editor
        if (!ed) return false
        return ed.getText().includes('Chapter 1')
      },
      { timeout: 45000 }
    )
    .catch(() => {})
  await page.waitForTimeout(2500)
  step('replace-document', { ok: true })

  // ---- 6. close the settings popover so it does not cover the document ----
  await page.keyboard.press('Escape').catch(() => {})
  await page.waitForTimeout(600)
  const popoverStillOpen = await page
    .locator('button:has-text("Replace document"), button:has-text("Choose file…")')
    .first()
    .isVisible()
    .catch(() => false)
  if (popoverStillOpen) {
    await page.mouse.click(200, 600).catch(() => {})
    await page.waitForTimeout(600)
  }
  step('close-panel', { popoverStillOpen })

  // ---- 7. scroll ----------------------------------------------------------
  const scrolled = await page.evaluate(
    ({ needle, top }) => {
      const scroller = document.querySelector('.editorWrapper') ?? document.scrollingElement
      if (top && scroller) scroller.scrollTop = 0
      if (!needle) return { ok: true, top: true }
      const low = needle.toLowerCase()
      let best = null
      let bestLen = Infinity
      for (const n of document.querySelectorAll('.tiptap__editor *')) {
        const txt = (n.textContent || '').toLowerCase()
        if (!txt.includes(low)) continue
        if (txt.length < bestLen) {
          best = n
          bestLen = txt.length
        }
      }
      if (!best) return { ok: false, needle }
      best.scrollIntoView({ block: 'center', inline: 'center' })
      return { ok: true, needle, tag: best.tagName, text: (best.textContent || '').slice(0, 80) }
    },
    { needle: SCROLL_TEXT, top: SCROLL_TOP }
  )
  await page.waitForTimeout(1200)
  step('scroll', scrolled)

  // ---- 8. what does the UI actually show? --------------------------------
  const rendered = await page.evaluate((markers) => {
    const ed = window._editor
    const text = ed ? ed.getText() : ''
    const doc = ed ? ed.state.doc : null

    const nodes = {}
    let images = []
    let tables = 0
    let rows = 0
    let comments = 0
    doc?.descendants((node) => {
      nodes[node.type.name] = (nodes[node.type.name] || 0) + 1
      if (node.type.name === 'image') {
        images.push({
          src: node.attrs.src,
          alt: node.attrs.alt ?? null,
          width: node.attrs.width ?? null,
          height: node.attrs.height ?? null
        })
      }
      if (node.type.name === 'table') tables += 1
      if (node.type.name === 'tableRow') rows += 1
      if (node.type.name === 'comment') comments += 1
    })

    const imgEls = Array.from(document.querySelectorAll('.tiptap__editor img')).map((i) => ({
      src: i.currentSrc || i.src,
      alt: i.alt,
      complete: i.complete,
      naturalWidth: i.naturalWidth,
      naturalHeight: i.naturalHeight,
      renderedWidth: Math.round(i.getBoundingClientRect().width),
      renderedHeight: Math.round(i.getBoundingClientRect().height)
    }))

    const svgEls = Array.from(document.querySelectorAll('.tiptap__editor svg')).length
    const svgDetail = Array.from(document.querySelectorAll('.tiptap__editor svg')).map((s) =>
      (s.outerHTML || '').slice(0, 160)
    )
    const canvasEls = Array.from(document.querySelectorAll('.tiptap__editor canvas')).length
    const mathEls = document.querySelectorAll('.tiptap__editor math, .tiptap__editor [class*="katex"]').length

    const body = document.body.innerText
    const present = {}
    for (const m of markers) present[m] = body.includes(m)

    return {
      markersPresent: present,
      nodeTypes: nodes,
      images,
      imageElements: imgEls,
      svgCount: svgEls,
      svgDetail,
      canvasCount: canvasEls,
      mathElementCount: mathEls,
      tables,
      tableRows: rows,
      commentNodes: comments,
      textLength: text.length,
      textHead: text.slice(0, 600),
      textTail: text.slice(-600)
    }
  }, MARKERS)
  report.rendered = rendered

  return report
}
