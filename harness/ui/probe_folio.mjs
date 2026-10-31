export async function probe(page) {
  return await page.evaluate(() => {
    const txt = document.body.innerText || '';
    const sel = (s) => txt.includes(s);
    return {
      bodyTextLen: txt.length,
      hasTextBoxContent: sel('Text box content'),
      hasFallbackText: sel('AlternateContent fallback text'),
      hasStepOne: sel('Step one'),
      hasChartCategory: sel('Cat A'),
      hasChartLegend: sel('Series 1'),
      hasEquation: /E\s*=\s*mc/.test(txt),
      hasOleTitle: sel('Text box'),
      hasHebrew: /[֐-׿]/.test(txt),
      hasAltChunk: sel('Imported altChunk'),
      hasHiddenText: sel('hidden text'),
      // count rendered page sheets, whatever the app calls them
      pageishNodes: document.querySelectorAll(
        '[class*="page"],[data-page],.ProseMirror'
      ).length,
      editorHTML: (document.querySelector('.ProseMirror')?.innerText || '').slice(0, 2500),
    };
  });
}
