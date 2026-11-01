/**
 * Apryse probe: open WebViewer's comments panel after load, by clicking the
 * toolbar's own comments button as a reader would, so the screenshot shows
 * whether the corpus's comment reached the editor. The annotation list is
 * returned too, as the evidence behind the picture.
 */
import { probe as load } from './probe.mjs';

export async function probe(page) {
  const r = await load(page);
  if (r.miss) return r;
  const after = await page.evaluate(async () => {
    const inst = window.__apryse.instance;
    await new Promise((res) => setTimeout(res, 5000));
    const list = inst.Core.annotationManager.getAnnotationsList();
    return { annotations: list.length, contents: list.map((a) => (a.getContents && a.getContents()) || '').filter(Boolean) };
  });
  const btn = page.locator('[data-element="toggleNotesButton"], button[aria-label*="omment" i]').first();
  const clicked = (await btn.count()) > 0;
  if (!clicked) return { ...r, comments: after, miss: 'no comments button found' };
  await btn.click();
  await page.waitForTimeout(3000);
  return { ...r, comments: after, panel: 'opened by clicking the comments button' };
}
