/**
 * Apryse WebViewer probe for harness/ui/shot.mjs (`--probe`).
 *
 * WebViewer's DOCX Editor draws its pages on a canvas, so shot.mjs's
 * `--wait-for` / `--scroll-text` (which read the DOM's text) cannot see them.
 * This probe asks WebViewer instead:
 *   1. waits for window.__apryse.loaded (document and its comments loaded,
 *      set by harness/apryse/main.js);
 *   2. if APRYSE_SCROLL is set, reads each page's text through WebViewer's
 *      API and goes to the first page that contains it.
 * A target it cannot reach is returned as `miss`, which fails the capture.
 */
const SCROLL = process.env.APRYSE_SCROLL || '';

export async function probe(page) {
  const loaded = await page.evaluate(async () => {
    const r = await Promise.race([
      window.__apryse.loaded.then((v) => ({ ok: v }), (e) => ({ err: String(e) })),
      new Promise((res) => setTimeout(() => res({ err: 'not loaded after 90 s' }), 90000)),
    ]);
    return r;
  });
  if (loaded.err) return { miss: `document did not load: ${loaded.err}` };
  await page.waitForTimeout(3000);
  if (!SCROLL) return { loaded: loaded.ok };

  const found = await page.evaluate(async (needle) => {
    const { documentViewer } = window.__apryse.instance.Core;
    const doc = documentViewer.getDocument();
    const n = doc.getPageCount();
    const norm = (s) => s.replace(/\s+/g, ' ').toLowerCase();
    for (let p = 1; p <= n; p++) {
      const text = await doc.loadPageText(p);
      if (norm(text).includes(norm(needle))) {
        documentViewer.setCurrentPage(p, false);
        return { page: p, of: n };
      }
    }
    return { page: null, of: n };
  }, SCROLL);
  if (!found.page) return { miss: `"${SCROLL}" is on none of the ${found.of} pages`, loaded: loaded.ok };
  await page.waitForTimeout(4000);
  return { loaded: loaded.ok, scrolled: SCROLL, page: found.page, of: found.of };
}
