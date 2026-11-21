/**
 * BetterOffice probe for harness/ui/shot.mjs (`--probe`).
 *
 * BetterOffice paints its pages on canvases; the text is in an accessible
 * "page mirror" the reader does not see, so shot.mjs's `--wait-for` and
 * `--scroll-text` (which read the visible text) cannot use it. This probe:
 *   1. waits for the editor's own whenLayoutComplete() (window.__host.loaded,
 *      set by main.js);
 *   2. if BO_SCROLL is set, finds the page whose mirror holds that text and
 *      asks the editor to go there with its own scrollToPage().
 * A document that did not lay out, or a target on no page, is a `miss`.
 */
const SCROLL = process.env.BO_SCROLL || '';

export async function probe(page) {
  const r = await page.evaluate(async () => {
    const loaded = await Promise.race([
      window.__host.loaded.then((v) => ({ ok: v }), (e) => ({ err: String(e && e.message || e) })),
      new Promise((res) => setTimeout(() => res({ err: 'layout not complete after 120 s' }), 120000)),
    ]);
    if (loaded.err) return { ...loaded, errors: window.__host.errors };
    const root = document.getElementById('root');
    const ref = window.__host.ref.current;
    return {
      ok: loaded.ok,
      totalPages: ref.getTotalPages(),
      comments: (await ref.getComments()).length,
      errors: window.__host.errors,
      // each page's size as drawn, in CSS pixels (a landscape page is wider than tall)
      pages: [...root.querySelectorAll('.paged-editor__page')].map((p) => [Math.round(p.offsetWidth), Math.round(p.offsetHeight)]),
      dom: { canvas: root.querySelectorAll('canvas').length, img: root.querySelectorAll('img').length },
    };
  });
  if (r.err) return { miss: `document did not load: ${r.err}`, errors: r.errors };
  await page.waitForTimeout(2000);
  if (!SCROLL) return r;

  const found = await page.evaluate(async (needle) => {
    let best = null;
    for (const n of document.querySelectorAll('.layout-page-mirror *')) {
      const t = n.textContent || '';
      if (t.includes(needle) && (!best || t.length < best.textContent.length)) best = n;
    }
    const pageEl = best && best.closest('.layout-page-mirror');
    if (!pageEl) return null;
    const n = Number(pageEl.getAttribute('data-page-index')) + 1;
    await window.__host.ref.current.scrollToPage(n);
    return n;
  }, SCROLL);
  if (!found) return { ...r, miss: `"${SCROLL}" is on none of the ${r.totalPages} pages` };
  await page.waitForTimeout(3000);
  return { ...r, scrolled: SCROLL, page: found };
}
