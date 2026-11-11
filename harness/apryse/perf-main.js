// Browser perf host for Apryse WebViewer's DOCX Editor (@pdftron/webviewer).
//
// Same product path as index.html/main.js (enableOfficeEditing, Apryse's office
// engine in WebAssembly), with what the warm/cold probe needs:
//
//   - the document comes from /corpus.docx, the route the probe fulfils with
//     its own fixture (vite.perf.config.mjs serves fixture/complex.docx there
//     so the page also opens by hand);
//   - readiness means the first page is PAINTED, not merely loaded:
//     documentLoaded + annotationsLoaded + a page canvas (canvas.hacc inside
//     the <apryse-webviewer> shadow root) with a size and ink in it + two
//     animation frames. Only then does window.__aprysePerf.state become
//     'rendered' and #ready turn green;
//   - the editable surface is WebViewer's own office editor: #pageContainer1
//     is the first page's text surface (role="region", aria-label="Page 1"),
//     a click on it places the office editor's caret and the next keystroke is
//     inserted there.
//
// One host-level workaround, measured not guessed: WebViewer 12.2.1 puts an
// EMPTY .HeaderFooterControlsOverlay (position:absolute; inset:0;
// width/height:100%; z-index:501) over every page. With pointer-events:auto it
// is the hit target for every click on the page, and pageContainer1.click()
// times out with "<div class="HeaderFooterControlsOverlay"> intercepts pointer
// events"; a real mouse click on it places no caret and typing changes nothing.
// Setting pointer-events:none on that one element gives the click back to the
// page surface (see installOverlayRule below); nothing else about
// the UI or the document changes.
//
// The license key is the trial's .env (APRYSE_API_KEY, demo:...) and never
// appears in this file or in the page's globals.
import WebViewer from '@pdftron/webviewer';

const DOC_URL = '/corpus.docx';

const perf = {
  state: 'booting',
  docUrl: DOC_URL,
  errors: [],
  paint: null,
  pageCount: null,
  marks: { bootedAt: performance.now() },
  instance: null,
  // Deterministic keyboard entry point, if a driver cannot click the page:
  // the office editor's own focus call (the one roundtrip.mjs uses).
  async focusContent() {
    const editor = perf.instance.Core.documentViewer.getDocument().getOfficeEditor();
    await editor.focusContent();
    return true;
  },
  async bodyText() {
    const editor = perf.instance.Core.documentViewer.getDocument().getOfficeEditor();
    const content = await editor.getDocumentBodyContent();
    const walk = (node, out) => {
      if (node && node._text) out.push(node._text);
      for (const child of (node && node._children) || []) walk(child, out);
      return out;
    };
    return (Array.isArray(content) ? content : [content]).flatMap((n) => walk(n, [])).join('');
  },
};
window.__aprysePerf = perf;

function viewerRoot() {
  const host = document.querySelector('#viewer apryse-webviewer');
  return host && host.shadowRoot ? host.shadowRoot : null;
}

function setState(state, detail) {
  perf.state = state;
  perf.marks[state + 'At'] = performance.now();
  const ready = document.getElementById('ready');
  if (ready) {
    ready.dataset.state = state;
    ready.textContent = detail ? state + ' — ' + detail : state;
  }
  // #viewer carries the same state, so a CSS selector can be the signal:
  //   #viewer[data-apryse-state="rendered"]
  document.getElementById('viewer').dataset.apryseState = state;
}

// See the header comment: the empty header/footer overlay is the only thing
// between a click and the page. One rule inside the shadow root is enough and
// costs nothing per frame (a MutationObserver re-applying it on every editor
// mutation would run DOM queries exactly where C06 is measured).
function installOverlayRule() {
  const root = viewerRoot();
  if (!root) return false;
  if (root.querySelector('style[data-apryse-perf-overlay]')) return true;
  const style = document.createElement('style');
  style.dataset.aprysePerfOverlay = 'header-footer-overlay';
  style.textContent = '.HeaderFooterControlsOverlay { pointer-events: none !important; }';
  root.appendChild(style);
  return true;
}

