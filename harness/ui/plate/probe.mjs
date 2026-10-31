/**
 * Probe the running Plate editor: what nodes did the DOCX importer produce,
 * and what did the import report as lost?
 */
export async function probe(page) {
  // expand the import diagnostics panel
  await page.evaluate(() => {
    const details = document.querySelector('details.app-details');

    if (details) details.open = true;
  });

  const diagnostics = await page.evaluate(() => {
    const pre = document.querySelector('details.app-details pre');

    return pre ? pre.textContent : '';
  });

  const status = await page.evaluate(() => {
    const el = document.querySelector('.status');

    return el ? el.textContent : '';
  });

  const nodes = await page.evaluate(() => {
    const root = document.querySelector('.doc-content');

    if (!root) return [];

    const out = [];
    const walk = (el, depth) => {
      for (const child of el.children) {
        const tag = child.tagName.toLowerCase();
        const type = child.getAttribute('data-editor-node-type') || '';
        const text = (child.innerText || '').slice(0, 60);
        out.push({
          depth,
          tag,
          type,
          text,
          cls: child.className || '',
        });
        walk(child, depth + 1);
      }
    };

    walk(root, 0);

    return out;
  });

  const imgs = await page.evaluate(() =>
    Array.from(document.querySelectorAll('.doc-content img')).map((i) => ({
      alt: i.getAttribute('alt'),
      src: (i.getAttribute('src') || '').slice(0, 80),
      w: i.getBoundingClientRect().width,
      h: i.getBoundingClientRect().height,
    }))
  );

  const svgs = await page.evaluate(() => document.querySelectorAll('.doc-content svg').length);
  const canvases = await page.evaluate(() => document.querySelectorAll('.doc-content canvas').length);
  const text = await page.evaluate(() => {
    const root = document.querySelector('.doc-content');

    return root ? root.innerText : '';
  });

  return { status, diagnostics, imgs, svgs, canvases, text, nodes };
}
