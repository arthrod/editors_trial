/**
 * Document-structure probes for C11 (initial layout/pagination), C12
 * (incremental reflow), C14 (large-document scaling) and C15 (search/replace)
 * on published-package browser hosts.
 *
 * One invocation measures one sample against one already-running host. The
 * Python driver (perf/runner/benchmark_document.py) starts and stops each host
 * and decides how many samples a cell gets.
 *
 * Clocks. One page clock (`performance.now` + `performance.timeOrigin`) and the
 * B1c screencast witness. A shell paint is not the document.
 *   load    C11 is the first acked screencast frame at or after the disclosed
 *           document element (its own rect: inside the shadow root for a
 *           shadow host, never the host box or toolbar text; a non-blank
 *           canvas samples the page, not the top-left margin). The
 *           screencast_ink signal marks usable when the region has persistent
 *           ink matching one settled screenshot (min 64 non-mode pixels,
 *           four CSS pixel inset, at most 0.5% differing pixels). FCP is recorded
 *           beside that frame and is not the sample. The witness window is
 *           500 ms. No forced repaint.
 *   reflow  input (Enter at the document start, page clock) to the acked
 *           frame at or after the anchor reflow, not the first input paint.
 *           Layout reads stay outside the observation window; forced_layout_ms
 *           is 0. Page.startScreencast frames are acked via the witness
 *           recorder (Page.screencastFrame). frame_source: 'cdp_screencast'.
 *   scale   usable on an animation frame, then the next acked frame that
 *           differs after the document has settled. No post-load damage is
 *           measured as the document-surface time and recorded as no damage
 *           followed. A 1 px outline outside the document is mechanism
 *           forced_repaint and is not itself the sample. The witness window
 *           is 500 ms.
 *   find    the editor's own find widget. Completion and first-match are the
 *           full query's count text, tagged by the input value when that
 *           reply was scheduled. A prefix reply never completes it. No widget
 *           is not_applicable with a reason. cap_ms is null.
 *
 * Usage (from repo root, with a dev server already listening):
 *   node perf/runner/document_probe.mjs --mode load \
 *     --url http://127.0.0.1:5208/ --corpus /abs/fixture.docx \
 *     --corpus-route /corpus.docx --doc-selector ".doc-paragraph" \
 *     --page-model continuous_flow --ready-selector ".status-ok"
 */
import fs from 'node:fs';
import zlib from 'node:zlib';

import {
  DEFAULT_CHANNEL_TOLERANCE,
  DEFAULT_WINDOW_MS,
  decodePng,
  convertFrameToPageMs,
  frameAckSettled,
  frameInterval,
  pageClock,
  detectTimestampKind,
  diffRatio,
  getRecorder,
  injectCaretMask,
  loadPlaywright,
  stopRecorder,
  WEBGL_UNMASK_FLAG,
  witnessFrame,
} from './witness.mjs';
import { normalizeDocumentText } from './document_text_normalize.mjs';
import { openingContentVerdict } from './perf_model_text.mjs';
import { hasDocumentTextSurface, readAndGateDocumentText } from './edit_surface.mjs';
import { startChromeTrace, stopChromeTrace } from './chrome_trace.mjs';
import {
  C12_NO_PARAGRAPH_GEOMETRY,
  LIST_MODEL_PARAGRAPHS,
  PICK_ANCHOR_BELOW,
  ANCHOR_REFIND_CONTEXT_OK,
  ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC,
  REFIND_ANCHOR,
  REFIND_ANCHOR_PAGE_SRC,
  C12_BLOCK_ENTRIES_PAGE_SRC,
  C12_BLOCK_TEXT,
  C12_IDENTITY_DIAGNOSTIC_PAGE_SRC,
  ensureReflowCaret,
  gatherReflowBefore,
  placeC12BodyCaret,
  prepareLaneCaret,
  reflowBlockSelector,
  reflowWitnessSelector,
  waitForC12CaretEdit,
} from './lane_edit_burst.mjs';
import { EDIT_SURFACES } from './edit_surface.mjs';
import { loadTimeoutMs } from './load_timeout.mjs';

/** Screencast ink needs at least this many region pixels above the witness threshold. */
const SCREENCAST_INK_MIN_PIXELS = 64;

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (!a.startsWith('--')) continue;
  const key = a.slice(2);
  const next = argv[i + 1];
  if (next === undefined || next.startsWith('--')) {
    opt[key] = true;
  } else {
    opt[key] = next;
    i++;
  }
}

const MODES = new Set(['load', 'reflow', 'scale', 'find']);
const mode = opt.mode;
if (!MODES.has(mode)) {
  console.error('document_probe: --mode must be one of load|reflow|scale|find');
  process.exit(2);
}
const url = opt.url;
const corpusFile = opt.corpus;
const corpusRoute = opt['corpus-route'] || '/corpus.docx';
const readySelector = opt['ready-selector'] || '';
const readyJs = opt['ready-js'] || '';
const waitAfterReadyMs = Number(opt['wait-after-ready'] || 0);
const docSelector = opt['doc-selector'] || '';
const documentSelector = opt['document-selector'] || '';
const pageSelector = opt['page-selector'] || '';
const pageModel = opt['page-model'] || (pageSelector ? 'page' : 'continuous_flow');
const editSelector = opt['edit-selector'] || docSelector;
const editorId = typeof opt.editor === 'string' ? opt.editor : '';
const settleMs = Number(opt['settle-ms'] || 0);
const timeoutMs = Number(opt['timeout-ms'] || loadTimeoutMs());
const anchorIndex = Number(opt['anchor-index'] || 1);
const minTextChars = Number(opt['min-text-chars'] || 8);
const findInputSelector = opt['find-input-selector'] || '';
const findCountSelector = opt['find-count-selector'] || '';
const findMatchSelector = opt['find-match-selector'] || '';
const findQuery = opt['find-query'] || '';
const findExpected = opt['find-expected-matches'] ? Number(opt['find-expected-matches']) : null;
const findShortcuts = (opt['find-shortcuts'] || 'Control+f,Meta+f').split(',').map((s) => s.trim()).filter(Boolean);
const SIGNAL_INPUTS = new Set(['dom_text', 'canvas_pixel', 'shadow_text', 'screencast_ink']);
const usableSignal = opt['usable-signal'] || 'dom_text';
const screencastInkMinPixels = Number(opt['screencast-ink-min-pixels'] || SCREENCAST_INK_MIN_PIXELS);
const expectedClosingSentinel =
  typeof opt['expected-closing-sentinel'] === 'string' ? opt['expected-closing-sentinel'] : '';
const fixtureTextChars = Number(opt['fixture-text-chars'] || 0);
const lengthCheckMode = typeof opt['length-check-mode'] === 'string' ? opt['length-check-mode'] : null;
// r3lanes4 ruling 5b: the fixture body the way the input lane passes it
// (PERF_EXPECTED_BODY_PATH). Used by the virtualized mounted-text check on
// prose workloads; complex-corpus passes no body (coarse mode ignores it).
const expectedBodyText = (() => {
  const path = process.env.PERF_EXPECTED_BODY_PATH;
  if (typeof path === 'string' && path && fs.existsSync(path)) {
    try {
      return fs.readFileSync(path, 'utf8');
    } catch {
      return null;
    }
  }
  return null;
})();
const errorJs = typeof opt['error-js'] === 'string' ? opt['error-js'] : '';
if (!SIGNAL_INPUTS.has(usableSignal)) {
  console.error('document_probe: --usable-signal must be dom_text|canvas_pixel|shadow_text|screencast_ink');
  process.exit(2);
}
const SIGNAL_NAME = {
  dom_text: 'dom_text',
  canvas_pixel: 'canvas_pixel_non_blank',
  shadow_text: 'open_shadow_root_text',
  screencast_ink: 'screencast_ink',
};
function crc32(data) {
  let c = ~0;
  for (const byte of data) {
    c ^= byte;
    for (let bit = 0; bit < 8; bit++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return ~c >>> 0;
}

function pngChunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  const body = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body), 0);
  return Buffer.concat([length, body, crc]);
}

// A 1x1 PNG used only when no pre-surface screencast frame exists, so the
// first frame at or after the document surface still has a baseline to differ
// from. It is not a document pixel and it is not a forced repaint.
function tinyBaselinePng() {
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.from([0, 0, 0, 1, 0, 0, 0, 1, 8, 2, 0, 0, 0]);
  const raw = zlib.deflateSync(Buffer.from([0, 255, 0, 0]));
  return Buffer.concat([
    signature,
    pngChunk('IHDR', ihdr),
    pngChunk('IDAT', raw),
    pngChunk('IEND', Buffer.alloc(0)),
  ]).toString('base64');
}

const TINY_BASELINE_PNG = tinyBaselinePng();

if (!url || !corpusFile) {
  console.error('document_probe: --url and --corpus are required');
  process.exit(2);
}
if (!docSelector && mode !== 'find') {
  console.error('document_probe: --doc-selector is required for mode ' + mode);
  process.exit(2);
}

const corpusBytes = fs.readFileSync(corpusFile);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function decodeRecorderFrame(recorder, frame) {
  const cached = recorder.decoded.get(frame.seq);
  if (cached !== undefined) return cached;
  let decoded = null;
  try {
    decoded = decodePng(Buffer.from(frame.data, 'base64'));
  } catch {
    decoded = null;
  }
  recorder.decoded.set(frame.seq, decoded);
  return decoded;
}

async function resolveInkRegionDevice(page, frameDecoded) {
  const rect = await page
    .evaluate(() => {
      const fn = window.__docProbeSurface;
      if (typeof fn !== 'function') return null;
      const surface = fn('screencast_ink');
      return surface && surface.rect ? surface.rect : null;
    })
    .catch(() => null);
  if (!rect || !(rect.width > 0) || !(rect.height > 0)) return { scoped: false, rect_device: null, error: 'no region rect' };
  const dpr = await page.evaluate(() => window.devicePixelRatio || 1).catch(() => 1);
  let device = {
    x: Math.round(rect.x * dpr),
    y: Math.round(rect.y * dpr),
    width: Math.round(rect.width * dpr),
    height: Math.round(rect.height * dpr),
  };
  if (frameDecoded) {
    const x0 = Math.max(0, device.x);
    const y0 = Math.max(0, device.y);
    const x1 = Math.min(frameDecoded.width, device.x + device.width);
    const y1 = Math.min(frameDecoded.height, device.y + device.height);
    device = { x: x0, y: y0, width: Math.max(0, x1 - x0), height: Math.max(0, y1 - y0) };
  }
  if (device.width < 1 || device.height < 1) {
    return { scoped: false, rect_device: device, error: 'empty region in frame' };
  }
  return { scoped: true, rect_device: device, rect_css: rect, dpr, error: null };
}

