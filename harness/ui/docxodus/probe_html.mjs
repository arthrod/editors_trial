import fs from 'node:fs';
import path from 'node:path';

/**
 * Probe for the standalone paginated HTML that Docxodus itself produced
 * (`docxodus convert --to html`). This is the product's own rendered page,
 * not a host page: the HTML is the materializer's output, with the page tree
 * already fixed.
 *
 * The census is the same shape the other editors' probes use.
 */
export async function probe(page) {
  try {
    await page.waitForFunction(
      () => document.querySelectorAll('[class*="page"], .page, section').length > 0,
      undefined,
      { timeout: 60000 },
    );
  } catch (e) {
    /* report whatever is on the page */
  }

  const dom = await page.evaluate(() => {
    const counts = {
      tables: 0, tableRows: 0, tableCells: 0, svg: 0, canvas: 0,
      objects: 0, math: 0, images: 0, paragraphs: 0,
    };
    const imageInfo = [];
    document.querySelectorAll('table').forEach(() => (counts.tables += 1));
    document.querySelectorAll('tr').forEach(() => (counts.tableRows += 1));
    document.querySelectorAll('td,th').forEach(() => (counts.tableCells += 1));
    document.querySelectorAll('svg').forEach(() => (counts.svg += 1));
    document.querySelectorAll('canvas').forEach(() => (counts.canvas += 1));
    document.querySelectorAll('object,embed').forEach(() => (counts.objects += 1));
    document.querySelectorAll('math,[data-mjx],[class*="katex"],[class*="MathJax"]').forEach(() => (counts.math += 1));
    document.querySelectorAll('p').forEach(() => (counts.paragraphs += 1));
    document.querySelectorAll('img').forEach((im) => {
      counts.images += 1;
      const r = im.getBoundingClientRect();
      imageInfo.push({
        src: (im.getAttribute('src') || '').slice(0, 60),
        natural: im.naturalWidth + 'x' + im.naturalHeight,
        rendered: Math.round(r.width) + 'x' + Math.round(r.height),
        alt: (im.getAttribute('alt') || '').slice(0, 60),
      });
    });

    const txt = document.body.innerText || '';
    const has = (q) => txt.includes(q);

    // the page boxes the materializer laid out
    const pages = [];
    document.querySelectorAll('[class*="page"]').forEach((p) => {
      const r = p.getBoundingClientRect();
      if (r.width > 300 && r.height > 300) {
        pages.push({
          cls: String(p.className || '').slice(0, 70),
          w: Math.round(r.width),
          h: Math.round(r.height),
          top: Math.round(r.top + window.scrollY),
        });
      }
    });

    return {
      counts,
      imageInfo: imageInfo.slice(0, 12),
      pageBoxes: pages.slice(0, 12),
      pageBoxCount: pages.length,
      collectedChars: txt.length,
      textBoxContent: has('Text box content'),
      fallbackText: has('AlternateContent fallback text'),
      smartArtPlaceholder: has('[SMARTART]'),
      mathPlaceholder: has('[MATH]'),
      stepOne: has('Step one'),
      catA: has('Cat A'),
      series1: has('Series 1'),
      equation: /E\s*=\s*mc/.test(txt),
      hiddenText: has('hidden text'),
      commentBody: has('This is a comment body.'),
      deletedRow: has('This row was deleted'),
      insertedRow: has('This row was inserted'),
      footnoteBody: has('This is the footnote body'),
      endnoteBody: has('This is the endnote body'),
      sample: txt.slice(0, 700),
    };
  });

  return dom;
}
