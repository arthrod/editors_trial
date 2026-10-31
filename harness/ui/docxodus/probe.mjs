import fs from 'node:fs';
import path from 'node:path';

/**
 * Docxodus probe: DOM construct census + package facts + the round-trip DOCX.
 *
 * The census is the same shape the other editors' probes use, so the §3
 * table in the report is read the same way for every editor: a count of the
 * element types a construct would produce. `natural` vs `rendered` on each
 * image is the discriminator for "the editor ignored the extent".
 */
export async function probe(page) {
  // wait for the product's own render to finish
  try {
    await page.waitForFunction(
      () => window.__docxodus && (window.__docxodus.rendered || window.__docxodus.error),
      undefined,
      { timeout: 120000 },
    );
  } catch (e) {
    /* fall through and report whatever is on the page */
  }

  const dom = await page.evaluate(() => {
    const s = window.__docxodus || {};

    // collect text from the light DOM, every open shadow root and every
    // same-origin iframe — the materializer lays out in a private attached
    // browsing context, so the document may live in an iframe.
    const texts = [];
    const walkRoot = (root) => {
      if (!root) return;
      texts.push(root.innerText || root.textContent || '');
      root.querySelectorAll('*').forEach((el) => {
        if (el.shadowRoot) walkRoot(el.shadowRoot);
      });
    };
    const walkFrames = (win) => {
      try {
        walkRoot(win.document);
        win.document.querySelectorAll('iframe,frame').forEach((f) => {
          if (f.contentWindow) walkFrames(f.contentWindow);
        });
      } catch (e) {
        /* cross-origin */
      }
    };
    walkFrames(window);

    // element census, across frames too
    const counts = {
      tables: 0, tableRows: 0, tableCells: 0, svg: 0, canvas: 0,
      objects: 0, math: 0, textboxEls: 0, images: 0, paragraphs: 0,
    };
    const imageInfo = [];
    const collect = (doc) => {
      if (!doc) return;
      counts.tables += doc.querySelectorAll('table').length;
      counts.tableRows += doc.querySelectorAll('tr').length;
      counts.tableCells += doc.querySelectorAll('td,th').length;
      counts.svg += doc.querySelectorAll('svg').length;
      counts.canvas += doc.querySelectorAll('canvas').length;
      counts.objects += doc.querySelectorAll('object,embed').length;
      counts.math += doc.querySelectorAll('math,[data-mjx],[class*="katex"],[class*="MathJax"]').length;
      counts.textboxEls += doc.querySelectorAll('[class*="text-box"],[class*="textbox"],[data-text-box]').length;
      counts.paragraphs += doc.querySelectorAll('p').length;
      doc.querySelectorAll('img').forEach((im) => {
        counts.images += 1;
        const r = im.getBoundingClientRect();
        imageInfo.push({
          src: (im.getAttribute('src') || '').slice(0, 90),
          natural: im.naturalWidth + 'x' + im.naturalHeight,
          rendered: Math.round(r.width) + 'x' + Math.round(r.height),
          cls: String(im.className || '').slice(0, 60),
        });
      });
    };
    const walkDocs = (win) => {
      try {
        collect(win.document);
        win.document.querySelectorAll('iframe,frame').forEach((f) => {
          if (f.contentWindow) walkDocs(f.contentWindow);
        });
      } catch (e) {
        /* cross-origin */
      }
    };
    walkDocs(window);

    const txt = texts.join('\n');
    const has = (q) => txt.includes(q);

    // page boxes the materializer produced
    const pageEls = document.querySelectorAll('[class*="page"]');
    const pageSizes = [];
    pageEls.forEach((p) => {
      const r = p.getBoundingClientRect();
      if (r.width > 100 && r.height > 100) pageSizes.push(Math.round(r.width) + 'x' + Math.round(r.height));
    });

    return {
      counts,
      imageInfo: imageInfo.slice(0, 12),
      frameCount: document.querySelectorAll('iframe,frame').length,
      pageBoxSizes: Array.from(new Set(pageSizes)).slice(0, 12),
      collectedChars: txt.length,
      textBoxContent: has('Text box content'),
      fallbackText: has('AlternateContent fallback text'),
      stepOne: has('Step one'),
      catA: has('Cat A'),
      series1: has('Series 1'),
      equation: /E\s*=\s*mc/.test(txt),
      altChunk: has('Imported altChunk'),
      hiddenText: has('hidden text'),
      commentBody: has('This is a comment body.'),
      commentAnchor: has('A sentence with a comment'),
      deletedRow: has('This row was deleted'),
      insertedRow: has('This row was inserted'),
      footnoteBody: has('This is the footnote body'),
      endnoteBody: has('This is the endnote body'),
      heading: has('Chapter 1: Heading with'),
      sample: txt.slice(0, 900),
      state: {
        wasmReady: s.wasmReady,
        rendered: s.rendered,
        error: s.error,
        pageCount: s.pageCount,
        renderMs: s.renderMs,
        sourceBytes: s.sourceBytes,
        savedBytes: s.savedBytes,
        rendererFingerprint: s.rendererFingerprint,
        warnings: s.warnings,
        mode: s.mode,
      },
      manifest: s.manifest,
      metadata: s.metadata,
      renderReport: s.renderReport,
    };
  });

  // pull the round-trip DOCX out of the page and write it next to the other
  // editors' outputs, so the namespace census and the pass-through audit can
  // run on it unchanged
  const b64 = await page.evaluate(() => (window.__docxodus && window.__docxodus.savedDocxBase64) || null);
  if (b64) {
    const outDir = '/Users/arthrod/temp/T/editors_trial/out/docxodus';
    fs.mkdirSync(outDir, { recursive: true });
    const buf = Buffer.from(b64, 'base64');
    fs.writeFileSync(path.join(outDir, 'complex.docx'), buf);
    dom.savedTo = path.join(outDir, 'complex.docx');
    dom.savedSize = buf.length;
  }

  return dom;
}
