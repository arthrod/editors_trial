/**
 * react-docx probe for harness/ui/shot.mjs (`--probe`).
 *
 * Waits for the viewer's own controller to report a loaded document
 * (window.__host.loaded, set by main.js) and returns what the controller says
 * about it: page count, tracked changes, comments, and whether its review
 * marks are switched on. A document that did not load is a `miss`.
 */
export async function probe(page) {
  const r = await page.evaluate(async () => {
    const loaded = await Promise.race([
      window.__host.loaded.then((v) => ({ ok: v }), (e) => ({ err: String(e && e.message || e) })),
      new Promise((res) => setTimeout(() => res({ err: 'not loaded after 90 s' }), 90000)),
    ]);
    if (loaded.err) return loaded;
    const c = window.__host.viewer.getController();
    const root = document.getElementById('viewer');
    return {
      ok: loaded.ok,
      totalPages: c.totalPages,
      trackedChanges: (c.trackedChanges || []).length,
      comments: (c.comments || []).length,
      showTrackedChanges: !!c.showTrackedChanges,
      showComments: !!c.showComments,
      dom: { img: root.querySelectorAll('img').length, svg: root.querySelectorAll('svg').length, canvas: root.querySelectorAll('canvas').length, table: root.querySelectorAll('table').length },
    };
  });
  if (r.err) return { miss: `document did not load: ${r.err}` };
  await page.waitForTimeout(1500);
  return r;
}
