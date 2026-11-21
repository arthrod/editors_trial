/**
 * OnlyOffice probe for harness/ui/shot.mjs (`--probe`).
 *
 * OnlyOffice paints its pages on a canvas inside its own frame, so shot.mjs's
 * `--wait-for` / `--scroll-text` cannot read them. This probe:
 *   1. waits for window.__host.loaded (main.js): the converter has returned,
 *      the editor has reported the document ready and has paginated to its
 *      last page;
 *   2. if OO_PAGE is set, asks the editor to go to that page (its `goToPage`).
 * A document that did not open is a `miss`, with the reason the converter or
 * the editor gave; so is a page that does not exist.
 */
const PAGE = Number(process.env.OO_PAGE || 0);

export async function probe(page) {
  const r = await page.evaluate(async () => {
    const loaded = await Promise.race([
      window.__host.loaded.then((v) => ({ ok: v }), (e) => ({ err: String(e && e.message || e) })),
      new Promise((res) => setTimeout(() => res({ err: 'not loaded after 300 s' }), 300000)),
    ]);
    return { ...loaded, convertMs: window.__host.convertMs, errors: window.__host.errors };
  });
  if (r.err) {
    await page.waitForTimeout(3000); // let the editor draw its own error message, if it has one
    return { miss: `document did not open: ${r.err}`, convertMs: r.convertMs, errors: r.errors };
  }
  await page.waitForTimeout(4000);
  const out = { loaded: r.ok, convertMs: r.convertMs, totalPages: r.ok.pages };
  if (!PAGE) return out;
  if (PAGE > r.ok.pages) return { ...out, miss: `there is no page ${PAGE} (the document has ${r.ok.pages})` };
  const at = await page.evaluate(async (n) => {
    const api = window.__host.api();
    api.goToPage(n - 1);
    await new Promise((res) => setTimeout(res, 3000));
    return api.getCurrentPage() + 1;
  }, PAGE);
  if (at !== PAGE) return { ...out, miss: `the editor is on page ${at}, not ${PAGE}` };
  await page.waitForTimeout(2000);
  return { ...out, page: PAGE };
}