/** Crop in device pixels; inset excludes four CSS pixels of border/chrome. */
function cropInkRegion(decoded, region, inset = 0) {
  if (!decoded) return null;
  const x = Math.max(0, Math.round(region.x + inset));
  const y = Math.max(0, Math.round(region.y + inset));
  const right = Math.min(decoded.width, Math.round(region.x + region.width - inset));
  const bottom = Math.min(decoded.height, Math.round(region.y + region.height - inset));
  const width = right - x, height = bottom - y;
  if (width <= 0 || height <= 0) return null;
  const data = Buffer.alloc(width * height * 4);
  for (let row = 0; row < height; row++) {
    data.set(decoded.data.subarray(
      ((y + row) * decoded.width + x) * 4,
      ((y + row) * decoded.width + right) * 4), row * width * 4);
  }
  return { width, height, data };
}

/** Ink is variation from the dominant RGBA colour, never a solid fill. */
function settledInkPixels(decoded) {
  if (!decoded) return 0;
  const counts = new Map();
  let mode = 0, highest = 0;
  for (let i = 0; i < decoded.data.length; i += 4) {
    const colour = decoded.data.readUInt32BE(i);
    const count = (counts.get(colour) || 0) + 1;
    counts.set(colour, count);
    if (count > highest) { highest = count; mode = colour; }
  }
  const channels = [mode >>> 24, (mode >>> 16) & 255, (mode >>> 8) & 255, mode & 255];
  let ink = 0;
  for (let i = 0; i < decoded.data.length; i += 4) {
    if (channels.some((value, c) => Math.abs(value - decoded.data[i + c]) > DEFAULT_CHANNEL_TOLERANCE)) ink++;
  }
  return ink;
}

// Pixel equality tolerance: at most 0.5% of inset pixels may differ by >8
// channel levels. A candidate must match every subsequent acked frame.
const SETTLED_MATCH_TOLERANCE = 0.005;
function matchesSettled(frame, reference) {
  if (!frame || !reference) return false;
  const diff = diffRatio(frame, reference, { channelTolerance: DEFAULT_CHANNEL_TOLERANCE });
  return diff.comparable && diff.ratio <= SETTLED_MATCH_TOLERANCE;
}

async function waitForScreencastInk(page, recorder) {
  await injectCaretMask(page);
  await page.waitForLoadState('load', { timeout: timeoutMs });
  const clock = await pageClock(page);
  const kind = detectTimestampKind(recorder.frames[0] || {});
  const pageTime = (frame) => {
    const frameKind = detectTimestampKind(frame);
    return convertFrameToPageMs(frame, {
      ...clock, timestamp_kind: frameKind.kind === 'unknown' ? kind.kind : frameKind.kind,
    });
  };
  const refused = (reason) => ({ at_ms: null, signal: SIGNAL_NAME.screencast_ink,
    baseline: null, ink_frame: null, reason });
  const scope = await resolveInkRegionDevice(page, null);
  if (!scope.scoped) return refused('document_region_missing');
  if (scope.dpr !== 1) return refused('unsupported_device_scale');
  const inset = 4 * scope.dpr;
  const deadline = Date.now() + timeoutMs;
  // A blank initial frame is not load completion. Wait for potential ink,
  // then 500ms without a document-region change, ignoring animated chrome.
  let potentialInk = false;
  let checked = 0;
  let previousCrop = null;
  let lastObserved = null;
  let quietSince = Date.now();
  while (Date.now() < deadline) {
    const available = recorder.frames.length;
    for (; checked < available; checked++) {
      const frame = recorder.frames[checked];
      const ms = pageTime(frame);
      if ((ms !== null && ms < 0) || (await frameAckSettled(frame)) !== 'acked') continue;
      const crop = cropInkRegion(decodeRecorderFrame(recorder, frame), scope.rect_device, inset);
      // Earlier ink starts the quiet wait; only the settled reference can qualify.
      if (settledInkPixels(crop) >= screencastInkMinPixels) {
        potentialInk = true;
      }
      if (!matchesSettled(crop, previousCrop)) quietSince = Date.now();
      previousCrop = crop;
      lastObserved = frame;
    }
    // Drain CDP events after synchronous PNG work. Time spent blocking the
    // event loop is not evidence that the compositor stopped sending frames.
    await sleep(8);
    if (checked < recorder.frames.length) continue;
    if (potentialInk && lastObserved && Date.now() - quietSince >= 500) break;
  }
  if (!lastObserved || Date.now() - quietSince < 500) return refused('settled_frame_not_observed');
  // Exactly one settled capture. CDP clips use CSS coordinates; PNG pixels
  // are device pixels (scale=1 and the page's deviceScaleFactor).
  // Freeze the observation at capture initiation. A clipped screenshot may
  // itself emit a resized screencast frame; that is capture machinery, not
  // a document paint preceding the settled reference.
  const frames = recorder.frames.slice();
  const shot = await recorder.cdp.send('Page.captureScreenshot', {
    format: 'png', clip: { ...scope.rect_css, scale: 1 }, captureBeyondViewport: false,
  });
  const decoded = decodePng(Buffer.from(shot.data, 'base64'));
  const reference = cropInkRegion(decoded, { x: 0, y: 0, width: decoded.width, height: decoded.height }, inset);
  if (settledInkPixels(reference) < screencastInkMinPixels) return refused('document_surface_absent');
  // Scan backwards: only the final uninterrupted matching suffix qualifies.
  let candidate = null;
  for (let i = frames.length - 1; i >= 0; i--) {
    const frame = frames[i];
    if ((await frameAckSettled(frame)) !== 'acked') continue;
    const ms = pageTime(frame);
    if (ms !== null && ms < 0) continue;
    const crop = cropInkRegion(decodeRecorderFrame(recorder, frame), scope.rect_device, inset);
    if (!matchesSettled(crop, reference)) break;
    if (ms !== null) candidate = { frame, ms, index: i };
  }
  if (!candidate) return refused('settled_frame_not_observed');
  let baseline = null;
  for (let i = candidate.index - 1; i >= 0; i--) {
    const frame = frames[i];
    const ms = pageTime(frame);
    if (ms !== null && ms >= 0 && (await frameAckSettled(frame)) === 'acked') { baseline = frame; break; }
  }
  await page.evaluate((atMs) => {
    const state = window.__docProbeState;
    if (state && state.docTextAt === null && typeof atMs === 'number') {
      state.docTextAt = atMs;
      state.docTextCharsAt = 1;
    }
  }, candidate.ms);
  return { at_ms: candidate.ms, signal: SIGNAL_NAME.screencast_ink,
    baseline, ink_frame: candidate.frame, reason: null };
}

async function routeCorpus(context) {
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === corpusRoute) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: corpusBytes,
      });
      return;
    }
    await route.continue();
  });
}

async function waitForReady(page) {
  const t0 = Date.now();
  const deadline = t0 + timeoutMs;
  if (readyJs || errorJs) {
    await page.waitForFunction(
      ({ expr, errExpr }) => {
        const run = (code) => {
          try {
            // eslint-disable-next-line no-eval
            return eval(code);
          } catch {
            return undefined;
          }
        };
        if (errExpr) {
          const error = run(errExpr);
          if (error) throw new Error(`editor_load_failed: ${String(error).slice(0, 400)}`);
        }
        const editorError = window.__DOCX_ERROR__;
        if (typeof editorError === 'string' && editorError) {
          throw new Error(`editor_load_failed: ${editorError}`);
        }
        if (!expr) return true;
        try {
          return Boolean(eval(expr));
        } catch {
          return false;
        }
      },
      { expr: readyJs || '', errExpr: errorJs || '' },
      { timeout: timeoutMs },
    );
  } else if (readySelector) {
    await page.waitForSelector(readySelector, { timeout: timeoutMs, state: 'visible' });
  }
  if (waitAfterReadyMs > 0 && Date.now() < deadline) {
    await page.waitForTimeout(waitAfterReadyMs);
  }
  return Date.now() - t0;
}

/** Paint entries, read once after the page is usable. */
async function paintEntries(page) {
  return page.evaluate(() => performance.getEntriesByType('paint').map((e) => ({ name: e.name, start_ms: e.startTime })));
}

function fcpFrom(paints) {
  const row = (paints || []).find((p) => p.name === 'first-contentful-paint');
  return row ? Number(row.start_ms) : null;
}

/**
 * In-page observation, installed before navigation. The usable instant is
 * performance.now() inside the animation frame where the disclosed signal
 * becomes true. textContent does not pierce an open shadow root and does not
 * see canvas pixels; those signals are checked on purpose.
 */
