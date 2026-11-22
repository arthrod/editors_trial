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
 *   reflow  Enter keydown (page clock) to the acked frame at or after the
 *           first recorded frame in which the anchor moved — never the edit
 *           confirmation's return time. Layout reads timestamped inside that
 *           window (the recorder's per-frame anchor-top read, and any census
 *           read that landed before the frame) are reported
 *           (layout_reads_during_window, forced_layout_ms). Reads before
 *           Enter and reads after the frame are not called in-window.
 *           Nothing is claimed excluded. Page.startScreencast frames are
 *           acked via the witness recorder (Page.screencastFrame).
 *           frame_source: 'cdp_screencast'.
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
  framesFrom,
  nextFrameSeq,
  pageClock,
  detectTimestampKind,
  diffRatio,
  getRecorder,
  injectCaretMask,
  loadPlaywright,
  stopRecorder,
  WEBGL_UNMASK_FLAG,
  witnessFrame,
  rememberDecoded,
} from './witness.mjs';
import { normalizeDocumentText } from './document_text_normalize.mjs';
import { openingContentVerdict } from './perf_model_text.mjs';
import { bindModelSurfaceClock } from './surface_clock.mjs';
import { hasDocumentTextSurface, readAndGateDocumentText } from './edit_surface.mjs';
import { startChromeTrace, stopChromeTrace } from './chrome_trace.mjs';
import { editorPage, frameClockOffsetMs } from './editor_frame.mjs';
import {
  C12_NO_PARAGRAPH_GEOMETRY,
  LIST_MODEL_PARAGRAPHS,
  PICK_ANCHOR_BELOW,
  ANCHOR_REFIND_CONTEXT_OK,
  ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC,
  REFIND_ANCHOR,
  REFIND_ANCHOR_PAGE_SRC,
  C12_ANCHOR_BY_TEXT_PAGE_SRC,
  C12_FRAME_TIE_PAGE_SRC,
  C12_SCROLL_CARET_PAGE_SRC,
  C12_BLOCK_ENTRIES_PAGE_SRC,
  C12_BLOCK_TEXT_PAGE_SRC,
  C12_LOCATE_PAGE_SRC,
  C12_IDENTITY_DIAGNOSTIC_PAGE_SRC,
  C12_CARET_SELECTION_PAGE_SRC,
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
import { C14_COPY_WAIT_MS, readC14WholeText } from './c14_whole_text.mjs';

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
const c12CaretText = typeof opt['c12-caret-text'] === 'string' ? opt['c12-caret-text'] : '';
const c12AnchorText = typeof opt['c12-anchor-text'] === 'string' ? opt['c12-anchor-text'] : '';
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
  return rememberDecoded(recorder, frame, decoded);
}

async function resolveInkRegionDevice(page, frameDecoded) {
  let rect = await page
    .evaluate(() => {
      const fn = window.__docProbeSurface;
      if (typeof fn !== 'function') return null;
      const surface = fn('screencast_ink');
      return surface && surface.rect ? surface.rect : null;
    })
    .catch(() => null);
  if (!rect || !(rect.width > 0) || !(rect.height > 0)) return { scoped: false, rect_device: null, error: 'no region rect' };
  // A screencast frame can only ever contain viewport pixels, so the
  // comparable region is inherently viewport-bound (#174): intersect before
  // the device rect so the settled screenshot clip and every screencast crop
  // cover the same pixels. Usable then certifies the first viewport, and the
  // payload discloses it.
  const rectUnclamped = rect;
  const viewport = await page
    .evaluate(() => ({ width: window.innerWidth, height: window.innerHeight }))
    .catch(() => null);
  let clamped = false;
  if (viewport && viewport.width > 0 && viewport.height > 0) {
    const x = Math.max(0, Math.min(rect.x, viewport.width));
    const y = Math.max(0, Math.min(rect.y, viewport.height));
    const right = Math.max(x, Math.min(rect.x + rect.width, viewport.width));
    const bottom = Math.max(y, Math.min(rect.y + rect.height, viewport.height));
    clamped =
      x !== rect.x || y !== rect.y ||
      right !== rect.x + rect.width || bottom !== rect.y + rect.height;
    rect = { x, y, width: right - x, height: bottom - y };
  }
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
  return {
    scoped: true, rect_device: device, rect_css: rect,
    rect_css_unclamped: clamped ? rectUnclamped : null,
    clamped_to_viewport: clamped, dpr, error: null,
  };
}

