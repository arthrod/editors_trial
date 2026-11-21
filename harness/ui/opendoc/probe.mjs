/**
 * OpenDoc probe for harness/ui/shot.mjs (`--probe`).
 *
 * OpenDoc's host contract (0.1.0-alpha) has no way to hand it a document: it
 * opens files from its own file input. And it paints its pages on canvases, so
 * shot.mjs's `--wait-for` / `--scroll-text` cannot read them. This probe:
 *   1. waits for the page to mark its engine ready (`html.engine-ready`; a file
 *      handed over earlier is lost) or failed (`html.engine-failed`);
 *   2. puts OPENDOC_FILE on the application's own file input (#file), as a
 *      reader choosing File > Open would, and waits for `body.doc-loaded` and
 *      the page canvases;
 *   3. if OPENDOC_PAGE is set, scrolls the application's own viewport until its
 *      status bar names that page.
 * A document that did not open, or a page that is not reached, is a `miss`.
 */
const FILE = process.env.OPENDOC_FILE || '';
const PAGE = Number(process.env.OPENDOC_PAGE || 0);

export async function probe(page) {
  if (!FILE) return { miss: 'OPENDOC_FILE is not set' };
  try {
    await page.waitForFunction(() => {
      const c = document.documentElement.classList;
      return c.contains('engine-ready') || c.contains('engine-failed');
    }, null, { timeout: 180000 });
  } catch {
    return { miss: 'the engine was neither ready nor failed after 180 s' };
  }
  if (await page.evaluate(() => document.documentElement.classList.contains('engine-failed'))) {
    return { miss: "OpenDoc's engine failed to start" };
  }
  await page.setInputFiles('#file', FILE);
  try {
    await page.waitForFunction(() => document.body.classList.contains('doc-loaded')
      && document.querySelectorAll('#pages .page-wrap canvas').length > 0, null, { timeout: 120000 });
  } catch {
    const status = await page.evaluate(() => (document.getElementById('status') || {}).textContent || '');
    return { miss: `the document did not open within 120 s (status: "${status.trim().slice(0, 200)}")` };
  }
  await page.waitForTimeout(4000);
  // The application draws only the pages near the viewport, so the page count
  // and the current page are read from its own status bar ("Page 1 of 6").
  const info = () => page.evaluate(() => {
    const m = /(\d+)\D+(\d+)/.exec((document.getElementById('statPages') || {}).textContent || '');
    const band = document.querySelector('#pages .page-band');
    return {
      currentPage: m ? Number(m[1]) : null,
      totalPages: m ? Number(m[2]) : null,
      // the pages drawn right now, as [top in the page band, width, height] in CSS pixels
      drawn: [...document.querySelectorAll('#pages .page-wrap')].map((p) => [p.offsetTop, p.offsetWidth, p.offsetHeight]),
      bandHeight: band ? band.offsetHeight : null,
      findings: ((document.querySelector('[data-import-findings], #importFindings') || {}).textContent || '').trim().slice(0, 80),
    };
  });
  let r = await info();
  if (r.totalPages == null) return { ...r, miss: 'the status bar shows no page count' };
  if (!PAGE) return r;
  if (PAGE > r.totalPages) return { ...r, miss: `there is no page ${PAGE} (the document has ${r.totalPages})` };
  // Scroll its own viewport until its status bar names the page, then put that
  // page's top at the top of the viewport.
  for (let i = 0; i < 400 && r.currentPage !== PAGE; i++) {
    await page.evaluate(() => { document.getElementById('viewport').scrollTop += 120; });
    await page.waitForTimeout(120);
    r = await info();
  }
  if (r.currentPage !== PAGE) return { ...r, miss: `scrolling never reached page ${PAGE}` };
  await page.evaluate(() => {
    const view = document.getElementById('viewport');
    const top = view.getBoundingClientRect().top;
    // the first drawn page whose top edge is below the viewport's top: the page just reached
    const wrap = [...document.querySelectorAll('#pages .page-wrap')].find((p) => p.getBoundingClientRect().top > top + 1);
    if (wrap) view.scrollTop += wrap.getBoundingClientRect().top - top - 8;
  });
  await page.waitForTimeout(4000);
  r = await info();
  if (r.currentPage !== PAGE) return { ...r, miss: `the status bar reads page ${r.currentPage}, not ${PAGE}` };
  return { ...r, page: PAGE };
}
