/**
 * Nutrient Web SDK probe for harness/ui/shot.mjs (`--probe`).
 *
 * Nutrient shows the PDF it made from the .docx inside its own shadow root, so
 * shot.mjs's `--wait-for` / `--scroll-text` cannot read it. This probe:
 *   1. waits for window.__host.loaded (main.js): the engine has been fetched,
 *      the .docx converted and the first page shown;
 *   2. if NUTRIENT_SCROLL is set, reads each page's text lines through the
 *      SDK's own API and goes to the first page that contains it.
 * A document that did not load, or a target on no page, is a `miss`.
 */
const SCROLL = process.env.NUTRIENT_SCROLL || '';

export async function probe(page) {
  const loaded = await page.evaluate(async () => Promise.race([
    window.__host.loaded.then((v) => ({ ok: v }), (e) => ({ err: String(e && e.message || e) })),
    new Promise((res) => setTimeout(() => res({ err: 'not loaded after 300 s' }), 300000)),
  ]));
  if (loaded.err) return { miss: `document did not load: ${loaded.err}` };
  await page.waitForTimeout(5000);
  const sizes = await page.evaluate(() => {
    const inst = window.__host.instance;
    // each page's size in PDF points (a landscape page is wider than tall)
    return Array.from({ length: inst.totalPageCount }, (_, i) => { const p = inst.pageInfoForIndex(i); return [Math.round(p.width), Math.round(p.height)]; });
  });
  const out = { loaded: loaded.ok, pages: sizes };
  if (!SCROLL) return out;

  const found = await page.evaluate(async (needle) => {
    const inst = window.__host.instance;
    const norm = (s) => s.replace(/\s+/g, ' ').toLowerCase();
    for (let i = 0; i < inst.totalPageCount; i++) {
      const lines = await inst.textLinesForPageIndex(i);
      const text = lines.map((l) => l.contents).join(' ');
      if (norm(text).includes(norm(needle))) {
        inst.setViewState((v) => v.set('currentPageIndex', i));
        return i + 1;
      }
    }
    return null;
  }, SCROLL);
  if (!found) return { ...out, miss: `"${SCROLL}" is on none of the ${sizes.length} pages` };
  await page.waitForTimeout(5000);
  return { ...out, scrolled: SCROLL, page: found };
}
