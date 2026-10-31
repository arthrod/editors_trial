/**
 * Probe: dumps the editor's rendered DOM layout so we can work out how to
 * scroll a canvas-rendered editor to a given page.
 */
export async function probe(page) {
  return await page.evaluate(() => {
    const editorEl = document.querySelector('#editor')
    const container = document.querySelector('.ce-page-container') ||
      document.querySelector('.ce-page') ||
      editorEl
    const describe = el => {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return {
        tag: el.tagName,
        cls: el.className && el.className.toString().slice(0, 60),
        w: Math.round(r.width),
        h: Math.round(r.height),
        top: Math.round(r.top + window.scrollY),
        left: Math.round(r.left + window.scrollX)
      }
    }
    const kids = []
    const walk = (el, depth) => {
      if (!el || depth > 4) return
      for (const c of el.children) {
        kids.push({ depth, ...describe(c) })
        walk(c, depth + 1)
      }
    }
    walk(editorEl, 0)
    return {
      imported: !!window.__DOCX_IMPORTED__,
      pageSize: window.__PAGE_SIZE__ ?? null,
      editorScrollTop: editorEl ? editorEl.scrollTop : null,
      editorScrollHeight: editorEl ? editorEl.scrollHeight : null,
      editorClientHeight: editorEl ? editorEl.clientHeight : null,
      container: describe(container),
      tree: kids.slice(0, 40)
    }
  })
}
