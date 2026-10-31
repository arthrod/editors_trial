export async function probe(page) {
  // Scroll the editor's own scroll container. Several editors render text
  // as CSS-generated content or into a canvas, so the only reliable way to
  // reach a later page is to scroll the container the app itself scrolls.
  const frac = Number(process.env.SCROLL_FRAC || 0);
  const px = Number(process.env.SCROLL_PX || 0);
  const info = await page.evaluate(({ frac, px }) => {
    const cands = Array.from(document.querySelectorAll('*')).filter((el) => {
      if (el.scrollHeight - el.clientHeight < 200) return false;
      const s = getComputedStyle(el);
      return /auto|scroll/.test(s.overflowY) && el.clientHeight > 200;
    });
    if (!cands.length) return { scrolled: false, reason: 'no scrollable container' };
    cands.sort((a, b) => b.scrollHeight - a.scrollHeight);
    const el = cands[0];
    const before = el.scrollTop;
    el.scrollTop = px > 0 ? px : Math.round((el.scrollHeight - el.clientHeight) * frac);
    el.dispatchEvent(new Event('scroll', { bubbles: true }));
    return {
      scrolled: true,
      tag: el.tagName,
      cls: String(el.className).slice(0, 60),
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      scrollTop: el.scrollTop,
      from: before,
      containerCount: cands.length,
    };
  }, { frac, px });
  await page.waitForTimeout(2500);
  return info;
}