const INIT_SCRIPT = ({ docSel, pageSel, minTextChars: minChars, signal, documentSelector: documentSel, textWaitBudgetMs }) => {
  const recorded =
    signal === 'canvas_pixel'
      ? 'canvas_pixel_non_blank'
      : signal === 'shadow_text'
        ? 'open_shadow_root_text'
        : signal === 'screencast_ink'
          ? 'screencast_ink'
          : 'dom_text';
  const state = (window.__docProbeState = {
    firstElementAt: null,
    firstElementInfo: null,
    pageCountAtFirst: null,
    docTextAt: null,
    docTextCharsAt: null,
    usableSignal: recorded,
  });
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (!(r.width > 0 && r.height > 0)) return null;
    return { text: (el.textContent || '').trim().slice(0, 40), width: Math.round(r.width), height: Math.round(r.height) };
  };
  // visibility:hidden / display:none / opacity:0 text is not paint. A shadow
  // root's <style> or <script> source is not document text either.
  const paintedBox = (el) => {
    if (!el || el.nodeType !== 1) return null;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse') return null;
    const opacity = Number.parseFloat(style.opacity);
    if (Number.isFinite(opacity) && opacity === 0) return null;
    const r = el.getBoundingClientRect();
    if (!(r.width > 0 && r.height > 0)) return null;
    return r;
  };
  const isChrome = (el) => {
    if (!el || el.nodeType !== 1) return false;
    const tag = el.tagName;
    if (tag === 'BUTTON' || tag === 'NAV' || tag === 'MENU') return true;
    const role = (el.getAttribute('role') || '').toLowerCase();
    return role === 'toolbar' || role === 'menu' || role === 'menubar' || role === 'menuitem';
  };
  // Text of one element. Toolbar, button and menu labels are not document text.
  // Style and script source are not either. Hidden boxes are not paint.
  const elementText = (el, region = null) => {
    if (!paintedBox(el) || isChrome(el)) return '';
    const excluded = (node) => {
      for (let parent = node; parent; parent = parent.parentElement || parent.getRootNode()?.host) {
        // aria-hidden on a painted page is the editor's accessibility split
        // (folio .paged-editor__pages, superdoc .superdoc-fragment), not unpainted text.
        if (['STYLE', 'SCRIPT', 'NOSCRIPT', 'TEXTAREA', 'INPUT', 'SELECT'].includes(parent.tagName)
            || isChrome(parent)) return true;
      }
      return false;
    };
    if (excluded(el)) return '';
    if (el.tagName === 'IFRAME') {
      // Frame body coordinates are local to the visible frame viewport.
      try { return el.contentDocument?.body ? elementText(el.contentDocument.body,
        { left: 0, top: 0, right: el.clientWidth, bottom: el.clientHeight }) : ''; }
      catch { return ''; }
    }
    const bounds = region || el.getBoundingClientRect();
    const view = el.ownerDocument.defaultView;
    const intersects = (r) => r.width > 0 && r.height > 0
      && r.right > Math.max(0, bounds.left) && r.left < Math.min(view.innerWidth, bounds.right)
      && r.bottom > Math.max(0, bounds.top) && r.top < Math.min(view.innerHeight, bounds.bottom);
    const parts = [];
    const walk = (node) => {
      if (!node) return;
      if (node.nodeType === 3) {
        const parent = node.parentElement;
        if (!parent || excluded(parent)
            || !parent.checkVisibility({ opacityProperty: true, visibilityProperty: true })
            || !Array.from(parent.getClientRects()).some(intersects)) return;
        const chunk = (node.textContent || '').replace(/\s+/g, ' ').trim();
        if (chunk) parts.push(chunk);
        return;
      }
      if (node.nodeType !== 1 || excluded(node)) return;
      for (const child of node.childNodes) walk(child);
    };
    walk(el);
    return parts.join(' ').replace(/\s+/g, ' ').trim();
  };
  const canvasDrawnEl = (el) => {
    if (typeof HTMLCanvasElement === 'undefined' || !(el instanceof HTMLCanvasElement)) return false;
    let g = null;
    try {
      g = el.getContext('2d');
    } catch {
      g = null;
    }
    if (!g || typeof g.getImageData !== 'function') return false;
    const w = el.width || 0;
    const h = el.height || 0;
    if (w < 1 || h < 1) return false;
    let data = null;
    try {
      data = g.getImageData(0, 0, w, h).data;
    } catch {
      return false;
    }
    // Full canvas decode: sparse ink on large page canvases must not be missed.
    for (let y = 0; y < h; y++) {
      const row = y * w;
      for (let x = 0; x < w; x++) {
        const i = (row + x) * 4;
        const r = data[i];
        const gc = data[i + 1];
        const b = data[i + 2];
        const a = data[i + 3];
        if (a > 16 && (r < 250 || gc < 250 || b < 250)) return true;
      }
    }
    return false;
  };
  // The witness paints an 8x8 square at (0,0). A region that contains it would
  // report that square as document paint, and #doc often starts at (0,0).
  const excludeMarker = (rect) => {
    if (!rect) return null;
    const marker = 8;
    let x = rect.x;
    let y = rect.y;
    let width = rect.width;
    let height = rect.height;
    const right = x + width;
    const bottom = y + height;
    if (!(x < marker && y < marker && right > 0 && bottom > 0)) return { x, y, width, height };
    if (bottom > marker) {
      y = Math.max(y, marker);
      height = bottom - y;
    }
    const rightAfter = x + width;
    if (x < marker && y < marker && rightAfter > marker) {
      x = marker;
      width = rightAfter - x;
    }
    if (!(width > 0 && height > 0)) return null;
    return { x, y, width, height };
  };
  const selectorFor = (which) => {
    if (documentSel) return documentSel;
    if (which === 'shadow_text') return '';
    return docSel;
  };
  window.__docProbeSurface = (which) => {
    const selector = selectorFor(which);
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    let n = 0;
    const add = (r) => {
      if (!r) return;
      minX = Math.min(minX, r.left);
      minY = Math.min(minY, r.top);
      maxX = Math.max(maxX, r.right);
      maxY = Math.max(maxY, r.bottom);
      n += 1;
    };
    const chunks = [];
    const contentChunks = [];
    let canvasPresent = false;
    const take = (el, text) => {
      canvasPresent ||= el.tagName === 'CANVAS' || Boolean(el.querySelector('canvas'));
      contentChunks.push(elementText(el));
      if (!text) return;
      chunks.push(text);
      // The document element's own rect. Never the shadow host's box.
      add(paintedBox(el));
    };
    if (which === 'screencast_ink') {
      if (docSel && selector && docSel !== selector) {
        const hosts = Array.from(document.querySelectorAll(docSel));
        for (const host of hosts) {
          const root = host && host.shadowRoot;
          if (root && typeof root.querySelector === 'function') {
            const el = root.querySelector(selector);
            if (el) take(el, 'region');
            continue;
          }
          const el = document.querySelector(selector);
          if (el) take(el, 'region');
        }
      } else {
        const nodes = selector ? Array.from(document.querySelectorAll(selector)) : [];
        for (const el of nodes) take(el, 'region');
      }
    } else if (which === 'shadow_text') {
      const hosts = docSel ? Array.from(document.querySelectorAll(docSel)) : [];
      for (const host of hosts) {
        const root = host && host.shadowRoot;
        if (!root || !selector || typeof root.querySelectorAll !== 'function') continue;
        for (const el of root.querySelectorAll(selector)) take(el, elementText(el));
      }
    } else {
      const nodes = selector ? Array.from(document.querySelectorAll(selector)) : [];
      if (which === 'canvas_pixel') {
        for (const el of nodes) {
          if (!canvasDrawnEl(el)) continue;
          take(el, 'drawn');
        }
      } else {
        for (const el of nodes) take(el, elementText(el));
      }
    }
    // Opening headings sit outside paragraph selectors (plate h1.editor-heading,
    // docxodus h1.docx-Heading1, genoffice h1). They belong to the content oracle
    // only. The timing surface stays the selector's own boxes.
    const openingHeadings = () => {
      if (!selector) return '';
      const matched = Array.from(document.querySelectorAll(selector));
      if (!matched.length) return '';
      const seen = new Set();
      const parts = [];
      const takeHeading = (heading) => {
        if (!heading || seen.has(heading)) return;
        const tag = heading.tagName || '';
        if (tag.length !== 2 || tag[0] !== 'H' || tag[1] < '1' || tag[1] > '6') return;
        if (matched.some((node) => node === heading || node.contains(heading) || heading.contains(node))) return;
        seen.add(heading);
        const text = elementText(heading);
        if (text) parts.push(text);
      };
      for (const node of matched) {
        let parent = node.parentElement;
        for (let depth = 0; parent && depth < 6; depth += 1, parent = parent.parentElement) {
          for (const heading of parent.querySelectorAll('h1,h2,h3,h4,h5,h6')) takeHeading(heading);
        }
      }
      return parts.join(' ');
    };
    const text = chunks.join(' ').replace(/\s+/g, ' ').trim();
    const rect = n
      ? excludeMarker({ x: minX, y: minY, width: maxX - minX, height: maxY - minY })
      : null;
    state.documentSelector = selector || null;
    state.surfaceText = text;
    return {
      text, chars: text.length, rect, selector: selector || null,
      documentText: [openingHeadings(), contentChunks.join(' ')].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim(), canvasPresent,
    };
  };
  const tick = () => {
    if (state.firstElementAt === null) {
      const target = pageSel ? document.querySelector(pageSel) : document.querySelector(docSel);
      const info = box(target);
      if (info) {
        state.firstElementAt = performance.now();
        state.firstElementInfo = info;
        state.pageCountAtFirst = pageSel ? document.querySelectorAll(pageSel).length : null;
      }
    }
    if (state.docTextAt === null && signal !== 'screencast_ink') {
      const surface = window.__docProbeSurface(signal);
      const chars = signal === 'canvas_pixel' ? (surface.chars > 0 ? 1 : 0) : surface.chars;
      if ((signal === 'canvas_pixel' && chars > 0) || (signal !== 'canvas_pixel' && chars >= minChars)) {
        state.docTextAt = performance.now();
        state.docTextCharsAt = chars;
      }
    }
    // The lax layer (owner 2026-11-11) replaced a hardcoded 120 s with the
    // probe's own --timeout-ms budget, injected here: this runs in the page.
    if (state.docTextAt === null && signal !== 'screencast_ink' && performance.now() < textWaitBudgetMs) {
      requestAnimationFrame(tick);
    }
  };
  requestAnimationFrame(tick);
};

async function newPage(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  await routeCorpus(context);
  const page = await context.newPage();
  const trace = await startChromeTrace(browser, page, opt.mode || 'document');
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
  await page.addInitScript(INIT_SCRIPT, {
    docSel: docSelector,
    pageSel: pageSelector,
    minTextChars: minTextChars,
    signal: usableSignal,
    documentSelector,
    textWaitBudgetMs: timeoutMs,
  });
  return { context, page, errors, cdp: null, recorder: null, trace };
}

async function releaseContext(browser, ctx) {
  await stopChromeTrace(browser, ctx.trace);
  await ctx.context.close();
}

/**
 * PNG screencast on the page clock. The witness recorder listens for
 * Page.screencastFrame and acks every frame. One screencast per page.
 */
