/**
 * Probe for the GenOffice rendering study.
 *
 * The driver calls probe(page) right before the screenshot, so this is where
 * the document is waited for and where the rendered DOM is inspected.  It only
 * reads the page; it never writes to it.
 */

/** Wait until the editor has actually painted the document. */
async function waitForDocument(page) {
  await page
    .waitForFunction(
      () => {
        const pages = document.querySelectorAll('.doc-page')
        if (!pages.length) return false
        return (document.body.innerText || '').length > 40
      },
      undefined,
      { timeout: 60000 },
    )
    .catch(() => {})
  // let images / charts / fonts settle
  await page.waitForTimeout(4000)
}

/** Everything the study asks about, read back out of the live DOM. */
const DIAG = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight
  }
  const chain = (el) => {
    const out = []
    let n = el
    for (let i = 0; n && i < 4; i++) {
      if (n.className && typeof n.className === 'string') out.push(n.className.split(/\s+/).join('.'))
      n = n.parentElement
    }
    return out.join(' < ')
  }
  const q = (sel) => Array.from(document.querySelectorAll(sel))

  const images = q('.doc-page img, .doc-page [class*="img"]').map((el) => ({
    tag: el.tagName,
    cls: el.className && el.className.toString ? el.className.toString() : '',
    src: (el.getAttribute && (el.getAttribute('src') || '')) || '',
    nat: el.naturalWidth || 0,
    box: [Math.round(el.getBoundingClientRect().width), Math.round(el.getBoundingClientRect().height)],
    visible: vis(el),
    chain: chain(el),
  }))

  const textOf = (sel) => q(sel).map((e) => (e.textContent || '').trim().slice(0, 120))

  return {
    // ---- pagination --------------------------------------------------
    pageCount: q('.doc-page').length,
    pageRects: q('.doc-page').map((p) => {
      const r = p.getBoundingClientRect()
      return {
        x: Math.round(r.x),
        y: Math.round(r.y),
        w: Math.round(r.width),
        h: Math.round(r.height),
        visible: vis(p),
      }
    }),
    statusBar: (document.querySelector('.status-bar') || {}).innerText || '',

    // ---- the constructs the brief asks about --------------------------
    constructs: {
      picture_imgs: images.filter((i) => i.tag === 'IMG'),
      chart_svgs: q('.doc-chart-svg svg, .doc-chart svg').length,
      chart_axis_labels: textOf('.doc-chart-axis-label'),
      chart_cats: textOf('.doc-chart-cat'),
      chart_vals: textOf('.doc-chart-val'),
      chart_name: textOf('.doc-chart-name'),
      chart_data_rows: textOf('.doc-chart-data tr').slice(0, 8),
      smartart: q('.doc-smartart, [class*="smartart"], [class*="diagram"]').length,
      dgm_nodes: q('[class*="dgm"]').length,
      textboxes: q('.doc-textbox').length,
      textbox_text: textOf('.doc-textbox'),
      ole: q('.doc-ole-wrap, .doc-ole-img, [class*="ole"]').length,
      ole_html: q('.doc-ole-wrap, [class*="ole"]').slice(0, 2).map((e) => e.outerHTML.slice(0, 400)),
      math: q('.doc-formula-math, math, [class*="formula"]').length,
      math_text: textOf('.doc-formula-math, [class*="formula"]'),
      text_outline: q('[class*="outline"], [style*="-webkit-text-stroke"]').length,
      text_outline_html: q('[style*="-webkit-text-stroke"]')
        .slice(0, 2)
        .map((e) => e.outerHTML.slice(0, 300)),
      note_refs: q('.doc-note-ref').length,
      note_ref_text: textOf('.doc-note-ref'),
      comment_marks: q('.doc-comment, [class*="comment"]').length,
      comment_html: q('.doc-comment').slice(0, 2).map((e) => e.outerHTML.slice(0, 300)),
      ins: q('.doc-ins').length,
      del: q('.doc-del').length,
      row_ins: q('.row-rev-ins').length,
      row_del: q('.row-rev-del').length,
      tables: q('.doc-page table').length,
    },

    // ---- what is inside the viewport right now -------------------------
    inViewport: (() => {
      const names = {
        picture: '.doc-img-wrap, .doc-protected-img, .doc-img-para',
        chart: '.doc-chart',
        smartart: '.doc-smartart, [class*="diagram"]',
        textbox: '.doc-textbox',
        ole: '.doc-ole-wrap, [class*="ole"]',
        equation: '.doc-formula-math, [class*="formula"]',
        comment: '.doc-comment',
        note: '.doc-note-ref',
        ins: '.doc-ins',
        del: '.doc-del',
        table: '.doc-page table',
      }
      const out = {}
      for (const [k, sel] of Object.entries(names)) {
        const els = q(sel)
        out[k] = {
          total: els.length,
          inView: els.filter(vis).length,
        }
      }
      return out
    })(),

    textLength: (document.body.innerText || '').length,
    textHead: (document.body.innerText || '').slice(0, 1200),
  }
}

export async function probe(page) {
  await waitForDocument(page)
  try {
    return await page.evaluate(DIAG)
  } catch (e) {
    return { error: String(e && e.stack ? e.stack : e) }
  }
}
