/**
 * Scroll the standalone paginated HTML to a given page of the materializer's
 * page tree, so the driver can photograph that page.
 *
 * The page number comes from the DX_PAGE environment variable (1-based); the
 * driver takes the screenshot AFTER the probe runs, so the scroll is in
 * effect when the shutter opens.
 */
export async function probe(page) {
  const want = parseInt(process.env.DX_PAGE || '1', 10);

  const info = await page.evaluate((n) => {
    const boxes = Array.from(document.querySelectorAll('.page-box'));
    if (!boxes.length) {
      return { found: 0, scrolled: false };
    }
    const box = boxes[Math.min(n, boxes.length) - 1];
    box.scrollIntoView({ block: 'start', behavior: 'instant' });
    // a small offset so the page is not flush against the viewport edge
    window.scrollBy(0, -20);
    const r = box.getBoundingClientRect();
    return {
      found: boxes.length,
      scrolled: true,
      page: n,
      boxTop: Math.round(r.top),
      boxH: Math.round(r.height),
      scrollY: Math.round(window.scrollY),
    };
  }, want);

  await page.waitForTimeout(600);
  return info;
}