/** Crop in device pixels; inset excludes four CSS pixels of border/chrome. */
function cropInkRegion(decoded, region, inset = 0) {
  if (!decoded) return null;
  // Clamp to the frame first, then inset: a region crossing the frame edge
  // keeps the same inset as the settled reference, so both crops carry the
  // same dimensions (#174).
  const x = Math.max(0, Math.round(region.x)) + inset;
  const y = Math.max(0, Math.round(region.y)) + inset;
  const right = Math.min(decoded.width, Math.round(region.x + region.width)) - inset;
  const bottom = Math.min(decoded.height, Math.round(region.y + region.height)) - inset;
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
    // A sequence cursor, never an array index: the recorder keeps only its last frames (#202).
    for (const frame of framesFrom(recorder, checked)) {
      checked = frame.seq + 1;
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
    if (checked < nextFrameSeq(recorder)) continue;
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
    baseline, ink_frame: candidate.frame, reason: null,
    region_clamped_to_viewport: scope.clamped_to_viewport === true,
    region_css: scope.rect_css,
    region_unclamped_css: scope.rect_css_unclamped };
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

// page -> performance.now() when its ready condition held (C11's model-host fallback).
const readyPageClock = new WeakMap();

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
  // The ready instant on the page clock, before wait_after_ready: the
  // duration returned below is on another clock (review D, docen C11).
  readyPageClock.set(page, await page.evaluate(() => performance.now()).catch(() => null));
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
const INIT_SCRIPT = ({ docSel, pageSel, minTextChars: minChars, signal, documentSelector: documentSel, textWaitBudgetMs, canvasReadyExpr }) => {
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
    docTextScanMs: null,
    usableSignal: recorded,
    // canvas_pixel with the editor's ready condition (#185 review): the first
    // drawn canvas at the first ink frame (the empty page when the editor is
    // not yet ready), and whether the usable frame shows something else.
    canvasInkBaseline: null,
    canvasInkBaselineReady: null,
    canvasInkChanged: null,
  });
  const canvasInkHash = () => {
    const nodes = docSel ? Array.from(document.querySelectorAll(docSel)) : [];
    for (const el of nodes) {
      if (typeof HTMLCanvasElement === 'undefined' || !(el instanceof HTMLCanvasElement)) continue;
      const w = el.width || 0;
      const h = el.height || 0;
      if (w < 1 || h < 1) continue;
      let data = null;
      try {
        const g = el.getContext('2d');
        data = g && typeof g.getImageData === 'function' ? g.getImageData(0, 0, w, h).data : null;
      } catch {
        data = null;
      }
      if (!data) continue;
      // FNV-1a over the whole first page canvas; null when it holds no opaque
      // ink (a cleared canvas is not the document).
      let hash = 2166136261;
      let ink = false;
      for (let i = 0; i < data.length; i += 4) {
        const a = data[i + 3];
        if (!ink && a > 16 && (data[i] < 250 || data[i + 1] < 250 || data[i + 2] < 250)) ink = true;
        for (let k = 0; k < 4; k++) {
          hash ^= data[i + k];
          hash = Math.imul(hash, 16777619) >>> 0;
        }
      }
      return ink ? w + 'x' + h + ':' + hash : null;
    }
    return null;
  };
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
  window.__docProbeSurface = (which, { timingOnly = false } = {}) => {
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
    // ownText: the element's text when the caller already read it (#206: the
    // walk ran twice per element, once for timing and once for content).
    const take = (el, text, ownText = null) => {
      canvasPresent ||= el.tagName === 'CANVAS' || Boolean(el.querySelector('canvas'));
      contentChunks.push(ownText === null ? elementText(el) : ownText);
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
        for (const el of root.querySelectorAll(selector)) {
          const text = elementText(el);
          take(el, text, text);
        }
      }
    } else {
      const nodes = selector ? Array.from(document.querySelectorAll(selector)) : [];
      if (which === 'canvas_pixel') {
        for (const el of nodes) {
          if (!canvasDrawnEl(el)) continue;
          take(el, 'drawn');
        }
      } else {
        for (const el of nodes) {
          const text = elementText(el);
          take(el, text, text);
        }
      }
    }
    // Opening headings sit outside paragraph selectors (plate h1.editor-heading,
    // docxodus h1.docx-Heading1, genoffice h1). They belong to the content oracle
    // only. The timing surface stays the selector's own boxes.
    // Linear in the page (#206). The scan it replaces asked every ancestor of
    // every matched node for its headings and tested each heading against every
    // matched node: on Plate's 250,000-word page it ran about 1,140 s inside a
    // load whose own scripts ran 21 s. Here every element is looked at a bounded
    // number of times whatever the nesting: the ancestors the old scan would
    // have asked are numbered in the order it asked them, each heading takes the
    // lowest number among its own ancestors (answers are remembered per
    // element), and the headings are sorted by that number, then by document
    // order. Same headings, same order. No selector is evaluated against a
    // heading, so a selector with :scope means what it meant for the page.
    const openingHeadingElements = () => {
      if (!selector) return [];
      const matched = Array.from(document.querySelectorAll(selector));
      if (!matched.length) return [];
      const matchedSet = new Set(matched);
      const firstAsk = new Map(); // ancestor -> when the old scan first asked it
      const holdsMatched = new Set(); // every strict ancestor of a matched node
      let order = 0;
      let lastParent = null;
      for (const node of matched) {
        const first = node.parentElement;
        if (first === lastParent) continue; // the same chain as the node before
        lastParent = first;
        let parent = first;
        for (let depth = 0; parent && depth < 6; depth += 1, parent = parent.parentElement) {
          if (!firstAsk.has(parent)) { firstAsk.set(parent, order); order += 1; }
        }
        for (let up = first; up && !holdsMatched.has(up); up = up.parentElement) holdsMatched.add(up);
      }
      // One answer per element, found by walking up to the nearest element
      // already answered: each element is walked from once.
      const remembered = (memo, own, join, start, el) => {
        const chain = [];
        let node = el;
        while (node && !memo.has(node)) { chain.push(node); node = node.parentElement; }
        let value = node ? memo.get(node) : start;
        for (let k = chain.length - 1; k >= 0; k -= 1) {
          value = join(value, own(chain[k]));
          memo.set(chain[k], value);
        }
        return value;
      };
      const askedMemo = new Map();
      const askedAt = (el) => remembered(askedMemo, (node) => (firstAsk.has(node) ? firstAsk.get(node) : Infinity), Math.min, Infinity, el);
      const insideMemo = new Map();
      const insideMatched = (el) => remembered(insideMemo, (node) => matchedSet.has(node), (a, c) => a || c, false, el);
      const found = [];
      let index = 0;
      for (const heading of document.querySelectorAll('h1,h2,h3,h4,h5,h6')) {
        index += 1;
        const tag = heading.tagName || '';
        if (tag.length !== 2 || tag[0] !== 'H' || tag[1] < '1' || tag[1] > '6') continue;
        const at = heading.parentElement ? askedAt(heading.parentElement) : Infinity;
        if (at === Infinity) continue; // under no ancestor the old scan asked
        if (insideMatched(heading) || holdsMatched.has(heading)) continue;
        found.push({ heading, at, index });
      }
      found.sort((x, y) => x.at - y.at || x.index - y.index);
      return found.map((entry) => entry.heading);
    };
    window.__docProbeOpeningHeadings = openingHeadingElements;
    const openingHeadings = () => openingHeadingElements().map((heading) => elementText(heading)).filter(Boolean).join(' ');
    const text = chunks.join(' ').replace(/\s+/g, ' ').trim();
    const rect = n
      ? excludeMarker({ x: minX, y: minY, width: maxX - minX, height: maxY - minY })
      : null;
    state.documentSelector = selector || null;
    state.surfaceText = text;
    return {
      text, chars: text.length, rect, selector: selector || null,
      // The load tick asks for the character count only (#206 review): the content
      // oracle's text is not built inside the timed interval.
      documentText: timingOnly ? null : [openingHeadings(), contentChunks.join(' ')].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim(), canvasPresent,
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
      const scanFrom = performance.now();
      const surface = window.__docProbeSurface(signal, { timingOnly: true });
      // What the probe's own read of the page cost: kept only for the tick that finds
      // the text (codex review), where it ends inside the timed interval.
      const scanMs = performance.now() - scanFrom;
      const chars = signal === 'canvas_pixel' ? (surface.chars > 0 ? 1 : 0) : surface.chars;
      // A canvas holds no text to match against the document, and an editor
      // paints its empty page (margin marks) before the import finishes. For
      // canvas_pixel the usable frame is the first one in which the editor's
      // own ready condition holds and the canvas has ink (#185).
      let canvasDocumentReady = true;
      if (signal === 'canvas_pixel' && canvasReadyExpr) {
        try {
          // eslint-disable-next-line no-eval
          canvasDocumentReady = Boolean((0, eval)(canvasReadyExpr));
        } catch {
          canvasDocumentReady = false;
        }
      }
      // canvas-editor flips its import flag a frame or two before its lazy
      // render draws the page, and its empty page already has ink (#185
      // review). With a ready condition, the usable frame is the first one
      // after the flag whose first page canvas holds opaque ink that differs
      // from the empty page seen before the flag.
      const canvasGated = signal === 'canvas_pixel' && Boolean(canvasReadyExpr);
      let canvasShowsDocument = true;
      if (canvasGated && chars > 0) {
        const pageHash = state.canvasInkBaseline === null || canvasDocumentReady ? canvasInkHash() : null;
        if (state.canvasInkBaseline === null && !canvasDocumentReady && pageHash !== null) {
          state.canvasInkBaseline = pageHash;
        }
        canvasShowsDocument = pageHash !== null && pageHash !== state.canvasInkBaseline;
      }
      if ((signal === 'canvas_pixel' && chars > 0 && canvasDocumentReady && canvasShowsDocument) || (signal !== 'canvas_pixel' && chars >= minChars)) {
        state.docTextAt = performance.now();
        state.docTextCharsAt = chars;
        state.docTextScanMs = scanMs;
        // True: an empty page was seen before the flag and the usable frame differs
        // from it. Null: the editor was ready at its first ink frame.
        if (canvasGated) state.canvasInkChanged = state.canvasInkBaseline !== null ? true : null;
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
  // OnlyOffice's document calls go to its editor frame; every other editor's page is itself.
  const page = editorPage(await context.newPage(), editorId);
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
    canvasReadyExpr: usableSignal === 'canvas_pixel' ? readyJs : '',
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

async function stateSnapshot(page, { noCopy = false } = {}) {
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
        // #206: the probe's own page read in the tick that found the text (inside the timed interval).
        probe_scan_ms_at_text: typeof s.docTextScanMs === 'number' ? s.docTextScanMs : null,
        canvas_ink_changed: typeof s.canvasInkChanged === 'boolean' ? s.canvasInkChanged : null,
        page_count_at_first: s.pageCountAtFirst === null || s.pageCountAtFirst === undefined ? null : s.pageCountAtFirst,
        page_count: pageSel ? document.querySelectorAll(pageSel).length : null,
        page_text_chars: pageEl ? (pageEl.textContent || '').trim().length : null,
        document_text_chars,
        document_text: docText.slice(0, 4000),
        // C14's I01-I03 fixture sits at the document's end, past any 4,000-character head (#181).
        document_text_tail: docText.slice(-4000),
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
    snap.document_text_tail = gated.text.slice(-4000);
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
      // #196: a select_all_copy surface reads the clipboard from the driver;
      // the same bound C14's whole-text read takes.
      copyWaitMs: opt['c14-copy-wait-ms'] !== undefined ? Number(opt['c14-copy-wait-ms']) : null,
      noCopy,
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
    const readyPageMs = readyPageClock.get(ctx.page) ?? null;
    at = bindModelSurfaceClock({ at, inkAt, firstElementMs: snap.first_element_ms ?? null, readyPageMs });
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
  // An editor that runs in a frame of its host page (OnlyOffice) is read on the
  // frame's clock; C11 counts from the host page's navigation, so each page-clock
  // time below moves to the host page's clock. 0 for every other editor.
  const originOffset = await frameClockOffsetMs(ctx.page, editorId);
  const onHostClock = (value) => (typeof value === 'number' && originOffset ? value + originOffset : value);
  const frameAt = at; // the deltas below are differences on one clock
  if (originOffset) {
    at = onHostClock(at);
    facts = { ...facts, presented_frame_ms: onHostClock(facts.presented_frame_ms) };
  }
  return {
    mode: 'load',
    driver: 'playwright',
    url,
    navigation_ms: navigationMs,
    ready_ms: readyMs,
    frame_clock_offset_ms: originOffset || null,
    paints: originOffset ? paints.map((row) => ({ ...row, start_ms: onHostClock(row.start_ms) })) : paints,
    fcp_ms: onHostClock(fcp),
    first_element_ms: onHostClock(snap.first_element_ms),
    canvas_ink_changed: snap.canvas_ink_changed,
    first_element_info: snap.first_element_info,
    first_element_selector: pageSelector || docSelector,
    document_text_at_ms: at,
    // #206: what the probe's own read of the page cost in the tick that found the text.
    probe_scan_ms_at_text: snap.probe_scan_ms_at_text ?? null,
    usable_ms: at,
    usable_signal: (surface && surface.signal) || SIGNAL_NAME[usableSignal],
    first_element_delta_from_fcp_ms: fcp !== null && snap.first_element_ms !== null ? snap.first_element_ms - fcp : null,
    document_text_ms_delta_from_fcp_ms: fcp !== null && frameAt !== null ? frameAt - fcp : null,
    page_model: pageModel,
    page_count: snap.page_count,
    page_count_at_first: snap.page_count_at_first,
    document_text_chars: snap.document_text_chars,
    document_text: snap.document_text,
    document_text_tail: snap.document_text_tail,
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
    region_clamped_to_viewport: (surface && surface.region_clamped_to_viewport) ?? null,
    region_css: (surface && surface.region_css) ?? null,
    region_unclamped_css: (surface && surface.region_unclamped_css) ?? null,
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
    readyPageClock.delete(ctx.page); // a reused page never carries the previous ready instant
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
        region_clamped_to_viewport: ink.region_clamped_to_viewport ?? null,
        region_css: ink.region_css ?? null,
        region_unclamped_css: ink.region_unclamped_css ?? null,
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

/**
 * C14 stage log (Arthur, 2026-11-13: "if it keeps timing out, explain where").
 * Each stage of a scale sample is written to stderr as it starts and ends, and
 * the finished stages ride in the payload as `load_stages`. A failure names
 * the stage it hit; if our watchdog kills the probe, benchmark_document.py
 * reads the same lines from stderr.
 */
const scaleStages = [];
let scaleStage = null;

function stageDone() {
  if (!scaleStage) return;
  const ms = Date.now() - scaleStage.t0;
  scaleStages.push({ stage: scaleStage.stage, ms });
  process.stderr.write(`[c14-stage] ${scaleStage.stage} done ${ms} ms\n`);
  scaleStage = null;
}

function stageStart(name) {
  stageDone();
  scaleStage = { stage: name, t0: Date.now() };
  process.stderr.write(`[c14-stage] ${name} start\n`);
}

function stageFailure() {
  if (!scaleStage) return null;
  const done = scaleStages.map((s) => `${s.stage} ${s.ms} ms`).join(', ') || 'none';
  return `stage ${scaleStage.stage} failed after ${Date.now() - scaleStage.t0} ms; done: ${done}`;
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
    stageStart('navigation');
    const navT0 = Date.now();
    await ctx.page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationMs = Date.now() - navT0;
    stageStart('ready');
    const readyMs = await waitForReady(ctx.page);
    if (settleMs > 0) await ctx.page.waitForTimeout(settleMs);
    stageStart('surface');
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
      surface = {
        at_ms: ink.at_ms, chars: ink.at_ms === null ? null : 1, signal: ink.signal,
        region_clamped_to_viewport: ink.region_clamped_to_viewport ?? null,
        region_css: ink.region_css ?? null,
        region_unclamped_css: ink.region_unclamped_css ?? null,
      };
      surfaceReason = ink.reason;
    } else {
      surface = await waitForSurface(ctx.page);
    }
    stageStart('witness');
    // C14's frame witness and its own whole-text read follow: no select-all + copy here (#196).
    const snap = await stateSnapshot(ctx.page, { noCopy: true });
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
        // #203: this witness classifies (did damage follow load inside the
        // window?); a frame recorded while a busy page delayed the scan, past
        // the window and its clock error, is not damage inside it.
        strictWindow: true,
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
    // Every timed step is over: ask the editor for its whole document (#183).
    stageStart('c14_text_read');
    const c14Text = await readC14WholeText(ctx.page, editorId, {
      waitMs: opt['c14-copy-wait-ms'] !== undefined ? Number(opt['c14-copy-wait-ms']) : C14_COPY_WAIT_MS,
    });
    stageDone();
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
      canvas_ink_changed: snap.canvas_ink_changed,
      page_model: pageModel,
      page_count: snap.page_count,
      document_text_chars: snap.document_text_chars,
      document_text: snap.document_text,
      document_text_tail: snap.document_text_tail,
      c14_text: c14Text,
      load_stages: scaleStages.slice(),
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
      region_clamped_to_viewport: surface.region_clamped_to_viewport ?? null,
      region_css: surface.region_css ?? null,
      region_unclamped_css: surface.region_unclamped_css ?? null,
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
          : editorId === 'onlyoffice'
            ? '#id_viewer in its editor frame (OnlyOffice paints each page into one <canvas>)'
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
        forced_layout_ms: 0,
        layout_reads_during_window: 0,
        anchor_frames: 0,
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
          forced_layout_ms: 0,
          layout_reads_during_window: 0,
          anchor_frames: 0,
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
          forced_layout_ms: 0,
          layout_reads_during_window: 0,
          anchor_frames: 0,
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
      caretText: c12CaretText,
      anchorText: c12AnchorText,
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
    const scrollSettleMs = settleMs > 0 ? settleMs : 100;
    const scrollCaretParagraph = async () =>
      ctx.page.evaluate(
        ({ scrollSrc, editorId, docSel, excludeSel, caretText }) => {
          let scrollCaret = null;
          try {
            // eslint-disable-next-line no-eval
            scrollCaret = (0, eval)(`(function(){ ${scrollSrc}; return c12ScrollCaretIntoView; })()`);
          } catch {
            scrollCaret = null;
          }
          if (typeof scrollCaret !== 'function') {
            return {
              ok: false,
              block: 'center',
              inline: 'nearest',
              behavior: 'instant',
              reason: 'caret scroll unavailable',
            };
          }
          return scrollCaret(editorId || '', docSel, excludeSel || '', caretText, 1);
        },
        {
          scrollSrc: C12_SCROLL_CARET_PAGE_SRC,
          editorId: editorId || '',
          docSel: reflowSel,
          excludeSel: excludeSelEarly,
          caretText: c12CaretText || (bodyCaret && bodyCaret.caretText) || '',
        },
      );
    // The nearest scroll inside the click leaves the next paragraph below
    // the fold. The shared center scroll is the same for every editor. The
    // caret placement's own scroll then runs for about 100 ms and undoes the
    // first call, so the probe waits out that settle and issues the same call
    // again. The snapshot reads the second call. Neither call is inside the
    // measured window.
    const centerScroll = async () => {
      let scroll = await scrollCaretParagraph();
      if (scroll && scroll.ok === true) {
        const first = scroll;
        await ctx.page.waitForTimeout(scrollSettleMs);
        const second = await scrollCaretParagraph();
        scroll = {
          ...(second && typeof second === 'object' ? second : first),
          top_before: first.top_before,
          top_after_first: first.top_after,
          top_after: second && typeof second.top_after === 'number' ? second.top_after : first.top_after,
          settle_ms: scrollSettleMs,
          calls: 2,
        };
      }
      return scroll;
    };
    const placementRefusal = (placement, scroll) => ({
      mode: 'reflow',
      driver: 'playwright',
      url,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      error: (placement && placement.reason) || 'c12_body_caret_unavailable',
      caret_placement: placement || null,
      caret_scroll: scroll || null,
      forced_layout_ms: 0,
      layout_reads_during_window: 0,
      anchor_frames: 0,
      page_errors: ctx.errors,
    });
    let bodyCaret = await placeC12BodyCaret(ctx.page, editorId, reflowSel, excludeSelEarly, {
      caretText: c12CaretText,
      anchorText: c12AnchorText,
    });
    if (!bodyCaret || bodyCaret.ok !== true) {
      // One retry, after the shared center scroll settles. The second click
      // uses the same glyph point, recomputed on the settled layout.
      if (bodyCaret && bodyCaret.reason === 'caret_not_at_paragraph_start') {
        const retryScroll = await centerScroll();
        const retry = await placeC12BodyCaret(ctx.page, editorId, reflowSel, excludeSelEarly, {
          caretText: c12CaretText,
          anchorText: c12AnchorText,
        });
        if (retry && retry.ok === true) {
          bodyCaret = {
            ...retry,
            retried: true,
            first_click_hit: bodyCaret.click_hit || null,
            first_caret_verify: bodyCaret.caret_verify || null,
          };
        } else {
          const placement =
            retry && typeof retry === 'object'
              ? { ...retry }
              : { ok: false, reason: 'caret_not_at_paragraph_start' };
          placement.retried = true;
          placement.first_click_hit = bodyCaret.click_hit || null;
          placement.first_caret_verify = bodyCaret.caret_verify || null;
          return placementRefusal(placement, retryScroll);
        }
      } else {
        return placementRefusal(bodyCaret, null);
      }
    }
    let caretScroll = await centerScroll();

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
      locateSrc: C12_LOCATE_PAGE_SRC,
      caretText: c12CaretText,
      anchorText: c12AnchorText,
      selectionSrc: C12_CARET_SELECTION_PAGE_SRC,
    });
    if (!before.ok) {
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        error: before.reason,
        caret_placement: bodyCaret || null,
        before,
        caret_scroll: caretScroll,
        forced_layout_ms: 0,
        layout_reads_during_window: 0,
        anchor_frames: 0,
      };
    }

    const frameDeadline = Date.now() + 1500;
    while (ctx.recorder.frames.length === 0 && Date.now() < frameDeadline) await sleep(10);
    const baseline = ctx.recorder.frames.length ? ctx.recorder.frames[ctx.recorder.frames.length - 1] : null;

    const inputMark = await ctx.page.evaluate(({ findSrc, entriesSrc }) => {
      window.__c12InputMs = null;
      window.__c12MovedAnchorEl = null;
      // The measured window opens at the Enter keydown and ends at the first
      // presented frame in which the anchor moved. The edit-confirmation poll
      // is a validity check AFTER the fact; its duration is never part of the
      // sample. Record the anchor's top once per rendered frame starting
      // before Enter. A re-render that replaces the node leaves the remembered
      // element disconnected. Follow the new node by the anchor paragraph's
      // own text (the fixture anchor string, or the painted text on a host
      // that has none). Do not call REFIND_ANCHOR here: that census cannot
      // resolve until the caret "x" exists, so the recorded move would be the
      // text-commit time, and it reads every block's rect inside the window.
      // The text finder does not group lines that have no paragraph id,
      // because that grouping needs their rects. When the finder has no
      // element, one pass of the same census the after path uses resolves the
      // paragraph and the recorder holds that element. A later frame reads
      // only the held node, until it disconnects again. Those census rects
      // stay in the read log. A finder hit never takes this pass.
      // The recorder's own getBoundingClientRect on the matched block is real
      // work inside the window and is counted in __c12ProbeReadLog.
      window.__c12FrameLog = [];
      window.__c12FrameLogActive = false;
      window.__c12ProbeReadLog = [];
      window.__c12ProbeReadLogClosed = false;
      window.__c12PreInputMove = false;
      let findByText = null;
      try {
        // eslint-disable-next-line no-eval
        findByText = (0, eval)(`(function(){ ${findSrc}; return c12AnchorElementByText; })()`);
      } catch {
        findByText = null;
      }
      let blockEntries = null;
      try {
        // eslint-disable-next-line no-eval
        blockEntries = (0, eval)(`(function(){ ${entriesSrc}; return c12BlockEntries; })()`);
      } catch {
        blockEntries = null;
      }
      const normAnchor = (value) => {
        const collapsed = String(value || '').replace(/\s+/g, ' ').trim();
        return typeof collapsed.normalize === 'function' ? collapsed.normalize('NFC') : collapsed;
      };
      const anchorFromCensus = () => {
        if (typeof blockEntries !== 'function') return null;
        const want = normAnchor(window.__c12FixtureAnchorText || window.__c12AnchorText);
        if (!want) return null;
        let entries = [];
        try {
          entries = blockEntries(
            window.__c12EditorId || '',
            window.__c12DocSel,
            window.__c12ExcludeSel || '',
            (el) => normAnchor(el && (el.innerText || el.textContent)),
          );
        } catch {
          return null;
        }
        const hits = [];
        for (const entry of entries) {
          if (entry && normAnchor(entry.text) === want) hits.push(entry);
        }
        const occ = Number(window.__c12AnchorOccurrence);
        const picked = !Number.isFinite(occ) || occ < 1
          ? (hits.length === 1 ? hits[0] : null)
          : (hits[occ - 1] || null);
        return picked && picked.el ? picked.el : null;
      };
      const liveAnchor = () => {
        const kept = window.__c12AnchorEl;
        const sel = window.__c12DocSel;
        // A connected node that no longer matches the census selector has left
        // the paragraph list (stale.html strips .doc-paragraph and parks the
        // old node). Do not keep reading it. A node that still matches is the
        // pre-Enter anchor until the caret "x" exists, which is what lets
        // clock.html record the move before the confirm poll can resolve.
        const stillListed =
          kept &&
          kept.isConnected === true &&
          (typeof kept.matches !== 'function' || !sel || kept.matches(sel));
        if (stillListed) return kept;
        const anchorText = window.__c12FixtureAnchorText || window.__c12AnchorText;
        let found = null;
        if (typeof findByText === 'function') {
          found = findByText(
            window.__c12EditorId || '',
            sel,
            window.__c12ExcludeSel || '',
            anchorText,
            window.__c12AnchorOccurrence,
          );
        }
        if (!found) found = anchorFromCensus();
        if (found) window.__c12AnchorEl = found;
        return found || null;
      };
      const record = (frameTime) => {
        if (!window.__c12FrameLogActive) return;
        const el = liveAnchor();
        if (!el) {
          requestAnimationFrame(record);
          return;
        }
        const t0 = performance.now();
        const top = el.getBoundingClientRect().top;
        // t0 is taken after liveAnchor(), so on a loaded host it can fall past
        // the window that still contains this frame. frameT is that frame's clock.
        window.__c12ProbeReadLog.push({ t: t0, ms: performance.now() - t0, frameT: frameTime });
        window.__c12FrameLog.push({ t: frameTime, top, connected: el.isConnected === true });
        const input = window.__c12InputMs;
        const afterInput = typeof input === 'number' && typeof frameTime === 'number' && frameTime >= input;
        if (!afterInput) {
          // A settle before Enter is the baseline, not the sample. The frame
          // stays in the log and is ignored once the keydown stamp exists.
          const armedTop = window.__c12ArmedTop;
          if (typeof armedTop === 'number' && top > armedTop + 0.5) window.__c12PreInputMove = true;
          window.__c12AnchorTop = top;
          requestAnimationFrame(record);
          return;
        }
        const before = window.__c12AnchorTop;
        if (typeof before === 'number' && top > before + 0.5) {
          // First moved frame at or after Enter. Stop forcing further reads.
          // Keep this node so the after-path can refuse a sample whose frame
          // is not the anchor the census confirms.
          window.__c12MovedAnchorEl = el;
          window.__c12FrameLogActive = false;
          window.__c12ProbeReadLogClosed = true;
          return;
        }
        requestAnimationFrame(record);
      };
      // The census top can be a second stale. Re-read the anchor in this
      // turn, then arm. A move that the arm itself provokes lands in a
      // pre-Enter frame and becomes the baseline.
      const armedNow = liveAnchor();
      if (armedNow && typeof armedNow.getBoundingClientRect === 'function') {
        window.__c12AnchorTop = armedNow.getBoundingClientRect().top;
      }
      window.__c12ArmedTop = window.__c12AnchorTop;
      window.__c12FrameLogActive = true;
      requestAnimationFrame(record);
      document.addEventListener(
        'keydown',
        (event) => {
          if (event.key === 'Enter' && window.__c12InputMs === null) window.__c12InputMs = performance.now();
        },
        true,
      );
      return performance.now();
    }, {
      findSrc: C12_ANCHOR_BY_TEXT_PAGE_SRC,
      entriesSrc: C12_BLOCK_ENTRIES_PAGE_SRC,
    });
    // Frames are judged against the arm re-read (window.__c12ArmedTop), not
    // the earlier census top. Report that same number as before.anchor_top
    // so shift_px and the refusal name the baseline the frames used. The
    // census value stays on the trace as census_anchor_top.
    const armedTop = await ctx.page.evaluate(() =>
      typeof window.__c12ArmedTop === 'number' ? window.__c12ArmedTop : null,
    );
    if (before && typeof before === 'object') {
      before.census_anchor_top = before.anchor_top;
      if (typeof armedTop === 'number') before.anchor_top = armedTop;
    }
    // Stops the frame recorder and returns the layout accounting: every
    // getBoundingClientRect the probe caused since Enter, timestamped so the
    // report can bound them to the presented window when a frame exists.
    const stopC12Recorder = () =>
      ctx.page.evaluate(() => {
        window.__c12FrameLogActive = false;
        const log = Array.isArray(window.__c12ProbeReadLog) ? window.__c12ProbeReadLog : [];
        let read_ms = 0;
        for (const read of log) read_ms += read.ms;
        return {
          reads: log.length,
          read_ms,
          frames: Array.isArray(window.__c12FrameLog) ? window.__c12FrameLog.length : 0,
        };
      });
    // Reads and recorded frames with start <= t <= bound belong to the
    // measured window (Enter keydown -> presented frame). A null start or
    // bound leaves that side open: without a resolved frame every read is
    // reported, and a missing keydown stamp does not drop reads.
    const c12WindowReads = (startMs, boundMs) =>
      ctx.page.evaluate(({ start, bound }) => {
        const log = Array.isArray(window.__c12ProbeReadLog) ? window.__c12ProbeReadLog : [];
        const frames = Array.isArray(window.__c12FrameLog) ? window.__c12FrameLog : [];
        const inside = (t) => {
          if (typeof t !== 'number') return false;
          if (start !== null && t < start) return false;
          if (bound !== null && t > bound) return false;
          return true;
        };
        let reads = 0;
        let read_ms = 0;
        for (const read of log) {
          // Census rects have no frameT and stay on their own timestamp. A
          // frame with no paired read still leaves reads < frames.
          if (!(inside(read.t) || inside(read.frameT))) continue;
          reads += 1;
          read_ms += read.ms;
        }
        let frameCount = 0;
        for (const frame of frames) {
          if (inside(frame.t)) frameCount += 1;
        }
        return { reads, read_ms, total: log.length, frames: frameCount };
      }, { start: startMs, bound: boundMs });
    // Let an arm-time settle paint before Enter, so its frame is stamped
    // before the keydown and absorbed into the baseline. Same wait for
    // every editor. The sample still opens at the keydown.
    await ctx.page.evaluate(
      () =>
        new Promise((resolve) => {
          requestAnimationFrame(() => requestAnimationFrame(resolve));
        }),
    );
    await ctx.page.keyboard.press('Enter');
    await ctx.page.keyboard.type('x', { delay: 0 });
    // The confirm census reads one rect per block. Wait until the recorder
    // has the moved frame, or this bound, so that census is outside the
    // window. The bound is the old shift poll. It is not added to the sample.
    const moveDeadline = Date.now() + 4000;
    while (Date.now() < moveDeadline) {
      const closed = await ctx.page.evaluate(() => window.__c12ProbeReadLogClosed === true);
      if (closed) break;
      await sleep(16);
    }
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
          if (!snap || !docSel) return { ok: false, reason: 'anchor_identity_ambiguous', keys_landed_elsewhere: false };
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
          const beforeTexts = Array.isArray(snap.blockTexts) ? snap.blockTexts.map(norm) : [];
          const afterTexts = entries.map((entry) => norm(entry.text));
          const censusUnchanged =
            beforeTexts.length === afterTexts.length &&
            beforeTexts.every((text, index) => text === afterTexts[index]);
          if (verdict && verdict.ok === false) {
            let diagnose = null;
            let emptyWindow = null;
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
            try {
              // eslint-disable-next-line no-eval
              const windowFn = (0, eval)(`(function(){ ${diagSrc}; return c12EmptyInclusiveWindow; })()`);
              if (typeof windowFn === 'function') emptyWindow = windowFn(eid, docSel, excl || '', snap);
            } catch {
              emptyWindow = null;
            }
            // An unchanged census did not receive the keys. A changed census
            // that still fails identity is the keys landing somewhere else.
            return {
              ...verdict,
              identity_diagnostic: diagnose,
              empty_inclusive_window: emptyWindow,
              keys_landed_elsewhere: !censusUnchanged,
            };
          }
          return verdict;
        },
        {
          checkSrc: `${ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC}`,
          diagSrc: `${C12_IDENTITY_DIAGNOSTIC_PAGE_SRC}`,
          blockTextSrc: C12_BLOCK_TEXT_PAGE_SRC,
          entriesSrc: `${C12_BLOCK_ENTRIES_PAGE_SRC}`,
          eid: editorId || '',
          excl: excludeSel,
          docSel: reflowSel,
        },
      );
    if (!editSeen || editSeen.ok !== true) {
      const anchorOnEditMiss = await evaluateAnchorIdentity();
      // A confirm timeout is edit_not_observed. anchor_identity_ambiguous is
      // only for a census that changed, which is the keys landing somewhere
      // other than the caret paragraph's x-prefix.
      const landedElsewhere = Boolean(anchorOnEditMiss && anchorOnEditMiss.keys_landed_elsewhere);
      if (landedElsewhere) {
        const rec = await stopC12Recorder();
        return {
          mode: 'reflow',
          driver: 'playwright',
          url,
          navigation_ms: navigationMs,
          ready_ms: readyMs,
          before,
          caret_scroll: caretScroll,
          error: (anchorOnEditMiss && anchorOnEditMiss.reason) || 'anchor_identity_ambiguous',
          identity_diagnostic: (anchorOnEditMiss && anchorOnEditMiss.identity_diagnostic) || null,
          empty_inclusive_window: (anchorOnEditMiss && anchorOnEditMiss.empty_inclusive_window) || null,
          edit_confirmation: editSeen || null,
          moved: false,
          anchor_top_after: null,
          anchor_after_top: null,
          shift_px: null,
          window_excludes_forced_layout: false,
          forced_layout_ms: rec.read_ms,
          layout_reads_during_window: rec.reads,
          anchor_frames: rec.frames,
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
          let emptyWindow = null;
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
          if (snap) {
            try {
              // eslint-disable-next-line no-eval
              const windowFn = (0, eval)(`(function(){ ${diagSrc}; return c12EmptyInclusiveWindow; })()`);
              if (typeof windowFn === 'function') emptyWindow = windowFn(eid, docSel, excl || '', snap);
            } catch {
              emptyWindow = null;
            }
          }
          return { identity_diagnostic: diagnose, empty_inclusive_window: emptyWindow };
        },
        {
          diagSrc: `${C12_IDENTITY_DIAGNOSTIC_PAGE_SRC}`,
          blockTextSrc: C12_BLOCK_TEXT_PAGE_SRC,
          entriesSrc: `${C12_BLOCK_ENTRIES_PAGE_SRC}`,
          eid: editorId || '',
          excl: excludeSel,
          docSel: reflowSel,
        },
      );
      const rec = await stopC12Recorder();
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        before,
        caret_scroll: caretScroll,
        error: editSeen?.reason || 'edit_not_observed',
        identity_diagnostic: (identityDiagnostic && identityDiagnostic.identity_diagnostic) || null,
        empty_inclusive_window: (identityDiagnostic && identityDiagnostic.empty_inclusive_window) || null,
        edit_confirmation: editSeen || null,
        moved: false,
        anchor_top_after: null,
        anchor_after_top: null,
        shift_px: null,
        window_excludes_forced_layout: false,
        forced_layout_ms: rec.read_ms,
        layout_reads_during_window: rec.reads,
        anchor_frames: rec.frames,
        page_errors: ctx.errors,
      };
    }
    const anchorIdentity = await evaluateAnchorIdentity();
    if (anchorIdentity && anchorIdentity.ok === false) {
      const rec = await stopC12Recorder();
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        before,
        caret_scroll: caretScroll,
        error: anchorIdentity.reason || 'anchor_identity_ambiguous',
        identity_diagnostic: anchorIdentity.identity_diagnostic || null,
        empty_inclusive_window: anchorIdentity.empty_inclusive_window || null,
        moved: false,
        anchor_top_after: null,
        anchor_after_top: null,
        shift_px: null,
        window_excludes_forced_layout: false,
        forced_layout_ms: rec.read_ms,
        layout_reads_during_window: rec.reads,
        anchor_frames: rec.frames,
        page_errors: ctx.errors,
      };
    }
    const meter = await ctx.page.evaluate(() => ({
      input_page_ms:
        window.__c12InputMs === null || window.__c12InputMs === undefined ? null : window.__c12InputMs,
    }));
    const inputPageMs = meter.input_page_ms === null ? inputMark : meter.input_page_ms;
    // The sample end is the first recorded frame whose anchor top moved more
    // than 0.5 px — the frame's own timestamp, not the moment this poll
    // noticed it. The confirmation poll only proves the edit is the expected
    // x+paragraph shape. A move that paints after that proof (the late-reflow
    // host waits 800 ms) is still in the log because the recorder stays
    // armed. The 4000 ms bound is the previous shift poll's bound; it is not
    // added to the sample.
    const readRecordedShift = () =>
      ctx.page.evaluate(() => {
        const beforeTop = window.__c12AnchorTop;
        const log = Array.isArray(window.__c12FrameLog) ? window.__c12FrameLog : [];
        const input = window.__c12InputMs;
        if (typeof beforeTop === 'number') {
          for (const frame of log) {
            if (typeof input === 'number' && !(typeof frame.t === 'number' && frame.t >= input)) continue;
            if (typeof frame.top === 'number' && frame.top > beforeTop + 0.5) {
              return { moved: true, top: frame.top, at: frame.t, frames: log.length };
            }
          }
        }
        return {
          moved: false,
          top: log.length ? log[log.length - 1].top : null,
          at: null,
          frames: log.length,
        };
      });
    let shift = await readRecordedShift();
    if (!shift.moved) {
      const closed = await ctx.page.evaluate(() => window.__c12ProbeReadLogClosed === true);
      if (closed) shift = await readRecordedShift();
    }
    await ctx.page.evaluate(() => {
      window.__c12FrameLogActive = false;
    });
    if (!shift.moved) {
      const preInputMove = await ctx.page.evaluate(() => window.__c12PreInputMove === true);
      if (preInputMove) {
        const rec = await stopC12Recorder();
        return {
          mode: 'reflow',
          driver: 'playwright',
          url,
          navigation_ms: navigationMs,
          ready_ms: readyMs,
          before,
          caret_scroll: caretScroll,
          error: 'recorded_move_before_input',
          moved: false,
          anchor_top_after: null,
          anchor_after_top: null,
          shift_px: null,
          input_page_ms: inputPageMs,
          observed_shift_page_ms: null,
          window_excludes_forced_layout: false,
          forced_layout_ms: rec.read_ms,
          layout_reads_during_window: rec.reads,
          anchor_frames: rec.frames,
          page_errors: ctx.errors,
        };
      }
    }
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
      ({ docSel, anchorText, anchorTop, anchorOccurrence, refindSrc, blockTextSrc, tieSrc }) => {
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
        let refind = null;
        try {
          // eslint-disable-next-line no-eval
          refind = (0, eval)(`(function(){ ${refindSrc}; return REFIND_ANCHOR; })()`);
        } catch {
          refind = null;
        }
        // The remembered node counts only while refind says it is the census
        // entry at the resolved anchor index. Otherwise use that entry. A
        // failed refind is anchor_identity_ambiguous, not a measurement of
        // whatever node still happens to hold the anchor string.
        const found = typeof refind === 'function'
          ? refind(docSel, anchorText, anchorTop, norm, readBlock, anchorOccurrence)
          : null;
        let matchedBy = null;
        if (found && kept && found === kept) matchedBy = 'element';
        else if (found) matchedBy = 'text';
        const movedEl = window.__c12MovedAnchorEl || null;
        window.__c12ConfirmedAnchorEl = found || null;
        let tieNs = null;
        try {
          // eslint-disable-next-line no-eval
          tieNs = (0, eval)(
            `(function(){ ${tieSrc}; return { c12FrameTieDiagnostic, c12SameAnchorElement }; })()`,
          );
        } catch {
          tieNs = null;
        }
        const sameAnchor = tieNs && typeof tieNs.c12SameAnchorElement === 'function'
          ? tieNs.c12SameAnchorElement
          : null;
        const frameTied = typeof sameAnchor === 'function'
          ? sameAnchor(movedEl, found) === true
          : Boolean(found && movedEl && found === movedEl);
        let frameTie = null;
        if (!frameTied && tieNs && typeof tieNs.c12FrameTieDiagnostic === 'function') {
          frameTie = tieNs.c12FrameTieDiagnostic(movedEl, found);
        }
        return {
          top: found ? found.getBoundingClientRect().top : null,
          block_count: document.querySelectorAll(docSel).length,
          matched_by: matchedBy,
          identity_ok: Boolean(found),
          frame_tied: frameTied,
          frame_tie: frameTie,
        };
      },
      {
        docSel: reflowSel,
        anchorText: before.anchor_text,
        anchorTop: before.anchor_top,
        anchorOccurrence: before.anchor_occurrence,
        refindSrc: `${REFIND_ANCHOR_PAGE_SRC}`,
        blockTextSrc: C12_BLOCK_TEXT_PAGE_SRC,
        tieSrc: C12_FRAME_TIE_PAGE_SRC,
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
          let emptyWindow = null;
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
          try {
            // eslint-disable-next-line no-eval
            const windowFn = (0, eval)(`(function(){ ${diagSrc}; return c12EmptyInclusiveWindow; })()`);
            if (typeof windowFn === 'function') emptyWindow = windowFn(eid, docSel, excl || '', snapshot);
          } catch {
            emptyWindow = null;
          }
          return { ...verdict, identity_diagnostic: diagnose, empty_inclusive_window: emptyWindow };
        }
        const refusal = window.__c12AnchorRefusal || null;
        if (refusal) return { ok: false, reason: refusal };
        return verdict;
      },
      {
        checkSrc: `${ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC}`,
        diagSrc: `${C12_IDENTITY_DIAGNOSTIC_PAGE_SRC}`,
        blockTextSrc: C12_BLOCK_TEXT_PAGE_SRC,
        entriesSrc: `${C12_BLOCK_ENTRIES_PAGE_SRC}`,
        eid: editorId || '',
        excl: excludeSel,
        docSel: reflowSel,
      },
    );
    if (endIdentity && endIdentity.ok === false) {
      const rec = await stopC12Recorder();
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        before,
        caret_scroll: caretScroll,
        error: endIdentity.reason || 'anchor_identity_ambiguous',
        identity_diagnostic: endIdentity.identity_diagnostic || null,
        empty_inclusive_window: endIdentity.empty_inclusive_window || null,
        moved: false,
        anchor_top_after: null,
        anchor_after_top: null,
        shift_px: null,
        window_excludes_forced_layout: false,
        forced_layout_ms: rec.read_ms,
        layout_reads_during_window: rec.reads,
        anchor_frames: rec.frames,
        page_errors: ctx.errors,
      };
    }
    if (!after || after.identity_ok !== true) {
      const rec = await stopC12Recorder();
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        before,
        caret_scroll: caretScroll,
        error: 'anchor_identity_ambiguous',
        identity_diagnostic: (endIdentity && endIdentity.identity_diagnostic) || null,
        empty_inclusive_window: (endIdentity && endIdentity.empty_inclusive_window) || null,
        moved: false,
        anchor_top_after: null,
        anchor_after_top: null,
        shift_px: null,
        window_excludes_forced_layout: false,
        forced_layout_ms: rec.read_ms,
        layout_reads_during_window: rec.reads,
        anchor_frames: rec.frames,
        page_errors: ctx.errors,
      };
    }
    // The after-path confirmed an anchor by the census and the K/count gates.
    // The recorded frame has to be that same node. A text match that moved a
    // different block is not a sample.
    if (shift.moved && after.frame_tied !== true) {
      const rec = await stopC12Recorder();
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        before,
        caret_scroll: caretScroll,
        error: 'recorded_frame_not_confirmed_anchor',
        frame_tie: (after && after.frame_tie) || null,
        moved: false,
        anchor_top_after: null,
        anchor_after_top: null,
        shift_px: null,
        window_excludes_forced_layout: false,
        forced_layout_ms: rec.read_ms,
        layout_reads_during_window: rec.reads,
        anchor_frames: rec.frames,
        page_errors: ctx.errors,
      };
    }
    // shift.moved is a post-Enter frame over the arm baseline. The frame-tied
    // identity gate above is the other half of this flag. The after-census
    // top is not a second baseline: a scroll that puts the anchor back does
    // not veto a move the frames already recorded.
    const moved = Boolean(shift.moved) && after.frame_tied === true;
    const framePageMs = witness && witness.outcome === 'witnessed' ? witness.frame_page_ms : null;
    const raw = framePageMs === null ? null : framePageMs - inputPageMs;
    const presented = raw;
    // Reads inside the measured window are those up to the presented frame.
    // The bound keeps at least the recorded move frame's own read (two frame
    // intervals of slack cover the screencast-conversion error and the rAF
    // callback running after the frame's nominal timestamp).
    const readBound =
      framePageMs === null
        ? null
        : Math.max(framePageMs, (typeof shift.at === 'number' ? shift.at : 0) + 34);
    const windowReads = await c12WindowReads(
      typeof inputPageMs === 'number' ? inputPageMs : null,
      readBound,
    );
    return {
      mode: 'reflow',
      driver: 'playwright',
      url,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      before,
      caret_scroll: caretScroll,
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
      // In-window layout work is reported, never subtracted or claimed away.
      // The bound is Enter keydown through the presented frame, plus slack
      // for reads on their own clock (census rects). The recorder's paired
      // read is counted on its frame's time (frameT), so it is kept even when
      // its own stamp lands after the bound (#175).
      forced_layout_ms: windowReads.read_ms,
      window_excludes_forced_layout: false,
      presented_frame_raw_ms: raw,
      presented_frame_ms: presented,
      frames_total: witness ? witness.frames_total : ctx.recorder.frames.length,
      frames_after_shift_observed: witness ? witness.frames_after : 0,
      frame_source: 'cdp_screencast',
      clock_skew_ms: witness ? witness.clock_skew_ms : null,
      clock_skew_acceptable: witness ? witness.clock_skew_acceptable : null,
      witness,
      layout_reads_during_window: windowReads.reads,
      layout_reads_after_input: windowReads.total,
      anchor_frames: windowReads.frames,
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
      ({ countSel, matchSel, expected, query, inputSel, intervalReplies }) => {
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
        // OnlyOffice only (intervalReplies): its find bar starts one setInterval
        // on the first input and searches whatever the input holds 400 ms after
        // the last input (web-apps onInputSearchChange, 9.3.2); it never uses
        // setTimeout for it. A tick of an interval started from an input is a
        // reply to the text the input holds when that tick runs: the search it
        // runs reads that text. Other editors keep the setTimeout rule alone.
        const nativeSetInterval = window.setInterval;
        if (intervalReplies) {
          const origInterval = nativeSetInterval.bind(window);
          window.setInterval = function (fn, delay) {
            const extra = Array.prototype.slice.call(arguments, 2);
            const fromInput = probe.scheduling === true;
            if (typeof fn !== 'function' || !fromInput) return origInterval.apply(window, arguments);
            return origInterval(function () {
              const valueAtTick = input && typeof input.value === 'string' ? input.value : '';
              const before = read().text;
              const result = fn.apply(this, extra);
              const after = read().text;
              // Only a tick that changed the count answers anything; a full-query
              // reply equal to a prefix reply stays unmeasured, as with setTimeout.
              if (after && after !== before) {
                if (valueAtTick === probe.query && !probe.prefixTexts.has(after)) noteFull(after);
                else if (valueAtTick !== probe.query) notePrefix(after);
              }
              return result;
            }, delay);
          };
        }
        probe.stop = () => {
          window.setTimeout = nativeSetTimeout;
          window.setInterval = nativeSetInterval;
        };
      },
      {
        countSel: findCountSelector,
        matchSel: findMatchSelector,
        expected: findExpected,
        query: findQuery,
        inputSel: findInputSelector,
        intervalReplies: editorId === 'onlyoffice',
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
  const message = String(error && error.message ? error.message : error);
  const where = mode === 'scale' ? stageFailure() : null;
  process.stdout.write(
    JSON.stringify({
      mode,
      status: 'probe_error',
      reason: (where ? `${where}: ${message}` : message).slice(0, 500),
      ...(mode === 'scale' ? { stages: scaleStages.slice() } : {}),
    }),
  );
  process.exitCode = 1;
} finally {
  await browser.close();
}
