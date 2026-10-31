/**
 * Probe for the Docen rendering study.
 *
 * The repo's own demo page (packages/editor/document.html) mounts a
 * <docen-document> component. Its "Open" path is a hidden file input that
 * lives inside the component's shadow root:
 *
 *     <input type="file" id="file-input" accept=".docx,.md,.markdown" hidden />
 *
 * shot.mjs's --file path waits for the selector with the default
 * 'visible' state, so it never fires on a hidden input. This probe does the
 * equivalent load itself, through the component's own public API, and then
 * waits for the canvas layout to settle before the screenshot is taken.
 *
 * Env:
 *   DOCEN_FIXTURE  path to the .docx to load (default: the study fixture)
 *   DOCEN_MARKS    'off' -> drop the demo's show-marks attribute
 *                  (Word's Show/Hide ¶ off, so the rendering is comparable
 *                  to Word's page images); anything else keeps the demo
 *                  default (marks on).
 *   DOCEN_PAGE     1-based page of the canvas to scroll to before the
 *                  screenshot (the document is painted on a canvas, so the
 *                  driver's --scroll-text cannot reach it — there is no
 *                  light-DOM text for it to find).
 */
import fs from 'node:fs';

const FIXTURE =
  process.env.DOCEN_FIXTURE ||
  '/Users/arthrod/temp/T/editors_trial/fixture/complex.docx';

export async function probe(page) {
  const out = { fixture: FIXTURE, marks: process.env.DOCEN_MARKS || 'demo-default' };

  // 1. Load the corpus through the component's real file-input path.
  try {
    await page.setInputFiles('#file-input', FIXTURE);
    out.loadMethod = 'setInputFiles(#file-input)';
  } catch (e) {
    out.loadMethod = 'el.open(File) API';
    out.setInputFilesError = String(e && e.message ? e.message : e);
    const b64 = fs.readFileSync(FIXTURE).toString('base64');
    await page.evaluate(async (payload) => {
      const bin = atob(payload);
      const u8 = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      const el = document.querySelector('docen-document');
      const file = new File([u8], 'complex.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      await el.open(file);
    }, b64);
  }

  // 2. Wait until the open finished (the component stamps the filename).
  try {
    await page.waitForFunction(
      () => {
        const el = document.querySelector('docen-document');
        return !!el && el.getAttribute('filename') === 'complex.docx';
      },
      null,
      { timeout: 60000 },
    );
    out.filenameStamped = true;
  } catch (e) {
    out.filenameStamped = false;
    out.waitError = String(e && e.message ? e.message : e);
  }

  // 3. Let the canvas re-layout and paint.
  await page.waitForTimeout(12000);

  // 3b. Optional: scroll the canvas to a given page. The document is painted
  //     into a <canvas> by the LeaferJS stage, so there is no DOM text to
  //     scroll into view — the scroll container is <docen-document-area>.
  if (process.env.DOCEN_PAGE) {
    const target = Number(process.env.DOCEN_PAGE);
    out.scrolledToPage = await page.evaluate((idx) => {
      const el = document.querySelector('docen-document');
      const root = el.shadowRoot;
      const scroller = Array.from(root.querySelectorAll('*')).filter(
        (n) => n.scrollHeight > n.clientHeight + 4 && n.clientHeight > 100,
      )[0];
      if (!scroller) return null;
      const pages = root.querySelectorAll('.canvas-pages > *');
      const pageCount = pages.length;
      // Per-page pitch: distance between the page wrappers.
      const pitch = pages.length > 1
        ? pages[1].getBoundingClientRect().top - pages[0].getBoundingClientRect().top
        : scroller.scrollHeight;
      scroller.scrollTop = Math.round(pitch * (idx - 1));
      return {
        pageCount,
        scrollTop: scroller.scrollTop,
        scrollHeight: scroller.scrollHeight,
        clientHeight: scroller.clientHeight,
        scroller: scroller.tagName,
      };
    }, target);
    await page.waitForTimeout(3000);
  }

  // 3c. Optional: Word-style "no formatting marks" view. The component's
  //      setShowMarks(false) is the supported switch — dropping the attribute
  //      by hand leaves the canvas stage painting the ↵ marks. It has to be
  //      the LAST mutating step: both the load transaction and a scroll
  //      repaint the pages and restore the marks (verified by A/B capture).
  if (process.env.DOCEN_MARKS === 'off') {
    await page.evaluate(() => {
      document.querySelector('docen-document')?.setShowMarks(false);
    });
    await page.waitForTimeout(5000);
  }

  // 5. Diagnostics: what did the editor actually parse + paint?
  out.state = await page.evaluate(() => {
    const el = document.querySelector('docen-document');
    const root = el?.shadowRoot;
    const canvasEl = root?.querySelector('.docen-canvas');
    const status = root?.querySelector('docen-status-bar');
    const json = el?.getJSON?.();
    const types = {};
    const walk = (n) => {
      if (!n) return;
      if (n.type) types[n.type] = (types[n.type] || 0) + 1;
      if (Array.isArray(n.content)) n.content.forEach(walk);
    };
    walk(json);
    const text = [];
    const collect = (n) => {
      if (!n) return;
      if (n.type === 'text' && n.text) text.push(n.text);
      if (Array.isArray(n.content)) n.content.forEach(collect);
    };
    collect(json);
    return {
      filename: el?.getAttribute('filename'),
      showMarks: el?.hasAttribute('show-marks'),
      nodeTypes: types,
      textSample: text.join(' ').slice(0, 3000),
      textLength: text.join(' ').length,
      canvasCount: root ? root.querySelectorAll('canvas').length : -1,
      canvasScrollHeight: canvasEl ? canvasEl.scrollHeight : -1,
      canvasChildTags: canvasEl
        ? Array.from(canvasEl.children).map((c) => c.tagName + (c.className ? '.' + c.className : ''))
        : [],
      statusBarText: status ? (status.shadowRoot?.textContent || status.textContent || '').trim().slice(0, 400) : '',
      rootText: root ? (root.textContent || '').trim().slice(0, 600) : '',
    };
  });

  // 6. Dump the parsed model so the parse-level gaps can be checked offline.
  try {
    const json = await page.evaluate(() => document.querySelector('docen-document')?.getJSON?.());
    if (json) {
      fs.writeFileSync('/tmp/docen_parsed.json', JSON.stringify(json, null, 2));
      out.parsedModelPath = '/tmp/docen_parsed.json';
      const extras = json.attrs?.documentExtras || {};
      out.documentExtras = {
        keys: Object.keys(extras),
        footnotes: (extras.footnotes || []).length,
        endnotes: (extras.endnotes || []).length,
        comments: (extras.comments || []).length,
      };
    }
  } catch (e) {
    out.parsedModelError = String(e && e.message ? e.message : e);
  }

  return out;
}