function overlayCount() {
  const root = viewerRoot();
  return root ? root.querySelectorAll('.HeaderFooterControlsOverlay').length : 0;
}

// The first page is painted when its canvas has a size and ink. WebViewer
// draws pages with a 2D context, so a pixel sample is available; if a build
// ever taints the canvas the size check alone still decides (pixelCheck says
// which one ran).
//
// Cost matters here: this loop runs while the page is loading and the probe
// times what it waits for, so the cheap DOM check runs first and pixels are
// only read once a sized page canvas exists, at most every 100 ms.
function pageCanvases() {
  const root = viewerRoot();
  if (!root) return [];
  return [...root.querySelectorAll('#pageContainer1 canvas, .pageContainer canvas')].filter(
    (c) => c.getBoundingClientRect().width >= 200,
  );
}

// Page 1 is drawn on more than one canvas (an empty .auxiliary layer and the
// .hacc page bitmap); the strongest ink reading of the sized canvases wins.
//
// Where the ink is, is not ours to assume: the perf harness's fixture is one
// w:t that opens with ~100 preserved spaces, so its only ink sits at x≈448 of
// an 816 px page — outside the top-left 400x400 corner a document usually
// starts in. Sampling that corner alone called a painted page blank, the state
// went to 'error', and the probe's ready_js never fired (a 120 s timeout that
// blamed the editor, AGENTS.md §4). So: the corner is the cheap first look,
// the whole bitmap is the second, and the detail records where the ink was.
const CORNER_PX = 400;
const FULL_SCAN_STRIDE = 2;
const FULL_SCAN_INTERVAL_MS = 400;
let lastFullScanAt = -Infinity;

function scanInk(ctx, width, height, stride) {
  const data = ctx.getImageData(0, 0, width, height).data;
  let ink = 0;
  let minX = 0;
  let minY = 0;
  let maxX = 0;
  let maxY = 0;
  for (let y = 0; y < height; y += stride) {
    for (let x = 0; x < width; x += stride) {
      const i = (y * width + x) * 4;
      if (data[i + 3] > 0 && (data[i] < 200 || data[i + 1] < 200 || data[i + 2] < 200)) {
        if (ink === 0) {
          minX = maxX = x;
          minY = maxY = y;
        } else {
          if (x < minX) minX = x;
          if (y < minY) minY = y;
          if (x > maxX) maxX = x;
          if (y > maxY) maxY = y;
        }
        ink += 1;
      }
    }
  }
  return { ink, bbox: ink > 0 ? [minX, minY, maxX, maxY] : null };
}