async function beginWitness(ctx) {
  const cdp = await ctx.context.newCDPSession(ctx.page);
  const recorder = getRecorder(cdp, { manageScreencast: true, maxWidth: 1280, maxHeight: 900 });
  await cdp.send('Page.startScreencast', {
    format: 'png',
    everyNthFrame: 1,
    maxWidth: 1280,
    maxHeight: 900,
  });
  recorder.started = true;
  ctx.cdp = cdp;
  ctx.recorder = recorder;
}

async function endWitness(ctx) {
  if (!ctx.cdp) return;
  try {
    await stopRecorder(ctx.cdp);
  } catch {
    /* already stopped */
  }
}

async function launch() {
  const { chromium } = await loadPlaywright();
  return chromium.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text', WEBGL_UNMASK_FLAG],
  });
}

async function stateSnapshot(page) {
  const expectedOpening = typeof opt['expected-opening-text'] === 'string' ? opt['expected-opening-text'] : '';
  const snap = await page.evaluate(
    ({ docSel, pageSel, signal }) => {
      const s = window.__docProbeState || {};
      const pageEl = pageSel ? document.querySelector(pageSel) : null;
      const which =
        signal === 'canvas_pixel'
          ? 'canvas_pixel'
          : signal === 'shadow_text'
            ? 'shadow_text'
            : signal === 'screencast_ink'
              ? 'screencast_ink'
              : 'dom_text';
      const surface = typeof window.__docProbeSurface === 'function' ? window.__docProbeSurface(which) : null;
      const docText = surface ? surface.documentText || '' : '';
      const model_oracle = 'dom';
      const content_text_accessible = Boolean(docText.trim());
      const model_document_check = null;
      const document_text_chars = docText.length;
      const canvasPresent = Boolean(surface?.canvasPresent);
      return {
        first_element_ms: s.firstElementAt === null || s.firstElementAt === undefined ? null : s.firstElementAt,
        first_element_info: s.firstElementInfo || null,
        document_text_at_ms: s.docTextAt === null || s.docTextAt === undefined ? null : s.docTextAt,
        document_text_chars_at: s.docTextCharsAt === null || s.docTextCharsAt === undefined ? null : s.docTextCharsAt,
        page_count_at_first: s.pageCountAtFirst === null || s.pageCountAtFirst === undefined ? null : s.pageCountAtFirst,
        page_count: pageSel ? document.querySelectorAll(pageSel).length : null,
        page_text_chars: pageEl ? (pageEl.textContent || '').trim().length : null,
        document_text_chars,
        document_text: docText.slice(0, 4000),
        content_text_accessible,
        canvas_present: canvasPresent,
        model_oracle,
        model_document_check,
        document_selector: (surface && surface.selector) || s.documentSelector || null,
        surface_text: docText.slice(0, 4000),
        time_origin_ms: performance.timeOrigin,
        usable_signal: s.usableSignal || null,
      };
    },
    {
      docSel: docSelector,
      pageSel: pageSelector,
      signal: usableSignal,
    },
  );

  const applyGatedRead = (gated) => {
    snap.document_text = gated.text.slice(0, 4000);
    snap.surface_text = snap.document_text;
    snap.document_text_chars = gated.chars;
    snap.content_text_accessible = Boolean(gated.text.trim());
    snap.model_oracle = gated.oracle;
    snap.model_document_check = gated.modelDocumentCheck;
    snap.dom_document_check = gated.domDocumentCheck;
    snap.content_check = gated.content_check;
    snap.content_check_reason = gated.content_check_reason;
    snap.content_length_check = gated.length_check;
    snap.length_enforced = gated.length_enforced;
    snap.editor_error = gated.error;
    snap.document_source = gated.source;
  };

  if (editorId && hasDocumentTextSurface(editorId)) {
    applyGatedRead(await readAndGateDocumentText(page, editorId, {
      expectedOpening,
      expectedClosing: expectedClosingSentinel,
      fixtureChars: fixtureTextChars,
      lengthCheckMode,
      root: documentSelector || docSelector || editSelector,
      expectedBody: expectedBodyText,
    }));
  } else if (!snap.document_text.trim() && snap.canvas_present) {
    applyGatedRead(await readAndGateDocumentText(page, 'canvas', {
      expectedOpening,
      expectedClosing: expectedClosingSentinel,
      fixtureChars: fixtureTextChars,
      lengthCheckMode,
      expectedBody: expectedBodyText,
    }));
  }
  return snap;
}

async function readSurface(page) {
  return page.evaluate(() => {
    const s = window.__docProbeState || {};
    return {
      at_ms: s.docTextAt === null || s.docTextAt === undefined ? null : s.docTextAt,
      chars: s.docTextCharsAt === null || s.docTextCharsAt === undefined ? null : s.docTextCharsAt,
      signal: s.usableSignal || null,
    };
  });
}

/** Text-bearing (or drawn-canvas) rect, with the 8x8 calibration square outside it. */
async function unionRegionRect(page, selector) {
  if (!selector) return null;
  return page
    .evaluate((sel) => {
      const nodes = Array.from(document.querySelectorAll(sel));
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;
      let n = 0;
      for (const el of nodes) {
        const r = el.getBoundingClientRect();
        if (!(r.width > 0 && r.height > 0)) continue;
        minX = Math.min(minX, r.left);
        minY = Math.min(minY, r.top);
        maxX = Math.max(maxX, r.right);
        maxY = Math.max(maxY, r.bottom);
        n += 1;
      }
      if (!n) return null;
      return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
    }, selector)
    .catch(() => null);
}

/** C12 witness region: the reflow surface when load and edit surfaces differ. */
async function reflowDocumentRegion(page, editorId) {
  const witnessSel = reflowWitnessSelector(editorId);
  if (witnessSel) {
    const rect = await unionRegionRect(page, witnessSel);
    if (rect && rect.width > 0 && rect.height > 0) return { rect };
  }
  return documentRegion(page);
}

async function documentRegion(page) {
  const rect = await page
    .evaluate((signal) => {
      const fn = window.__docProbeSurface;
      if (typeof fn !== 'function') return null;
      const which =
        signal === 'canvas_pixel'
          ? 'canvas_pixel'
          : signal === 'shadow_text'
            ? 'shadow_text'
            : signal === 'screencast_ink'
              ? 'screencast_ink'
              : 'dom_text';
      const surface = fn(which);
      return surface && surface.rect ? surface.rect : null;
    }, usableSignal)
    .catch(() => null);
  if (!rect || !(rect.width > 0) || !(rect.height > 0)) return null;
  return { rect };
}

/** Latest screencast frame while the document surface is still absent. */
async function waitForSurfaceKeepingBaseline(page, recorder) {
  const deadline = Date.now() + timeoutMs;
  let baseline = null;
  while (Date.now() < deadline) {
    let surface;
    try {
      surface = await readSurface(page);
    } catch (error) {
      const message = String(error && error.message ? error.message : error);
      if (/closed|disposed|Target closed/i.test(message)) {
        return { surface: { at_ms: null, chars: null, signal: null }, baseline };
      }
      surface = { at_ms: null, chars: null, signal: null };
    }
    if (surface.at_ms === null) {
      const last = recorder && recorder.frames.length ? recorder.frames[recorder.frames.length - 1] : null;
      if (last) baseline = last;
      await sleep(12);
      continue;
    }
    return { surface, baseline };
  }
  let surface;
  try {
    surface = await readSurface(page);
  } catch (error) {
    const message = String(error && error.message ? error.message : error);
    if (/closed|disposed|Target closed/i.test(message)) {
      return { surface: { at_ms: null, chars: null, signal: null }, baseline };
    }
    surface = { at_ms: null, chars: null, signal: null };
  }
  return { surface, baseline };
}

async function waitForSurface(page) {
  const found = await waitForSurfaceKeepingBaseline(page, null);
  return found.surface;
}

async function canvasReadable(page) {
  return page.evaluate((docSel) => {
    const nodes = Array.from(document.querySelectorAll(docSel)).filter(
      (el) => typeof HTMLCanvasElement !== 'undefined' && el instanceof HTMLCanvasElement,
    );
    const readable = nodes.some((el) => {
      try {
        const g = el.getContext('2d');
        return Boolean(g && typeof g.getImageData === 'function');
      } catch {
        return false;
      }
    });
    return { canvases: nodes.length, readable };
  }, docSelector);
}

function witnessFacts(witness) {
  if (!witness) {
    return {
      presented_frame_ms: null,
      frames_total: 0,
      frames_after_usable: 0,
      clock_skew_ms: null,
      clock_skew_acceptable: null,
      witness: null,
    };
  }
  return {
    presented_frame_ms: witness.outcome === 'witnessed' ? witness.frame_page_ms : null,
    frames_total: witness.frames_total,
    frames_after_usable: witness.frames_after,
    clock_skew_ms: witness.clock_skew_ms,
    clock_skew_acceptable: witness.clock_skew_acceptable,
    witness,
  };
}

