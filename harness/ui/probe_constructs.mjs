export async function probe(page) {
  return await page.evaluate(() => {
    // Collect text from the light DOM, every open shadow root, AND every
    // same-origin iframe. Editors mount the document in all three places
    // depending on their architecture, and document.body.innerText sees
    // none of them.
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
      } catch { /* cross-origin: not reachable */ }
    };
    walkFrames(window);

    const txt = texts.join('\n');
    const has = (s) => txt.includes(s);
    return {
      collectedChars: txt.length,
      frameCount: document.querySelectorAll('iframe,frame').length,
      textBoxContent: has('Text box content'),
      fallbackText: has('AlternateContent fallback text'),
      stepOne: has('Step one'),
      catA: has('Cat A'),
      series1: has('Series 1'),
      equation: /E\s*=\s*mc/.test(txt),
      altChunk: has('Imported altChunk'),
      hiddenText: has('hidden text'),
      commentBody: has('This is a comment body.'),
      deletedRow: has('This row was deleted'),
      insertedRow: has('This row was inserted'),
      footnoteBody: has('This is the footnote body'),
      endnoteBody: has('This is the endnote body'),
      oleImage: !!document.querySelector('img[src^="blob:"]'),
      canvasCount: document.querySelectorAll('canvas').length,
      sample: txt.slice(0, 600),
    };
  });
}