function pageInk() {
  const root = viewerRoot();
  const all = root ? [...root.querySelectorAll('canvas')] : [];
  const sized = pageCanvases();
  if (sized.length === 0) {
    return { canvases: all.length, sized: 0, ink: null, pixelCheck: 'no-page-canvas' };
  }
  const rect = sized[0].getBoundingClientRect();
  // The full-bitmap read is a GPU readback of the whole page; four per second
  // while loading is the seam. Between them the corner reading stands, and a 0
  // from the corner only ever means "keep polling".
  const mayScanFull = performance.now() - lastFullScanAt >= FULL_SCAN_INTERVAL_MS;
  let scannedFull = false;
  let best = { ink: null, pixelCheck: 'ok', canvas: null, bbox: null, window: null };
  for (const canvas of sized) {
    let reading = { ink: null, pixelCheck: 'ok', bbox: null, window: null };
    try {
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reading = { ink: null, pixelCheck: 'no-2d-context', bbox: null, window: null };
      } else {
        const corner = scanInk(
          ctx,
          Math.min(CORNER_PX, canvas.width),
          Math.min(CORNER_PX, canvas.height),
          1,
        );
        if (corner.ink > 0) {
          reading = { ...corner, pixelCheck: 'ok', window: 'corner' };
        } else if (mayScanFull) {
          scannedFull = true;
          reading = {
            ...scanInk(ctx, canvas.width, canvas.height, FULL_SCAN_STRIDE),
            pixelCheck: 'ok',
            window: 'full/' + FULL_SCAN_STRIDE,
          };
        } else {
          reading = { ink: 0, pixelCheck: 'ok', bbox: null, window: 'corner' };
        }
      }
    } catch (err) {
      reading = {
        ink: null,
        pixelCheck: 'getImageData failed: ' + String(err).slice(0, 80),
        bbox: null,
        window: null,
      };
    }
    if (best.ink === null || (reading.ink !== null && reading.ink > best.ink)) {
      best = { ...reading, canvas: String(canvas.className) || canvas.tagName };
    }
  }
  if (scannedFull) lastFullScanAt = performance.now();
  return {
    canvases: all.length,
    sized: sized.length,
    ink: best.ink,
    pixelCheck: best.pixelCheck,
    canvas: best.canvas,
    bbox: best.bbox,
    window: best.window,
    box: [Math.round(rect.width), Math.round(rect.height)],
  };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function painted(budgetMs) {
  const deadline = performance.now() + budgetMs;
  let last = { canvases: 0, sized: 0, ink: null, pixelCheck: 'waiting' };
  let nextPixelAt = 0;
  while (performance.now() < deadline) {
    const root = viewerRoot();
    const all = root ? root.querySelectorAll('canvas').length : 0;
    const sized = pageCanvases().length;
    last = { canvases: all, sized, ink: last.ink, pixelCheck: last.pixelCheck };
    if (sized > 0 && performance.now() >= nextPixelAt) {
      last = pageInk();
      nextPixelAt = performance.now() + 100;
      if (last.ink === null || last.ink > 0) return { ...last, timeout: false };
    }
    await sleep(50);
  }
  return { ...last, timeout: true };
}

function twoFrames() {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))));
}

WebViewer(
  {
    path: '/lib',
    licenseKey: import.meta.env.APRYSE_API_KEY,
    initialDoc: DOC_URL,
    // The DOCX Editor: opened for editing in the browser by Apryse's own
    // office engine, exactly as the round-trip host does it.
    enableOfficeEditing: true,
    enableFilePicker: true,
    extension: 'docx',
    filename: 'corpus.docx',
  },
  document.getElementById('viewer'),
).then(async (instance) => {
  perf.instance = instance;
  setState('instance');
  installOverlayRule();
  const { documentViewer } = instance.Core;

  instance.UI.addEventListener(instance.UI.Events.LOAD_ERROR, (e) => {
    perf.errors.push(String(e.detail));
    setState('error', String(e.detail));
  });

  documentViewer.addEventListener('documentLoaded', async () => {
    perf.marks.loadedAt = performance.now();
    try {
      await documentViewer.getAnnotationsLoadedPromise();
      // No officeEditor.documentCompletePromise wait here: for a one-page
      // fixture it is still pending long after the page is painted, and the
      // painted-page check below is the stronger signal anyway.
      installOverlayRule();
      const paint = await painted(60000);
      await twoFrames();
      perf.paint = paint;
      perf.marks.paintedAt = performance.now();
      perf.pageCount = documentViewer.getDocument().getPageCount();
      perf.overlaysNeutralised = overlayCount();
      if (paint.sized > 0 && (paint.ink === null || paint.ink > 0)) {
        setState('rendered', 'pages=' + perf.pageCount + ' ink=' + paint.ink + ' canvases=' + paint.canvases);
      } else {
        setState('error', 'page 1 not painted: ' + JSON.stringify(paint));
      }
    } catch (err) {
      perf.errors.push(String(err && err.stack ? err.stack : err));
      setState('error', String(err));
    }
  });
}).catch((err) => {
  perf.errors.push(String(err && err.stack ? err.stack : err));
  setState('error', String(err));
});