async function loadResult(ctx, { navigationMs, readyMs, surface, witness, surfaceReason, baseline = null }) {
  const paints = await paintEntries(ctx.page);
  const snap = await stateSnapshot(ctx.page);
  const fcp = fcpFrom(paints);
  let finalWitness = witness;
  let facts = witnessFacts(finalWitness);
  // Content qualifies the settled surface; it must not move the pixel clock.
  const expectedRaw = opt['expected-opening-text'] || '';
  const verdict = openingContentVerdict({
    expected: expectedRaw,
    actual: snap.document_text,
    modelOracle: snap.model_oracle || 'dom',
    modelDocumentCheck: snap.model_document_check,
    domDocumentCheck: snap.dom_document_check,
    editorError: snap.editor_error,
  });
  const contentVerified = verdict.content_verified;
  const contentReason = contentVerified ? null : verdict.surface_reason;
  let at = !contentReason && surface && surface.at_ms !== null && surface.at_ms !== undefined ? surface.at_ms : null;
  // Model hosts (docen screencast_ink): content is in the model while the ink
  // stamp may lag; once the gate passes and a witness frame exists, bind the
  // surface clock to the first layout box or ready time, not FCP.
  if (contentVerified && snap.model_oracle === 'perf_model') {
    const inkAt =
      surface && surface.at_ms !== null && surface.at_ms !== undefined ? surface.at_ms : null;
  const fallback = snap.first_element_ms ?? readyMs;
    const candidates = [at, inkAt, fallback].filter((value) => typeof value === 'number');
    if (candidates.length) at = Math.max(...candidates);
  }
  // Screencast ink may miss a stamp while the model gate already passed; witness then.
  if (at !== null && facts.presented_frame_ms === null && ctx.recorder && ctx.cdp) {
    const region = await documentRegion(ctx.page);
    finalWitness = await witnessFrame(ctx.page, ctx.cdp, {
      afterPageMs: at,
      baseline: baseline || null,
      windowMs: DEFAULT_WINDOW_MS,
      caretMask: true,
      settleMs: 0,
      recorder: ctx.recorder,
      minPixels: baseline ? 4 : 1,
      region,
    });
    facts = witnessFacts(finalWitness);
  }
  return {
    mode: 'load',
    driver: 'playwright',
    url,
    navigation_ms: navigationMs,
    ready_ms: readyMs,
    paints,
    fcp_ms: fcp,
    first_element_ms: snap.first_element_ms,
    first_element_info: snap.first_element_info,
    first_element_selector: pageSelector || docSelector,
    document_text_at_ms: at,
    usable_ms: at,
    usable_signal: (surface && surface.signal) || SIGNAL_NAME[usableSignal],
    first_element_delta_from_fcp_ms: fcp !== null && snap.first_element_ms !== null ? snap.first_element_ms - fcp : null,
    document_text_ms_delta_from_fcp_ms: fcp !== null && at !== null ? at - fcp : null,
    page_model: pageModel,
    page_count: snap.page_count,
    page_count_at_first: snap.page_count_at_first,
    document_text_chars: snap.document_text_chars,
    document_text: snap.document_text,
    document_selector: snap.document_selector,
    surface_text: snap.surface_text,
    presented_frame_ms: facts.presented_frame_ms,
    frames_total: ctx.recorder ? ctx.recorder.frames.length : facts.frames_total,
    frames_after_usable: facts.frames_after_usable,
    frame_source: 'cdp_screencast',
    clock_skew_ms: facts.clock_skew_ms,
    clock_skew_acceptable: facts.clock_skew_acceptable,
    witness: facts.witness,
    surface_reason: contentReason || surfaceReason || null,
    content_verified: contentVerified,
    content_length_check: snap.content_length_check ?? null,
    length_enforced: snap.length_enforced ?? null,
    content_check: snap.content_check ?? null,
    content_check_reason: snap.content_check_reason ?? null,
    content_text_accessible: snap.content_text_accessible,
    editor_error: snap.editor_error || null,
    expected_opening_text: normalizeDocumentText(expectedRaw) || null,
    screencast_ink_match_tolerance: usableSignal === 'screencast_ink' ? SETTLED_MATCH_TOLERANCE : null,
    screencast_ink_inset_css_px: usableSignal === 'screencast_ink' ? 4 : null,
    screencast_ink_min_pixels: usableSignal === 'screencast_ink' ? screencastInkMinPixels : null,
    page_errors: ctx.errors,
  };
}

async function runLoad(browser) {
  const ctx = await newPage(browser);
  // The first recorded navigation frame can already contain the document.
  // Preserve real, full-viewport pixels from before navigation rather than
  // letting witnessFrame choose a later frame as a historical baseline.
  const navigationBaseline = (await ctx.page.screenshot()).toString('base64');
  await beginWitness(ctx);
  try {
    if (usableSignal === 'shadow_text' && !documentSelector) {
      return await loadResult(ctx, {
        navigationMs: 0,
        readyMs: 0,
        surface: { at_ms: null, chars: null, signal: SIGNAL_NAME.shadow_text },
        witness: null,
        surfaceReason: 'document_selector_required',
      });
    }
  // Watch the surface from before navigation. A ready signal that means
    // "document text exists" would otherwise return with no pre-surface frame,
    // and a 1x1 stand-in cannot be compared with a screencast frame.
    const watching =
      usableSignal === 'screencast_ink' ? null : waitForSurfaceKeepingBaseline(ctx.page, ctx.recorder);
    const navT0 = Date.now();
    await ctx.page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationMs = Date.now() - navT0;
    const readyMs = await waitForReady(ctx.page);
    if (settleMs > 0) await ctx.page.waitForTimeout(settleMs);
    if (usableSignal === 'canvas_pixel') {
      const readable = await canvasReadable(ctx.page);
      if (readable.canvases > 0 && !readable.readable) {
        return await loadResult(ctx, {
          navigationMs,
          readyMs,
          surface: { at_ms: null, chars: null, signal: SIGNAL_NAME.canvas_pixel },
          witness: null,
          surfaceReason: 'canvas has no readable 2d context; FCP is not a C11 sample',
        });
      }
    }
    let surface;
    let baseline = null;
    let surfaceReason = null;
    if (usableSignal === 'screencast_ink') {
      const ink = await waitForScreencastInk(ctx.page, ctx.recorder);
      baseline = ink.baseline;
      surface = {
        at_ms: ink.at_ms,
        chars: ink.at_ms === null ? null : 1,
        signal: ink.signal,
      };
      surfaceReason = ink.reason;
    } else {
      const waited = await watching;
      surface = waited.surface;
      baseline = waited.baseline;
      surfaceReason =
        surface.at_ms === null ? 'document surface did not appear before the probe timeout' : null;
    }
    let witness = null;
    if (surface.at_ms !== null) {
      const region = await documentRegion(ctx.page);
      witness = await witnessFrame(ctx.page, ctx.cdp, {
        afterPageMs: surface.at_ms,
        baseline: baseline || navigationBaseline,
        windowMs: DEFAULT_WINDOW_MS,
        caretMask: true,
        settleMs: 0,
        recorder: ctx.recorder,
        minPixels: baseline ? 4 : 1,
        region,
      });
    }
    return await loadResult(ctx, {
      navigationMs,
      readyMs,
      surface,
      witness,
      surfaceReason,
      baseline: baseline || navigationBaseline,
    });
  } finally {
    await endWitness(ctx);
    await releaseContext(browser, ctx);
  }
}

