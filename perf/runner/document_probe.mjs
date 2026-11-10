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
 *           document surface (DOM text, a non-blank canvas pixel, or open
 *           shadow-root text). FCP is recorded beside that frame and is not
 *           the sample. The witness window is 500 ms. No forced repaint.
 *   reflow  input (Enter at the document start, page clock) to the first
 *           acked frame at or after the anchor was observed to move. The
 *           sample subtracts the probe's own getBoundingClientRect time.
 *           Page.startScreencast frames are acked via the witness recorder
 *           (Page.screencastFrame). frame_source: 'cdp_screencast'.
 *   scale   usable on an animation frame, then the next acked frame that
 *           differs after the document has settled. No post-load damage is
 *           not "no compositor frame": a 1 px outline outside the document
 *           is recorded as mechanism forced_repaint and is not a measured
 *           sample. The witness window is 500 ms.
 *   find    the editor's own find widget. Completion is the widget's own
 *           acknowledgement event. No widget is not_applicable with a reason.
 *           cap_ms is null: there is no fixed completion cap.
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
  DEFAULT_WINDOW_MS,
  getRecorder,
  loadPlaywright,
  stopRecorder,
  witnessFrame,
} from './witness.mjs';

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
const pageSelector = opt['page-selector'] || '';
const pageModel = opt['page-model'] || (pageSelector ? 'page' : 'continuous_flow');
const editSelector = opt['edit-selector'] || docSelector;
const settleMs = Number(opt['settle-ms'] || 0);
const timeoutMs = Number(opt['timeout-ms'] || 120000);
const anchorIndex = Number(opt['anchor-index'] || 1);
const minTextChars = Number(opt['min-text-chars'] || 8);
const findInputSelector = opt['find-input-selector'] || '';
const findCountSelector = opt['find-count-selector'] || '';
const findMatchSelector = opt['find-match-selector'] || '';
const findQuery = opt['find-query'] || '';
const findExpected = opt['find-expected-matches'] ? Number(opt['find-expected-matches']) : null;
const findShortcuts = (opt['find-shortcuts'] || 'Control+f,Meta+f').split(',').map((s) => s.trim()).filter(Boolean);
const SIGNAL_INPUTS = new Set(['dom_text', 'canvas_pixel', 'shadow_text']);
const usableSignal = opt['usable-signal'] || 'dom_text';
if (!SIGNAL_INPUTS.has(usableSignal)) {
  console.error('document_probe: --usable-signal must be dom_text|canvas_pixel|shadow_text');
  process.exit(2);
}
const SIGNAL_NAME = {
  dom_text: 'dom_text',
  canvas_pixel: 'canvas_pixel_non_blank',
  shadow_text: 'open_shadow_root_text',
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
  if (readyJs) {
    await page.waitForFunction(
      (expr) => {
        try {
          // eslint-disable-next-line no-eval
          return Boolean(eval(expr));
        } catch {
          return false;
        }
      },
      readyJs,
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
const INIT_SCRIPT = ({ docSel, pageSel, minTextChars: minChars, signal }) => {
  const recorded =
    signal === 'canvas_pixel' ? 'canvas_pixel_non_blank' : signal === 'shadow_text' ? 'open_shadow_root_text' : 'dom_text';
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
  const domText = () =>
    Array.from(document.querySelectorAll(docSel))
      .map((el) => (el.textContent || '').trim())
      .filter(Boolean)
      .join(' ');
  const shadowText = () => {
    const hosts = docSel ? Array.from(document.querySelectorAll(docSel)) : Array.from(document.querySelectorAll('*'));
    let text = '';
    const visit = (root) => {
      if (!root) return;
      text += ' ' + (root.textContent || '');
      const nested = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const el of nested) {
        if (el.shadowRoot) visit(el.shadowRoot);
      }
    };
    for (const host of hosts) {
      if (host.shadowRoot) visit(host.shadowRoot);
    }
    return text.replace(/\s+/g, ' ').trim();
  };
  const canvasDrawn = () => {
    const nodes = Array.from(document.querySelectorAll(docSel));
    for (const el of nodes) {
      if (typeof HTMLCanvasElement === 'undefined' || !(el instanceof HTMLCanvasElement)) continue;
      let g = null;
      try {
        g = el.getContext('2d');
      } catch {
        g = null;
      }
      if (!g || typeof g.getImageData !== 'function') continue;
      let data = null;
      try {
        const w = Math.min(32, el.width || 0);
        const h = Math.min(32, el.height || 0);
        if (w < 1 || h < 1) continue;
        data = g.getImageData(0, 0, w, h).data;
      } catch {
        continue;
      }
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const gc = data[i + 1];
        const b = data[i + 2];
        const a = data[i + 3];
        if (a > 16 && (r < 250 || gc < 250 || b < 250)) return true;
      }
    }
    return false;
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
    if (state.docTextAt === null) {
      let ok = false;
      let chars = 0;
      if (signal === 'canvas_pixel') {
        ok = canvasDrawn();
        chars = ok ? 1 : 0;
      } else if (signal === 'shadow_text') {
        const text = shadowText();
        chars = text.length;
        ok = chars >= minChars;
      } else {
        const text = domText();
        chars = text.length;
        ok = chars >= minChars;
      }
      if (ok) {
        state.docTextAt = performance.now();
        state.docTextCharsAt = chars;
      }
    }
    if (state.docTextAt === null && performance.now() < 120000) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
};

async function newPage(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await routeCorpus(context);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
  await page.addInitScript(INIT_SCRIPT, {
    docSel: docSelector,
    pageSel: pageSelector,
    minTextChars: minTextChars,
    signal: usableSignal,
  });
  return { context, page, errors, cdp: null, recorder: null };
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
  return chromium.launch({ headless: true, args: ['--font-render-hinting=none', '--disable-lcd-text'] });
}

async function stateSnapshot(page) {
  return page.evaluate(
    ({ docSel, pageSel }) => {
      const s = window.__docProbeState || {};
      const pageEl = pageSel ? document.querySelector(pageSel) : null;
      const docText = Array.from(document.querySelectorAll(docSel))
        .map((el) => (el.textContent || '').trim())
        .filter(Boolean)
        .join(' ');
      return {
        first_element_ms: s.firstElementAt === null || s.firstElementAt === undefined ? null : s.firstElementAt,
        first_element_info: s.firstElementInfo || null,
        document_text_at_ms: s.docTextAt === null || s.docTextAt === undefined ? null : s.docTextAt,
        document_text_chars_at: s.docTextCharsAt === null || s.docTextCharsAt === undefined ? null : s.docTextCharsAt,
        page_count_at_first: s.pageCountAtFirst === null || s.pageCountAtFirst === undefined ? null : s.pageCountAtFirst,
        page_count: pageSel ? document.querySelectorAll(pageSel).length : null,
        page_text_chars: pageEl ? (pageEl.textContent || '').trim().length : null,
        document_text_chars: docText.length,
        document_text: docText.slice(0, 4000),
        time_origin_ms: performance.timeOrigin,
        usable_signal: s.usableSignal || null,
      };
    },
    { docSel: docSelector, pageSel: pageSelector },
  );
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

/** Latest screencast frame while the document surface is still absent. */
async function waitForSurfaceKeepingBaseline(page, recorder) {
  const deadline = Date.now() + timeoutMs;
  let baseline = null;
  while (Date.now() < deadline) {
    const surface = await readSurface(page);
    if (surface.at_ms === null) {
      const last = recorder && recorder.frames.length ? recorder.frames[recorder.frames.length - 1] : null;
      if (last) baseline = last;
      await sleep(12);
      continue;
    }
    return { surface, baseline };
  }
  return { surface: await readSurface(page), baseline };
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

async function loadResult(ctx, { navigationMs, readyMs, surface, witness, surfaceReason }) {
  const paints = await paintEntries(ctx.page);
  const snap = await stateSnapshot(ctx.page);
  const fcp = fcpFrom(paints);
  const facts = witnessFacts(witness);
  const at = surface && surface.at_ms !== null && surface.at_ms !== undefined ? surface.at_ms : null;
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
    presented_frame_ms: facts.presented_frame_ms,
    frames_total: facts.frames_total,
    frames_after_usable: facts.frames_after_usable,
    frame_source: 'cdp_screencast',
    clock_skew_ms: facts.clock_skew_ms,
    clock_skew_acceptable: facts.clock_skew_acceptable,
    witness: facts.witness,
    surface_reason: surfaceReason || null,
    page_errors: ctx.errors,
  };
}

async function runLoad(browser) {
  const ctx = await newPage(browser);
  await beginWitness(ctx);
  try {
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
    const waited = await waitForSurfaceKeepingBaseline(ctx.page, ctx.recorder);
    let witness = null;
    if (waited.surface.at_ms !== null) {
      witness = await witnessFrame(ctx.page, ctx.cdp, {
        afterPageMs: waited.surface.at_ms,
        baseline: waited.baseline || TINY_BASELINE_PNG,
        windowMs: DEFAULT_WINDOW_MS,
        caretMask: false,
        settleMs: 0,
        recorder: ctx.recorder,
        minPixels: waited.baseline ? 4 : 1,
      });
    }
    return await loadResult(ctx, {
      navigationMs,
      readyMs,
      surface: waited.surface,
      witness,
      surfaceReason: waited.surface.at_ms === null ? 'document surface did not appear before the probe timeout' : null,
    });
  } finally {
    await endWitness(ctx);
    await ctx.context.close();
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
    const surface = surfaceReason ? { at_ms: null, chars: null, signal: SIGNAL_NAME.canvas_pixel } : await waitForSurface(ctx.page);
    const snap = await stateSnapshot(ctx.page);
    const paints = await paintEntries(ctx.page);
    let natural = null;
    let forced = null;
    let mechanism = null;
    if (surface.at_ms !== null) {
      const settled = await settleStableFrame(ctx.page, ctx.recorder);
      const afterPageMs = await ctx.page.evaluate(() => performance.now());
      natural = await witnessFrame(ctx.page, ctx.cdp, {
        afterPageMs,
        baseline: settled.frame || TINY_BASELINE_PNG,
        windowMs: DEFAULT_WINDOW_MS,
        caretMask: false,
        settleMs: 0,
        recorder: ctx.recorder,
        // No settled frame: a 1x1 stand-in must not count as document damage.
        minPixels: settled.frame ? 4 : 1e9,
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
          baseline: pre || TINY_BASELINE_PNG,
          windowMs: DEFAULT_WINDOW_MS,
          caretMask: false,
          settleMs: 0,
          recorder: ctx.recorder,
          minPixels: 1,
          threshold: 0,
          clockSkewMs: natural.clock_skew_ms,
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
    await ctx.context.close();
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

    const before = await ctx.page.evaluate(
      ({ docSel }) => {
        const blocks = Array.from(document.querySelectorAll(docSel));
        if (blocks.length < 2) {
          return { ok: false, reason: 'fewer than two document blocks; nothing below the insertion to move' };
        }
        const counts = new Map();
        for (const block of blocks) {
          const text = (block.textContent || '').trim();
          if (!text) continue;
          counts.set(text, (counts.get(text) || 0) + 1);
        }
        // The anchor is a block with unique text below the insertion point. Index
        // identity is not usable: inserting at the top renumbers every block and
        // makes an unchanged index look like an unchanged position.
        let anchor = null;
        for (let i = blocks.length - 1; i >= 1; i--) {
          const text = (blocks[i].textContent || '').trim();
          if (text && counts.get(text) === 1) {
            anchor = { el: blocks[i], index: i, text };
            break;
          }
        }
        if (!anchor) {
          return {
            ok: false,
            reason: 'no block below the insertion point has unique non-empty text; a y-shift could not be attributed',
            blocks: blocks.length,
          };
        }
        window.__c12AnchorEl = anchor.el;
        window.__c12AnchorTop = anchor.el.getBoundingClientRect().top;
        return {
          ok: true,
          blocks: blocks.length,
          anchor_index: anchor.index,
          anchor_text: anchor.text,
          anchor_top: window.__c12AnchorTop,
          first_block_top: blocks[0].getBoundingClientRect().top,
          first_block_text: (blocks[0].textContent || '').trim().slice(0, 40),
        };
      },
      { docSel: docSelector },
    );
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
    await ctx.page.keyboard.press('Control+Home');
    await ctx.page.waitForTimeout(150);
    await ctx.page.keyboard.press('Home');
    await ctx.page.waitForTimeout(100);

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

    const shift = await ctx.page.evaluate(
      ({ docSel, anchorText, beforeTop, timeoutMs: budget }) => {
        const started = performance.now();
        const locate = () => {
          const kept = window.__c12AnchorEl;
          if (kept && kept.isConnected) {
            const text = (kept.textContent || '').trim();
            if (text === anchorText) return { el: kept, by: 'element' };
          }
          const match = Array.from(document.querySelectorAll(docSel)).find(
            (block) => (block.textContent || '').trim() === anchorText,
          );
          return match ? { el: match, by: 'text' } : null;
        };
        return new Promise((resolve) => {
          let forced = 0;
          const finish = (moved, hit, top) => {
            const layoutStarted = performance.now();
            const afterTop = hit && hit.el ? hit.el.getBoundingClientRect().top : null;
            forced += performance.now() - layoutStarted;
            resolve({
              moved,
              observed_page_ms: moved ? top.observed : null,
              forced_layout_ms: forced,
              block_count: document.querySelectorAll(docSel).length,
              anchor_top_after: afterTop,
              matched_by: hit ? hit.by : null,
              input_page_ms: window.__c12InputMs === null || window.__c12InputMs === undefined ? null : window.__c12InputMs,
            });
          };
          const step = (rafNow) => {
            const hit = locate();
            if (hit) {
              const layoutStarted = performance.now();
              const top = hit.el.getBoundingClientRect().top;
              forced += performance.now() - layoutStarted;
              if (top > beforeTop + 0.5) {
                finish(true, hit, { observed: rafNow });
                return;
              }
            }
            if (performance.now() - started >= budget) {
              finish(false, hit, null);
              return;
            }
            requestAnimationFrame(step);
          };
          requestAnimationFrame(step);
        });
      },
      { docSel: docSelector, anchorText: before.anchor_text, beforeTop: before.anchor_top, timeoutMs: 3000 },
    );

    const forcedLayoutMs = Math.max(0, Number(shift.forced_layout_ms || 0));
    const inputPageMs = shift.input_page_ms === null || shift.input_page_ms === undefined ? inputMark : shift.input_page_ms;
    let witness = null;
    if (shift.moved && shift.observed_page_ms !== null) {
      witness = await witnessFrame(ctx.page, ctx.cdp, {
        afterPageMs: shift.observed_page_ms,
        baseline: baseline || TINY_BASELINE_PNG,
        windowMs: DEFAULT_WINDOW_MS,
        caretMask: false,
        settleMs: 0,
        recorder: ctx.recorder,
        minPixels: baseline ? 4 : 1,
      });
    }
    const framePageMs = witness && witness.outcome === 'witnessed' ? witness.frame_page_ms : null;
    const raw = framePageMs === null ? null : framePageMs - inputPageMs;
    const presented = raw === null ? null : raw - forcedLayoutMs;
    return {
      mode: 'reflow',
      driver: 'playwright',
      url,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      before,
      anchor_index: before.anchor_index,
      anchor_text: before.anchor_text,
      shift_px: shift.moved ? shift.anchor_top_after - before.anchor_top : null,
      moved: shift.moved,
      matched_by: shift.matched_by,
      block_count_before: before.blocks,
      block_count_after: shift.block_count,
      insertion_created_block: shift.block_count > before.blocks,
      anchor_top_after: shift.anchor_top_after,
      input_page_ms: inputPageMs,
      observed_page_ms: shift.observed_page_ms,
      forced_layout_ms: forcedLayoutMs,
      window_excludes_forced_layout: true,
      presented_frame_raw_ms: raw,
      presented_frame_ms: presented,
      frames_total: witness ? witness.frames_total : ctx.recorder.frames.length,
      frames_after_shift_observed: witness ? witness.frames_after : 0,
      frame_source: 'cdp_screencast',
      clock_skew_ms: witness ? witness.clock_skew_ms : null,
      clock_skew_acceptable: witness ? witness.clock_skew_acceptable : null,
      witness,
      page_errors: ctx.errors,
      anchor_index_requested: anchorIndex,
    };
  } finally {
    await endWitness(ctx);
    await ctx.context.close();
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
    await ctx.page.locator(findInputSelector).first().click({ timeout: 5000 });
    await ctx.page.evaluate(
      ({ countSel, matchSel, expected }) => {
        const probe = (window.__findProbe = { first_at: null, complete_at: null, last: '', expected: expected });
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
        const check = () => {
          const now = read();
          const changed = now.text !== probe.last;
          probe.last = now.text;
          if (changed && probe.first_at === null && now.text) probe.first_at = performance.now();
          const count = total(now.text, now.matches);
          const done =
            probe.expected === null ? Boolean(now.text) && !changed : count !== null && count === probe.expected;
          if (done && probe.complete_at === null) probe.complete_at = performance.now();
        };
        probe.check = check;
        const obs = new MutationObserver(check);
        obs.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true });
        probe.stop = () => obs.disconnect();
        check();
      },
      { countSel: findCountSelector, matchSel: findMatchSelector, expected: findExpected },
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
        last_count_text: probe.last || '',
      };
      if (probe.stop) probe.stop();
      return out;
    });
    const delta = (value) => (value === null ? null : value - inputPageMs);
    const eventCompleted = completion === 'event';
    return {
      mode: 'find',
      status: eventCompleted ? 'measured' : 'unverified',
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
    await ctx.context.close();
  }
}

const browser = await launch();
try {
  let result;
  if (mode === 'load') result = await runLoad(browser);
  else if (mode === 'scale') result = await runScale(browser);
  else if (mode === 'reflow') result = await runReflow(browser);
  else result = await runFind(browser);
  process.stdout.write(JSON.stringify(result));
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