async function settleStableFrame(page, recorder) {
  const rafSettle = await page.evaluate(
    () =>
      new Promise((resolve) => {
        let n = 0;
        const tick = (t) => {
          n += 1;
          if (n >= 3) resolve(t);
          else requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }),
  );
  const deadline = Date.now() + 400;
  let previous = null;
  let stable = 0;
  while (Date.now() < deadline) {
    const frame = recorder.frames.length ? recorder.frames[recorder.frames.length - 1] : null;
    if (frame && previous && frame.seq !== previous.seq && frame.data === previous.data) {
      stable += 1;
      if (stable >= 1) return { frame, rafSettle };
    } else if (frame && (!previous || frame.data !== previous.data)) {
      stable = 0;
    }
    previous = frame || previous;
    if (recorder.frames.length === 0) {
      await sleep(10);
      continue;
    }
    await sleep(16);
  }
  const frame = recorder.frames.length ? recorder.frames[recorder.frames.length - 1] : null;
  return { frame, rafSettle };
}

async function runScale(browser) {
  const ctx = await newPage(browser);
  await beginWitness(ctx);
  try {
    if (usableSignal === 'shadow_text' && !documentSelector) {
      return {
        mode: 'scale',
        driver: 'playwright',
        url,
        navigation_ms: 0,
        ready_ms: 0,
        usable_ms: null,
        usable_signal: SIGNAL_NAME.shadow_text,
        surface_reason: 'document_selector_required',
        page_errors: ctx.errors,
      };
    }
    const navT0 = Date.now();
    await ctx.page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationMs = Date.now() - navT0;
    const readyMs = await waitForReady(ctx.page);
    if (settleMs > 0) await ctx.page.waitForTimeout(settleMs);
    let surfaceReason = null;
    if (usableSignal === 'canvas_pixel') {
      const readable = await canvasReadable(ctx.page);
      if (readable.canvases > 0 && !readable.readable) {
        surfaceReason = 'canvas has no readable 2d context; FCP is not a C14 sample';
      }
    }
    let surface;
    if (surfaceReason) {
      surface = { at_ms: null, chars: null, signal: SIGNAL_NAME.canvas_pixel };
    } else if (usableSignal === 'screencast_ink') {
      const ink = await waitForScreencastInk(ctx.page, ctx.recorder);
      surface = { at_ms: ink.at_ms, chars: ink.at_ms === null ? null : 1, signal: ink.signal };
      surfaceReason = ink.reason;
    } else {
      surface = await waitForSurface(ctx.page);
    }
    const snap = await stateSnapshot(ctx.page);
    const paints = await paintEntries(ctx.page);
    let natural = null;
    let forced = null;
    let mechanism = null;
    if (surface.at_ms !== null) {
      const settled = await settleStableFrame(ctx.page, ctx.recorder);
      const afterPageMs = await ctx.page.evaluate(() => performance.now());
      const region = await documentRegion(ctx.page);
      natural = await witnessFrame(ctx.page, ctx.cdp, {
        afterPageMs,
        baseline: settled.frame || null,
        windowMs: DEFAULT_WINDOW_MS,
        caretMask: true,
        settleMs: 0,
        recorder: ctx.recorder,
        // No settled frame: nothing to compare, so do not invent document damage.
        minPixels: settled.frame ? 4 : 1e9,
        region,
      });
      if (natural.outcome === 'witnessed') {
        mechanism = 'document_damage';
      } else {
        mechanism = 'forced_repaint';
        const pre = ctx.recorder.frames.length ? ctx.recorder.frames[ctx.recorder.frames.length - 1] : settled.frame;
        const armedAt = await ctx.page.evaluate(() => {
          const probe = document.createElement('div');
          probe.id = '__c14_forced_repaint__';
          probe.setAttribute(
            'style',
            'position:fixed;right:0;bottom:0;width:1px;height:1px;outline:1px solid #ff00aa;z-index:2147483646;pointer-events:none',
          );
          (document.body || document.documentElement).appendChild(probe);
          return performance.now();
        });
        forced = await witnessFrame(ctx.page, ctx.cdp, {
          afterPageMs: armedAt,
          baseline: pre || null,
          windowMs: DEFAULT_WINDOW_MS,
          caretMask: true,
          settleMs: 0,
          recorder: ctx.recorder,
          minPixels: 1,
          threshold: 0,
          region,
          clockCheck: natural.clock_check,
        });
      }
    }
    const chosen = mechanism === 'forced_repaint' ? forced : natural;
    const facts = witnessFacts(chosen);
    // The exclusion decision is the post-settle window. A forced outline is
    // kept beside it and is never the measured sample.
    const decision = natural || chosen;
    return {
      mode: 'scale',
      driver: 'playwright',
      url,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      paints,
      fcp_ms: fcpFrom(paints),
      usable_ms: surface.at_ms,
      usable_source: surface.signal || SIGNAL_NAME[usableSignal],
      usable_signal: surface.signal || SIGNAL_NAME[usableSignal],
      first_element_ms: snap.first_element_ms,
      page_model: pageModel,
      page_count: snap.page_count,
      document_text_chars: snap.document_text_chars,
      document_text: snap.document_text,
      document_selector: snap.document_selector,
      surface_text: snap.surface_text,
      presented_frame_ms: mechanism === 'document_damage' ? facts.presented_frame_ms : chosen && chosen.outcome === 'witnessed' ? chosen.frame_page_ms : null,
      frames_total: decision ? decision.frames_total : 0,
      frames_after_usable: decision ? decision.frames_after : 0,
      frame_source: 'cdp_screencast',
      mechanism,
      clock_skew_ms: (chosen || decision) && (chosen || decision).clock_skew_ms,
      clock_skew_acceptable: (chosen || decision) && (chosen || decision).clock_skew_acceptable,
      witness: decision,
      forced_witness: forced,
      surface_reason: surface.at_ms === null ? surfaceReason || 'document surface did not appear before the probe timeout' : null,
      page_errors: ctx.errors,
    };
  } finally {
    await endWitness(ctx);
    await releaseContext(browser, ctx);
  }
}

async function runReflow(browser) {
  const ctx = await newPage(browser);
  await beginWitness(ctx);
  try {
    const navT0 = Date.now();
    await ctx.page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationMs = Date.now() - navT0;
    const readyMs = await waitForReady(ctx.page);
    if (settleMs > 0) await ctx.page.waitForTimeout(settleMs);

    if (editorId && C12_NO_PARAGRAPH_GEOMETRY.has(editorId)) {
      // r3lanes4 ruling 4: the page container is not a paragraph. canvas and
      // docen paint whole pages; no DOM block box can carry a paragraph's
      // y-shift, so C12 is not_applicable with the census as evidence —
      // never measured from a page box.
      const modelKind = EDIT_SURFACES[editorId] && EDIT_SURFACES[editorId].model;
      const census = await ctx.page.evaluate(
        ({ modelSrc, model, docSel }) => {
          let modelParagraphs = null;
          try {
            if (typeof modelSrc === 'string' && modelSrc) {
              // eslint-disable-next-line no-eval
              const list = eval(modelSrc);
              const paragraphs = list(model);
              modelParagraphs = Array.isArray(paragraphs) ? paragraphs.length : null;
            }
          } catch {
            modelParagraphs = null;
          }
          const blocks = Array.from(document.querySelectorAll(docSel));
          const withText = blocks.filter((block) => (block.textContent || '').trim()).length;
          return { model_paragraphs: modelParagraphs, dom_blocks: withText, dom_nodes: blocks.length };
        },
        { modelSrc: LIST_MODEL_PARAGRAPHS.toString(), model: modelKind, docSel: docSelector || editSelector },
      );
      const container =
        editorId === 'canvas'
          ? '#editor .ce-page-container (host paints into <canvas>)'
          : 'docen-document shadow .canvas-pages > div (page pitch)';
      return {
        mode: 'reflow',
        status: 'not_applicable',
        reason:
          `no paragraph geometry to attribute a C12 y-shift: this host paints whole pages ` +
          `(${container}); the only DOM box is the page container, which is not a paragraph ` +
          `(model_paragraphs=${census.model_paragraphs}, dom_blocks=${census.dom_blocks})`,
        evidence: { ...census, page_container: container, model: modelKind },
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        window_excludes_forced_layout: true,
        forced_layout_ms: 0,
        page_errors: ctx.errors,
      };
    }

    if (editorId) {
      const prepared = await prepareLaneCaret(ctx.page, editorId, editSelector, { timeoutMs });
      if (prepared.placeError) {
        return {
          mode: 'reflow',
          driver: 'playwright',
          url,
          navigation_ms: navigationMs,
          ready_ms: readyMs,
          error: prepared.placeError,
          window_excludes_forced_layout: true,
          forced_layout_ms: 0,
        };
      }
    }

    if (!editorId) {
      const box = await ctx.page.locator(editSelector).first().boundingBox();
      if (!box) {
        return {
          mode: 'reflow',
          driver: 'playwright',
          url,
          navigation_ms: navigationMs,
          ready_ms: readyMs,
          error: 'edit target has no box',
          window_excludes_forced_layout: true,
          forced_layout_ms: 0,
        };
      }
      await ctx.page.mouse.click(box.x + 3, box.y + Math.min(8, Math.max(2, box.height / 2)));
      await ctx.page.waitForTimeout(150);
    }
    await ctx.page.keyboard.press('Control+Home');
    await ctx.page.waitForTimeout(150);
    await ctx.page.keyboard.press('Home');
    await ctx.page.waitForTimeout(100);

    const reflowSel = reflowBlockSelector(editorId, docSelector);
    const editSurface = editorId && EDIT_SURFACES[editorId] ? EDIT_SURFACES[editorId] : null;
    const excludeSelEarly = editSurface && editSurface.exclude ? editSurface.exclude : '';
    await ensureReflowCaret(ctx.page, reflowSel, {
      settleMs: 100,
      editorId,
      excludeSel: excludeSelEarly,
    });
    if (editorId === 'superdoc') {
      try {
        await ctx.page.waitForFunction(
          () => {
            const lines = Array.from(document.querySelectorAll('#editor .superdoc-line'));
            return lines.some((line) => {
              const text = String(line.textContent || '').replace(/\s+/g, ' ').trim();
              return text.length >= 24 && !/^(Article \d+\.|Section \d+\.\d+\s)/.test(text);
            });
          },
          null,
          { timeout: 60000, polling: 100 },
        );
      } catch {
        /* best effort */
      }
    }
    let bodyCaret = await placeC12BodyCaret(ctx.page, editorId, reflowSel, excludeSelEarly);
    if (!bodyCaret || bodyCaret.ok !== true) {
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        error: bodyCaret?.reason || 'c12_body_caret_unavailable',
        caret_placement: bodyCaret || null,
        window_excludes_forced_layout: true,
        forced_layout_ms: 0,
        page_errors: ctx.errors,
      };
    }

    // The census runs after the caret is finally placed (the adapter's click,
    // then Control+Home/Home): the anchor is the nearest unique block below
    // THAT caret on the same screen (r3lanes4 ruling 3). This is still all
    // before the Enter listener arms, outside the measured window.
    const excludeSel = excludeSelEarly;
    const before = await ctx.page.evaluate(gatherReflowBefore, {
      editorId: editorId || '',
      docSel: reflowSel,
      excludeSel,
      pickBelowSrc: PICK_ANCHOR_BELOW.toString(),
      entriesSrc: C12_BLOCK_ENTRIES_PAGE_SRC,
    });
    if (!before.ok) {
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        error: before.reason,
        window_excludes_forced_layout: true,
        forced_layout_ms: 0,
      };
    }

    const frameDeadline = Date.now() + 1500;
    while (ctx.recorder.frames.length === 0 && Date.now() < frameDeadline) await sleep(10);
    const baseline = ctx.recorder.frames.length ? ctx.recorder.frames[ctx.recorder.frames.length - 1] : null;

    const inputMark = await ctx.page.evaluate(() => {
      window.__c12InputMs = null;
      document.addEventListener(
        'keydown',
        (event) => {
          if (event.key === 'Enter' && window.__c12InputMs === null) window.__c12InputMs = performance.now();
        },
        true,
      );
      return performance.now();
    });
    await ctx.page.keyboard.press('Enter');
    await ctx.page.keyboard.type('x', { delay: 0 });
    const snapshot = await ctx.page.evaluate(() => window.__c12BeforeSnapshot || null);
    const editConfirmMs = Math.min(timeoutMs, 10_000);
    const editSeen = await waitForC12CaretEdit(
      ctx.page,
      editorId,
      reflowSel,
      excludeSel,
      snapshot,
      { timeoutMs: editConfirmMs },
    );
    const evaluateAnchorIdentity = () =>
      ctx.page.evaluate(
        ({ checkSrc, diagSrc, blockTextSrc, entriesSrc, eid, excl, docSel }) => {
          const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
          let readBlock = (block) => norm(block.innerText || block.textContent);
          try {
            // eslint-disable-next-line no-eval
            const fn = eval(blockTextSrc);
            if (typeof fn === 'function') {
              readBlock = (block) => fn(block, norm);
            }
          } catch {
            /* keep default */
          }
          const snap = window.__c12BeforeSnapshot;
          if (!snap || !docSel) return { ok: false, reason: 'anchor_identity_ambiguous' };
          let check = null;
          let collect = null;
          try {
            // eslint-disable-next-line no-eval
            check = (0, eval)(`(function(){ ${checkSrc}; return ANCHOR_REFIND_CONTEXT_OK; })()`);
          } catch {
            check = null;
          }
          try {
            // eslint-disable-next-line no-eval
            collect = (0, eval)(`(function(){ ${entriesSrc}; return c12BlockEntries; })()`);
          } catch {
            collect = null;
          }
          if (typeof check !== 'function' || typeof collect !== 'function') {
            return { ok: false, reason: 'anchor_identity_ambiguous' };
          }
          const entries = collect(eid, docSel, excl || '', readBlock);
          const blocks = entries.map((entry) => entry.el);
          const verdict = check(snap, blocks, readBlock);
          if (verdict && verdict.ok === false) {
            let diagnose = null;
            try {
              // eslint-disable-next-line no-eval
              const diagFn = (0, eval)(`(function(){ ${diagSrc}; return C12_IDENTITY_REFUSAL_DIAGNOSTIC; })()`);
              if (typeof diagFn === 'function') {
                const texts = entries.map((entry) => entry.text);
                diagnose = diagFn(snap, texts, norm, 8, 80);
              }
            } catch {
              diagnose = null;
            }
            return { ...verdict, identity_diagnostic: diagnose };
          }
          return verdict;
        },
        {
          checkSrc: `${ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC}`,
          diagSrc: `${C12_IDENTITY_DIAGNOSTIC_PAGE_SRC}`,
          blockTextSrc: `${C12_BLOCK_TEXT}`,
          entriesSrc: `${C12_BLOCK_ENTRIES_PAGE_SRC}`,
          eid: editorId || '',
          excl: excludeSel,
          docSel: reflowSel,
        },
      );
    if (!editSeen || editSeen.ok !== true) {
      const anchorOnEditMiss = await evaluateAnchorIdentity();
      if (anchorOnEditMiss && anchorOnEditMiss.ok === false) {
        return {
          mode: 'reflow',
          driver: 'playwright',
          url,
          navigation_ms: navigationMs,
          ready_ms: readyMs,
          before,
          error: anchorOnEditMiss.reason || 'anchor_identity_ambiguous',
          identity_diagnostic: anchorOnEditMiss.identity_diagnostic || null,
          edit_confirmation: editSeen || null,
          moved: false,
          anchor_top_after: null,
          anchor_after_top: null,
          shift_px: null,
          window_excludes_forced_layout: true,
          forced_layout_ms: 0,
          page_errors: ctx.errors,
        };
      }
      const identityDiagnostic = await ctx.page.evaluate(
        ({ diagSrc, entriesSrc, blockTextSrc, eid, excl, docSel }) => {
          const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
          let readBlock = (block) => norm(block.innerText || block.textContent);
          try {
            // eslint-disable-next-line no-eval
            const fn = eval(blockTextSrc);
            if (typeof fn === 'function') readBlock = (block) => fn(block, norm);
          } catch {
            /* keep default */
          }
          const snap = window.__c12BeforeSnapshot;
          let collect = null;
          try {
            // eslint-disable-next-line no-eval
            collect = (0, eval)(`(function(){ ${entriesSrc}; return c12BlockEntries; })()`);
          } catch {
            collect = null;
          }
          let diagnose = null;
          if (snap && typeof collect === 'function') {
            const entries = collect(eid, docSel, excl || '', readBlock);
            const texts = entries.map((entry) => entry.text);
            try {
              // eslint-disable-next-line no-eval
              const diagFn = (0, eval)(`(function(){ ${diagSrc}; return C12_IDENTITY_REFUSAL_DIAGNOSTIC; })()`);
              if (typeof diagFn === 'function') diagnose = diagFn(snap, texts, norm, 8, 80);
            } catch {
              diagnose = null;
            }
          }
          return diagnose;
        },
        {
          diagSrc: `${C12_IDENTITY_DIAGNOSTIC_PAGE_SRC}`,
          blockTextSrc: `${C12_BLOCK_TEXT}`,
          entriesSrc: `${C12_BLOCK_ENTRIES_PAGE_SRC}`,
          eid: editorId || '',
          excl: excludeSel,
          docSel: reflowSel,
        },
      );
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        before,
        error: editSeen?.reason || 'edit_not_observed',
        identity_diagnostic: identityDiagnostic,
        edit_confirmation: editSeen || null,
        moved: false,
        anchor_top_after: null,
        anchor_after_top: null,
        shift_px: null,
        window_excludes_forced_layout: true,
        forced_layout_ms: 0,
        page_errors: ctx.errors,
      };
    }
    const anchorIdentity = await evaluateAnchorIdentity();
    if (anchorIdentity && anchorIdentity.ok === false) {
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        before,
        error: anchorIdentity.reason || 'anchor_identity_ambiguous',
        identity_diagnostic: anchorIdentity.identity_diagnostic || null,
        moved: false,
        anchor_top_after: null,
        anchor_after_top: null,
        shift_px: null,
        window_excludes_forced_layout: true,
        forced_layout_ms: 0,
        page_errors: ctx.errors,
      };
    }
    // The observation window waits for frames. It does not read layout.
    // getBoundingClientRect inside this window would flush layout and the
    // duration cannot be subtracted back out of the presented frame.
    await ctx.page.evaluate(() => {
      window.__c12Observe = true;
    });
    await ctx.page.evaluate(
      () =>
        new Promise((resolve) => {
          let n = 0;
          const step = () => {
            n += 1;
            if (n >= 3) resolve(0);
            else requestAnimationFrame(step);
          };
          requestAnimationFrame(step);
        }),
    );
    await ctx.page.evaluate(() => {
      window.__c12Observe = false;
    });
    const meter = await ctx.page.evaluate(() => ({
      reads: typeof window.__c12LayoutReads === 'number' ? window.__c12LayoutReads : 0,
      armed: window.__c12WindowArmed === true,
      input_page_ms: window.__c12InputMs === null || window.__c12InputMs === undefined ? null : window.__c12InputMs,
    }));
    const inputPageMs = meter.input_page_ms === null ? inputMark : meter.input_page_ms;
    // The sample ends when the anchor block has moved, then on the screencast
    // frame of that reflow. The first paint after Enter is not the reflow.
    // The no-read window is already closed, so this poll is not inside it.
    const shift = await ctx.page.evaluate(
      (refindSrc) => {
      let el = window.__c12AnchorEl;
      const before = window.__c12AnchorTop;
      const anchorText = window.__c12AnchorText;
      const docSel = window.__c12DocSel;
      const deadline = performance.now() + 4000;
      const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
      const readBlock = (block) => norm(block.innerText || block.textContent);
      let refind = null;
      let blockText = null;
      try {
        // eslint-disable-next-line no-eval
        refind = (0, eval)(`(function(){ ${refindSrc}; return REFIND_ANCHOR; })()`);
      } catch {
        refind = null;
      }
      const anchorOccurrence = window.__c12AnchorOccurrence;
      const resolveAnchor = () =>
        typeof refind === 'function'
          ? refind(docSel, anchorText, before, norm, readBlock, anchorOccurrence)
          : null;
      return new Promise((resolve) => {
        const step = () => {
          if (!el || !el.isConnected) el = resolveAnchor();
          else if (readBlock(el) !== anchorText) el = resolveAnchor();
          if (!el || typeof before !== 'number') {
            resolve({ moved: false, top: null, at: null });
            return;
          }
          const top = el.getBoundingClientRect().top;
          const now = performance.now();
          if (top > before + 0.5) {
            resolve({ moved: true, top, at: now });
            return;
          }
          if (now >= deadline) {
            resolve({ moved: false, top, at: null });
            return;
          }
          requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      });
    },
      `${REFIND_ANCHOR_PAGE_SRC}`,
    );
    let witness = null;
    if (shift.moved && typeof shift.at === 'number') {
      const region = await reflowDocumentRegion(ctx.page, editorId);
      const afterPageMs = Math.max(inputPageMs + 1, shift.at);
      witness = await witnessFrame(ctx.page, ctx.cdp, {
        afterPageMs,
        baseline: baseline || null,
        windowMs: 3000,
        caretMask: true,
        settleMs: 0,
        recorder: ctx.recorder,
        minPixels: baseline ? 4 : 1,
        region,
      });
    }
    const after = await ctx.page.evaluate(
      ({ docSel, anchorText, anchorTop, anchorOccurrence, refindSrc, blockTextSrc }) => {
        const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
        let readBlock = (block) => norm(block.innerText || block.textContent);
        try {
          // eslint-disable-next-line no-eval
          const fn = eval(blockTextSrc);
          if (typeof fn === 'function') {
            readBlock = (block) => fn(block, norm);
          }
        } catch {
          /* keep default */
        }
        const kept = window.__c12AnchorEl;
        let el = null;
        let matchedBy = null;
        if (kept && kept.isConnected && readBlock(kept) === anchorText) {
          el = kept;
          matchedBy = 'element';
        } else {
          let refind = null;
          try {
            // eslint-disable-next-line no-eval
            refind = (0, eval)(`(function(){ ${refindSrc}; return REFIND_ANCHOR; })()`);
          } catch {
            refind = null;
          }
          if (typeof refind === 'function') {
            el = refind(docSel, anchorText, anchorTop, norm, readBlock, anchorOccurrence);
            if (el) matchedBy = 'text';
          }
        }
        return {
          top: el ? el.getBoundingClientRect().top : null,
          block_count: document.querySelectorAll(docSel).length,
          matched_by: matchedBy,
        };
      },
      {
        docSel: reflowSel,
        anchorText: before.anchor_text,
        anchorTop: before.anchor_top,
        anchorOccurrence: before.anchor_occurrence,
        refindSrc: `${REFIND_ANCHOR_PAGE_SRC}`,
        blockTextSrc: `${C12_BLOCK_TEXT}`,
      },
    );
    const endIdentity = await ctx.page.evaluate(
      ({ checkSrc, diagSrc, blockTextSrc, entriesSrc, eid, excl, docSel }) => {
        const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
        let readBlock = (block) => norm(block.innerText || block.textContent);
        try {
          // eslint-disable-next-line no-eval
          const fn = eval(blockTextSrc);
          if (typeof fn === 'function') {
            readBlock = (block) => fn(block, norm);
          }
        } catch {
          /* keep default */
        }
        const snapshot = window.__c12BeforeSnapshot;
        if (!snapshot || !docSel) return { ok: false, reason: 'anchor_identity_ambiguous' };
        let check = null;
        let collect = null;
        try {
          // eslint-disable-next-line no-eval
          check = (0, eval)(`(function(){ ${checkSrc}; return ANCHOR_REFIND_CONTEXT_OK; })()`);
          // eslint-disable-next-line no-eval
          collect = (0, eval)(`(function(){ ${entriesSrc}; return c12BlockEntries; })()`);
        } catch {
          return { ok: false, reason: 'anchor_identity_ambiguous' };
        }
        if (typeof check !== 'function' || typeof collect !== 'function') {
          return { ok: false, reason: 'anchor_identity_ambiguous' };
        }
        const entries = collect(eid, docSel, excl || '', readBlock);
        const blocks = entries.map((entry) => entry.el);
        const verdict = check(snapshot, blocks, readBlock);
        if (verdict && verdict.ok === false) {
          let diagnose = null;
          try {
            // eslint-disable-next-line no-eval
            const diagFn = (0, eval)(`(function(){ ${diagSrc}; return C12_IDENTITY_REFUSAL_DIAGNOSTIC; })()`);
            if (typeof diagFn === 'function') {
              const texts = entries.map((entry) => entry.text);
              diagnose = diagFn(snapshot, texts, norm, 8, 80);
            }
          } catch {
            diagnose = null;
          }
          return { ...verdict, identity_diagnostic: diagnose };
        }
        const refusal = window.__c12AnchorRefusal || null;
        if (refusal) return { ok: false, reason: refusal };
        return verdict;
      },
      {
        checkSrc: `${ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC}`,
        diagSrc: `${C12_IDENTITY_DIAGNOSTIC_PAGE_SRC}`,
        blockTextSrc: `${C12_BLOCK_TEXT}`,
        entriesSrc: `${C12_BLOCK_ENTRIES_PAGE_SRC}`,
        eid: editorId || '',
        excl: excludeSel,
        docSel: reflowSel,
      },
    );
    if (endIdentity && endIdentity.ok === false) {
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        before,
        error: endIdentity.reason || 'anchor_identity_ambiguous',
        identity_diagnostic: endIdentity.identity_diagnostic || null,
        moved: false,
        anchor_top_after: null,
        anchor_after_top: null,
        shift_px: null,
        window_excludes_forced_layout: true,
        forced_layout_ms: 0,
        page_errors: ctx.errors,
      };
    }
    const moved = Boolean(shift.moved) && after.top !== null && after.top > before.anchor_top + 0.5;
    const framePageMs = witness && witness.outcome === 'witnessed' ? witness.frame_page_ms : null;
    const raw = framePageMs === null ? null : framePageMs - inputPageMs;
    const presented = raw;
    return {
      mode: 'reflow',
      driver: 'playwright',
      url,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      before,
      anchor_index: before.anchor_index,
      anchor_text: before.anchor_text,
      anchor_before_top: before.anchor_top,
      anchor_after_top: after.top,
      shift_px: moved && after.top !== null ? after.top - before.anchor_top : null,
      moved,
      matched_by: after.matched_by,
      block_count_before: before.blocks,
      block_count_after: after.block_count,
      insertion_created_block: after.block_count > before.blocks,
      anchor_top_after: after.top,
      input_page_ms: inputPageMs,
      observed_page_ms: framePageMs,
      observed_shift_page_ms: typeof shift.at === 'number' ? shift.at : null,
      forced_layout_ms: 0,
      window_excludes_forced_layout: true,
      presented_frame_raw_ms: raw,
      presented_frame_ms: presented,
      frames_total: witness ? witness.frames_total : ctx.recorder.frames.length,
      frames_after_shift_observed: witness ? witness.frames_after : 0,
      frame_source: 'cdp_screencast',
      clock_skew_ms: witness ? witness.clock_skew_ms : null,
      clock_skew_acceptable: witness ? witness.clock_skew_acceptable : null,
      witness,
      layout_reads_during_window: meter.reads,
      layout_window_armed: meter.armed,
      page_errors: ctx.errors,
      anchor_index_requested: anchorIndex,
    };
  } finally {
    await endWitness(ctx);
    await releaseContext(browser, ctx);
  }
}

async function findWidget(page) {
  for (const shortcut of findShortcuts) {
    await page.keyboard.press(shortcut);
    try {
      await page.waitForSelector(findInputSelector, { state: 'visible', timeout: 1500 });
      return { opened: true, shortcut };
    } catch {
      /* try the next binding */
    }
  }
  return { opened: false, shortcut: null };
}

async function runFind(browser) {
  const ctx = await newPage(browser);
  try {
    const navT0 = Date.now();
    await ctx.page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationMs = Date.now() - navT0;
    const readyMs = await waitForReady(ctx.page);
    if (settleMs > 0) await ctx.page.waitForTimeout(settleMs);
    if (!findInputSelector || !findQuery) {
      return {
        mode: 'find',
        status: 'not_applicable',
        reason: 'probe has no find-input-selector/find-query for this host',
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        cap_ms: null,
        completion: null,
      };
    }
    const opened = await findWidget(ctx.page);
    if (!opened.opened) {
      return {
        mode: 'find',
        status: 'not_applicable',
        reason:
          'no find widget appears after ' +
          findShortcuts.join('/') +
          ' (selector ' +
          findInputSelector +
          ' not visible)',
        shortcuts_tried: findShortcuts,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        cap_ms: null,
        completion: null,
      };
    }
    const observedInterval = await frameInterval(ctx.page, { frames: 6 });
    await ctx.page.locator(findInputSelector).first().click({ timeout: 5000 });
    await ctx.page.evaluate(
      ({ countSel, matchSel, expected, query, inputSel }) => {
        const probe = (window.__findProbe = {
          first_at: null,
          complete_at: null,
          last: '',
          accepted_text: '',
          prefix_text: '',
          prefixTexts: new Set(),
          scheduling: false,
          expected: expected,
          query: query,
          inputSel: inputSel,
        });
        const input = inputSel ? document.querySelector(inputSel) : null;
        const read = () => {
          const el = countSel ? document.querySelector(countSel) : null;
          const text = el ? (el.textContent || '').trim() : '';
          const matches = matchSel ? document.querySelectorAll(matchSel).length : null;
          return { text, matches };
        };
        const total = (text, matches) => {
          if (typeof matches === 'number') return matches;
          const numbers = (text.match(/\d+/g) || []).map(Number);
          return numbers.length ? Math.max.apply(null, numbers) : null;
        };
        // Completion and first-match are the full query's own count text.
        // A reply scheduled while the input was still a prefix is not that
        // response, even if it arrives after the input already shows the query.
        const notePrefix = (text) => {
          if (!text) return;
          probe.prefixTexts.add(text);
          probe.prefix_text = text;
        };
        const noteFull = (text) => {
          if (!text) return;
          const count = total(text, read().matches);
          const matchesExpected = probe.expected === null || (count !== null && count === probe.expected);
          if (!matchesExpected) return;
          probe.last = text;
          probe.accepted_text = text;
          const now = performance.now();
          if (probe.first_at === null) probe.first_at = now;
          if (probe.complete_at === null) probe.complete_at = now;
        };
        const nativeSetTimeout = window.setTimeout;
        const origTimeout = nativeSetTimeout.bind(window);
        // Capture runs before the page's element listener. A microtask queued
        // there runs before that listener on this input path, so the flag stays
        // up until bubble. Timers from later tasks are not a search response.
        const arm = (event) => {
          if (input && event.target === input) probe.scheduling = true;
        };
        const disarm = (event) => {
          if (!input || event.target !== input) return;
          const value = input.value;
          const text = read().text;
          if (value !== probe.query) notePrefix(text);
          else if (text && !probe.prefixTexts.has(text)) noteFull(text);
          probe.scheduling = false;
        };
        window.addEventListener('input', arm, true);
        window.addEventListener('input', disarm, false);
        window.setTimeout = function (fn, delay) {
          const extra = Array.prototype.slice.call(arguments, 2);
          const valueAtSchedule = input && typeof input.value === 'string' ? input.value : '';
          const fromInput = probe.scheduling === true;
          if (typeof fn !== 'function') return origTimeout.apply(window, arguments);
          return origTimeout(function () {
            const before = read().text;
            const result = fn.apply(this, extra);
            const after = read().text;
            if (!fromInput) return result;
            if (valueAtSchedule === probe.query) noteFull(after);
            else if (after && after !== before) notePrefix(after);
            return result;
          }, delay);
        };
        probe.stop = () => {
          window.setTimeout = nativeSetTimeout;
        };
      },
      {
        countSel: findCountSelector,
        matchSel: findMatchSelector,
        expected: findExpected,
        query: findQuery,
        inputSel: findInputSelector,
      },
    );
    const inputPageMs = await ctx.page.evaluate(() => performance.now());
    await ctx.page.keyboard.type(findQuery, { delay: 0 });
    const waitStarted = Date.now();
    let completion = 'event';
    try {
      await ctx.page.waitForFunction(
        () => {
          const probe = window.__findProbe;
          if (!probe) return false;
          if (probe.check) probe.check();
          return probe.complete_at !== null && probe.complete_at !== undefined;
        },
        null,
        { timeout: Math.min(timeoutMs, 10000), polling: 'raf' },
      );
    } catch {
      completion = 'no_event';
    }
    const completionWaitMs = Date.now() - waitStarted;
    const observed = await ctx.page.evaluate(() => {
      const probe = window.__findProbe || {};
      const out = {
        first_match_ms: probe.first_at === null || probe.first_at === undefined ? null : probe.first_at,
        search_complete_ms: probe.complete_at === null || probe.complete_at === undefined ? null : probe.complete_at,
        last_count_text: probe.accepted_text || '',
      };
      if (probe.stop) probe.stop();
      return out;
    });
    const delta = (value) => (value === null ? null : value - inputPageMs);
    const eventCompleted = completion === 'event';
    return {
      mode: 'find',
      status: eventCompleted ? 'measured' : 'unverified',
      frame_interval_ms: observedInterval.median_ms,
      completion,
      cap_ms: null,
      completion_wait_ms: completionWaitMs,
      shortcut: opened.shortcut,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      query: findQuery,
      expected_matches: findExpected,
      first_match_ms: eventCompleted ? delta(observed.first_match_ms) : null,
      search_complete_ms: eventCompleted ? delta(observed.search_complete_ms) : null,
      observed_count_text: observed.last_count_text,
      input_page_ms: inputPageMs,
      page_errors: ctx.errors,
      reason: eventCompleted ? null : 'find widget did not acknowledge the query on its own event',
    };
  } finally {
    await releaseContext(browser, ctx);
  }
}

const browser = await launch();
try {
  let result;
  if (mode === 'load') result = await runLoad(browser);
  else if (mode === 'scale') result = await runScale(browser);
  else if (mode === 'reflow') result = await runReflow(browser);
  else result = await runFind(browser);
  // Lax layer (owner 2026-11-11): every payload discloses the load timeout used.
  process.stdout.write(JSON.stringify({ ...result, load_timeout_ms: timeoutMs }));
} catch (error) {
  process.stdout.write(
    JSON.stringify({
      mode,
      status: 'probe_error',
      reason: String(error && error.message ? error.message : error).slice(0, 500),
    }),
  );
  process.exitCode = 1;
} finally {
  await browser.close();
}
