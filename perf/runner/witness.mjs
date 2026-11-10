/**
 * B1c — the shared witness module.
 *
 * The browser lanes (B2 input-to-paint, B3 document paint, B4 input criteria,
 * B5 scroll) all need the same three things, and none of them may be
 * re-invented per lane:
 *
 *   1. a frame witness: the first composited frame at or after a stated
 *      instant in the *page's* clock whose pixels really changed;
 *   2. a clock-skew probe: how far the screencast clock is from the page
 *      clock, so a lane can refuse a sample whose clock it cannot trust;
 *   3. a renderer string: what actually drew the pixels, with a reason when
 *      there is none.
 *
 * This module owns them. It is imported by the lanes; they never import each
 * other. Everything it returns is a plain JSON record (no class instances, no
 * Buffers), so a Python reader can validate it without knowing JavaScript.
 *
 * ---------------------------------------------------------------------------
 * Clocks, and what "skew" means here
 * ---------------------------------------------------------------------------
 * The page's clock is `performance.now()` (monotonic, origin = navigation
 * start) together with `performance.timeOrigin` (the wall clock at that
 * origin). A CDP screencast frame carries `metadata.timestamp`, which
 * Chromium documents as a frame-swap timestamp; in practice it is a *wall
 * clock* reading in seconds ("epoch seconds"), and some builds ship a
 * `metadata.monotonicTimestamp` beside it. Which one it is changes everything,
 * so the module detects it per frame (an epoch reading is within two minutes
 * of `Date.now()`; a monotonic reading is not) and records the answer in
 * `timestamp_kind`.
 *
 * Converting a frame to page time is then
 *
 *     page_ms = timestamp * 1000 - performance.timeOrigin
 *
 * and the *error* of that conversion is what `clockSkew` measures. It is not
 * the compositor's latency: the frame that shows a change is produced one
 * frame interval later, and on a software renderer much later than that
 * (~13 ms was measured here). That latency is reported separately as
 * `frame_lag_ms`; it is a property of the machine, not of the clock.
 *
 * The conversion error is the difference between two readings of the same OS
 * clock, and it is measurable inside the page:
 *
 *     (Date.now() - performance.timeOrigin) - performance.now()
 *
 * is the wall-clock/monotonic discrepancy the renderer has accumulated since
 * navigation, which is exactly the error the conversion inherits (the
 * screencast timestamp and `performance.timeOrigin` are both wall-clock
 * readings of the same OS clock). `Date.now()` truncates to a millisecond, so
 * the probe takes several samples and reports the median; the residual spread
 * is reported as `page_offset_spread_ms`.
 *
 * A frame anchor is measured as well, because the skew must be tied to a
 * real frame: the probe forces a visible change at a known `performance.now()`
 * and captures the frame that shows it. That frame gives `frame_page_ms` (the
 * converted page time) and `frame_lag_ms` (the compositor's latency), and it
 * is what proves the conversion lands in the page's timeline at all.
 *
 * The caller refuses a sample when `|skew_ms| > bound_ms` (2 ms by default,
 * recorded in every record).
 *
 * ---------------------------------------------------------------------------
 * The comparator
 * ---------------------------------------------------------------------------
 * "The frame that shows the change" is decided on decoded pixels, never on
 * bytes: PNG frames are decoded (there is no JPEG decoder in this tree, so
 * the screencast asks for PNG) and compared channel by channel. A frame counts
 * as different when more than `threshold` (a ratio of the frame's pixels,
 * 0.005 % by default) differ by more than `channel_tolerance` (8/255) in any
 * channel.
 *
 * A blinking caret damages the compositor on its own, so the caret is masked
 * before the baseline is taken: `* { caret-color: transparent !important }` is
 * injected and the record says whether it was injected (`caret_masked`). With
 * the caret masked the blink still produces frames, but the pixels do not
 * change, so a caret-only host produces no witness.
 *
 * A refusal is an outcome, never a zero: `outcome` is "witnessed" or
 * "no_frame", and a refusal keeps the payload (frames seen, biggest diff,
 * the mask, the skew) so the caller can record why.
 *
 * ---------------------------------------------------------------------------
 * How a lane calls this
 * ---------------------------------------------------------------------------
 *   const cdp = await context.newCDPSession(page);
 *   const skew = await clockSkew(page, cdp);          // before the interaction
 *   if (Math.abs(skew.skew_ms) > skew.bound_ms) { ...refuse... }
 *   const frame = await witnessFrame(page, cdp, { afterPageMs: eventPageMs });
 *
 * `witnessFrame` masks the caret, takes its baseline frame and only then
 * looks for the frame that shows the change, so the caller may pass
 * `afterPageMs` (a page-clock instant) or an `arm` callback that produces the
 * change and returns that instant. `afterPageMs` must be a page-clock value
 * (`performance.now()`), never a driver wall-clock value.
 */

import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '../..');

/** The default bound on |skew_ms|; a caller refuses a sample above it. */
export const DEFAULT_SKEW_BOUND_MS = 2;
/** The witness window: at least half a second, per the plan. */
export const DEFAULT_WINDOW_MS = 500;
/**
 * The default pixel-difference threshold, as a ratio of the frame's pixels.
 * A caret is a few dozen pixels, which is 0.002 % of a 1280x900 frame, so the
 * threshold has to be below that for the caret mask to matter; the absolute
 * floor (`DEFAULT_MIN_PIXELS`) keeps a handful of antialiased pixels from
 * counting as a change.
 */
export const DEFAULT_THRESHOLD = 0.00001;
/**
 * The absolute floor: a frame must differ in at least this many pixels. A
 * caret is thin (9 pixels on the fake host), so the floor stays low; the
 * ratio threshold is the criterion that does the work on a full-size frame.
 */
export const DEFAULT_MIN_PIXELS = 4;
/** The per-channel tolerance (8/255) below which a pixel counts as equal. */
export const DEFAULT_CHANNEL_TOLERANCE = 8;
/** The caret mask. It is injected before the baseline frame is taken. */
export const CARET_MASK_CSS = '* { caret-color: transparent !important }';
/** The launch flag that lets the WebGL probe ask for the unmasked renderer. */
export const WEBGL_UNMASK_FLAG = '--enable-unsafe-swiftshader';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const round = (value, digits = 3) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
};

const median = (values) => {
  if (!values || values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
};

const quantile = (values, q) => {
  if (!values || values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const pos = (sorted.length - 1) * q;
  const low = Math.floor(pos);
  const high = Math.ceil(pos);
  if (low === high) return sorted[low];
  return sorted[low] + (sorted[high] - sorted[low]) * (pos - low);
};

// ------------------------------------------------------------------ Playwright

/**
 * Resolve Playwright from the harness. `harness/` is a read-only symlink, so
 * the module never writes there; it only loads the package the harness pins.
 */
export async function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const candidates = [
    process.env.WITNESS_PLAYWRIGHT,
    path.join(repoRoot, 'harness/ui/plate/node_modules/playwright'),
    path.join(repoRoot, 'harness/ui/node_modules/playwright'),
    path.join(repoRoot, 'harness/ui/node_modules/playwright-core'),
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch {
      /* try the next one */
    }
  }
  return require('playwright');
}

// ----------------------------------------------------------------- PNG decoder

/**
 * Decode a PNG into RGBA. Only what Chromium's screencast writes is
 * supported: 8 bits per channel, no interlacing, greyscale/RGB/greyscale+alpha
 * /RGBA.
 */
export function decodePng(buffer) {
  const data = Buffer.isBuffer(buffer) ? buffer : Buffer.from(buffer);
  const signature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  if (data.length < 8 || !data.subarray(0, 8).equals(signature)) {
    throw new Error('not a PNG frame');
  }
  let offset = 8;
  let width = 0;
  let height = 0;
  let depth = 0;
  let colorType = 0;
  let interlace = 0;
  const idat = [];
  while (offset + 8 <= data.length) {
    const length = data.readUInt32BE(offset);
    const type = data.toString('ascii', offset + 4, offset + 8);
    const chunk = data.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      width = chunk.readUInt32BE(0);
      height = chunk.readUInt32BE(4);
      depth = chunk[8];
      colorType = chunk[9];
      interlace = chunk[12];
    } else if (type === 'IDAT') {
      idat.push(chunk);
    } else if (type === 'IEND') {
      break;
    }
    offset += 12 + length;
  }
  if (depth !== 8) throw new Error(`unsupported PNG bit depth ${depth}`);
  if (interlace !== 0) throw new Error('interlaced PNG frames are not supported');
  const channels = { 0: 1, 2: 3, 4: 2, 6: 4 }[colorType];
  if (!channels) throw new Error(`unsupported PNG color type ${colorType}`);
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = width * channels;
  const out = Buffer.alloc(height * stride);
  let pos = 0;
  for (let y = 0; y < height; y++) {
    const filter = raw[pos];
    pos += 1;
    const line = raw.subarray(pos, pos + stride);
    pos += stride;
    const cur = out.subarray(y * stride, (y + 1) * stride);
    const prev = y > 0 ? out.subarray((y - 1) * stride, y * stride) : null;
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? cur[x - channels] : 0;
      const b = prev ? prev[x] : 0;
      const c = prev && x >= channels ? prev[x - channels] : 0;
      const value = line[x];
      let out8;
      switch (filter) {
        case 0:
          out8 = value;
          break;
        case 1:
          out8 = value + a;
          break;
        case 2:
          out8 = value + b;
          break;
        case 3:
          out8 = value + ((a + b) >> 1);
          break;
        case 4: {
          const p = a + b - c;
          const pa = Math.abs(p - a);
          const pb = Math.abs(p - b);
          const pc = Math.abs(p - c);
          out8 = value + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c);
          break;
        }
        default:
          throw new Error(`unknown PNG filter ${filter}`);
      }
      cur[x] = out8 & 0xff;
    }
  }
  const rgba = new Uint8Array(width * height * 4);
  const pixels = width * height;
  for (let i = 0; i < pixels; i++) {
    const s = i * channels;
    const d = i * 4;
    if (colorType === 2) {
      rgba[d] = out[s];
      rgba[d + 1] = out[s + 1];
      rgba[d + 2] = out[s + 2];
      rgba[d + 3] = 255;
    } else if (colorType === 6) {
      rgba[d] = out[s];
      rgba[d + 1] = out[s + 1];
      rgba[d + 2] = out[s + 2];
      rgba[d + 3] = out[s + 3];
    } else if (colorType === 0) {
      rgba[d] = out[s];
      rgba[d + 1] = out[s];
      rgba[d + 2] = out[s];
      rgba[d + 3] = 255;
    } else {
      rgba[d] = out[s];
      rgba[d + 1] = out[s];
      rgba[d + 2] = out[s];
      rgba[d + 3] = out[s + 1];
    }
  }
  return { width, height, data: rgba, channels, color_type: colorType };
}

/** Compare two decoded frames; the ratio of pixels that differ. */
export function diffRatio(a, b, { channelTolerance = DEFAULT_CHANNEL_TOLERANCE } = {}) {
  const total = a.width * a.height;
  if (!total) return { ratio: 1, changed: 0, total: 0, comparable: false };
  if (a.width !== b.width || a.height !== b.height) {
    return { ratio: 1, changed: total, total, comparable: false };
  }
  const da = a.data;
  const db = b.data;
  let changed = 0;
  for (let i = 0; i < total; i++) {
    const p = i * 4;
    if (
      Math.abs(da[p] - db[p]) > channelTolerance ||
      Math.abs(da[p + 1] - db[p + 1]) > channelTolerance ||
      Math.abs(da[p + 2] - db[p + 2]) > channelTolerance ||
      Math.abs(da[p + 3] - db[p + 3]) > channelTolerance
    ) {
      changed += 1;
    }
  }
  return { ratio: changed / total, changed, total, comparable: true };
}

// ------------------------------------------------------------------- recorder

const recorders = new WeakMap();

/**
 * The frame recorder: it listens to `Page.screencastFrame`, acks every frame
 * (an unacked frame stops the screencast) and keeps the frames with their
 * metadata. One recorder per CDP session, so the lanes can share it.
 */
export function getRecorder(cdp, options = {}) {
  let recorder = recorders.get(cdp);
  if (recorder) return recorder;
  recorder = {
    cdp,
    frames: [],
    started: false,
    startError: null,
    format: options.format || 'png',
    maxWidth: options.maxWidth || 1280,
    maxHeight: options.maxHeight || 900,
    manageScreencast: options.manageScreencast !== false,
    decoded: new Map(),
  };
  recorder.listener = (event) => {
    const metadata = event.metadata || {};
    recorder.frames.push({
      data: event.data,
      ts: typeof metadata.timestamp === 'number' ? metadata.timestamp : null,
      mono:
        typeof metadata.monotonicTimestamp === 'number' ? metadata.monotonicTimestamp : null,
      receipt_ms: Date.now(),
      seq: recorder.frames.length,
    });
    if (recorder.frames.length > 1200) {
      const drop = recorder.frames.length - 1200;
      recorder.frames.splice(0, drop);
      recorder.decoded.clear();
    }
    cdp
      .send('Page.screencastFrameAck', { sessionId: event.sessionId })
      .catch(() => {
        /* the session may be gone; the frame is kept anyway */
      });
  };
  cdp.on('Page.screencastFrame', recorder.listener);
  recorders.set(cdp, recorder);
  return recorder;
}

/** Stop the recorder's screencast and forget its frames. */
export async function stopRecorder(cdp) {
  const recorder = recorders.get(cdp);
  if (!recorder) return;
  recorders.delete(cdp);
  cdp.off('Page.screencastFrame', recorder.listener);
  if (recorder.started) {
    try {
      await cdp.send('Page.stopScreencast');
    } catch {
      /* already stopped */
    }
  }
}

async function ensureScreencast(recorder) {
  if (recorder.started) return recorder;
  if (!recorder.manageScreencast) {
    recorder.started = true;
    return recorder;
  }
  try {
    await recorder.cdp.send('Page.startScreencast', {
      format: recorder.format,
      everyNthFrame: 1,
      maxWidth: recorder.maxWidth,
      maxHeight: recorder.maxHeight,
    });
    recorder.started = true;
  } catch (error) {
    recorder.startError = String(error);
    throw error;
  }
  return recorder;
}

function decodeFrame(recorder, frame) {
  const cached = recorder.decoded.get(frame.seq);
  if (cached) return cached;
  let decoded = null;
  try {
    decoded = decodePng(Buffer.from(frame.data, 'base64'));
  } catch {
    decoded = null;
  }
  recorder.decoded.set(frame.seq, decoded);
  return decoded;
}

// ---------------------------------------------------------------- page clock

async function pageClock(page, extra = {}) {
  const reading = await page.evaluate(() => ({
    time_origin_ms: performance.timeOrigin,
    now_ms: performance.now(),
    date_now_ms: Date.now(),
    user_agent: navigator.userAgent,
  }));
  return { ...reading, ...extra };
}

/**
 * Which kind of timestamp does a frame carry? An epoch reading is within two
 * minutes of `Date.now()`; a monotonic reading is not, and its origin is
 * unknown, so the conversion needs an anchor the module may not have.
 */
export function detectTimestampKind(frame, nodeEpochMs = Date.now()) {
  const fields = [];
  if (typeof frame.ts === 'number') fields.push({ field: 'timestamp', value: frame.ts });
  if (typeof frame.mono === 'number') {
    fields.push({ field: 'monotonicTimestamp', value: frame.mono });
  }
  for (const candidate of fields) {
    if (Math.abs(candidate.value * 1000 - nodeEpochMs) < 120000) {
      return { kind: 'epoch_seconds', field: candidate.field };
    }
  }
  for (const candidate of fields) {
    const asMs = candidate.value * 1000;
    if (asMs > 0 && asMs < 1e12) {
      return { kind: 'monotonic_seconds', field: candidate.field };
    }
  }
  return { kind: 'unknown', field: null };
}

function convertFrameToPageMs(frame, clock) {
  const kind = clock.timestamp_kind || detectTimestampKind(frame).kind;
  if (kind === 'epoch_seconds') {
    if (typeof frame.ts !== 'number') return null;
    return frame.ts * 1000 - clock.time_origin_ms;
  }
  if (kind === 'monotonic_seconds') {
    if (typeof frame.mono !== 'number' && typeof frame.ts !== 'number') return null;
    const value = typeof frame.mono === 'number' ? frame.mono : frame.ts;
    if (typeof clock.monotonic_origin_ms !== 'number') return null;
    return value * 1000 - clock.monotonic_origin_ms;
  }
  return null;
}

/**
 * The page's wall-clock/monotonic discrepancy since navigation: the error the
 * screencast->page-time conversion inherits. It needs no frame and no
 * compositor, so it is cheap enough to measure next to every witness.
 */
export async function pageClockOffset(page, { samples = 5, sampleGapMs = 5 } = {}) {
  const offsets = await page.evaluate(
    async ({ count, gap }) => {
      const out = [];
      for (let i = 0; i < count; i++) {
        const t = performance.now();
        out.push(Date.now() - performance.timeOrigin - t);
        await new Promise((resolve) => setTimeout(resolve, gap));
      }
      return out;
    },
    { count: samples, gap: sampleGapMs },
  );
  const value = median(offsets);
  return {
    page_offset_ms: value === null ? null : round(value, 3),
    page_offset_samples: offsets.map((v) => round(v, 3)),
    page_offset_spread_ms:
      offsets.length === 0 ? null : round(Math.max(...offsets) - Math.min(...offsets), 3),
  };
}

// ------------------------------------------------------------------ caret mask

/** Inject the caret mask; the record says whether it went in. */
export async function injectCaretMask(page) {
  try {
    await page.addStyleTag({ content: CARET_MASK_CSS });
    return { caret_masked: true, caret_mask_css: CARET_MASK_CSS, caret_mask_error: null };
  } catch (error) {
    return {
      caret_masked: false,
      caret_mask_css: CARET_MASK_CSS,
      caret_mask_error: String(error).slice(0, 200),
    };
  }
}

// ----------------------------------------------------------------- frame interval

/**
 * The frame interval: the median of at least `frames` rAF deltas. The median,
 * not the mean and not the minimum: headless Chromium produces deltas from
 * 0.4 ms to a full frame interval, and only the median survives that.
 */
export async function frameInterval(page, { frames = 60, timeoutMs = 15000 } = {}) {
  const deltas = await page.evaluate(
    async ({ count, budget }) => {
      const out = [];
      const started = performance.now();
      await new Promise((resolve) => {
        let last = null;
        const tick = (t) => {
          if (last !== null) out.push(t - last);
          last = t;
          if (out.length >= count || performance.now() - started > budget) {
            resolve();
            return;
          }
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      return out;
    },
    { count: frames, budget: timeoutMs },
  );
  const sorted = [...deltas].sort((a, b) => a - b);
  return {
    statistic: 'median',
    median_ms: round(median(sorted), 3),
    count: deltas.length,
    p10_ms: round(quantile(sorted, 0.1), 3),
    p90_ms: round(quantile(sorted, 0.9), 3),
    source: 'raf_delta',
    requested_frames: frames,
  };
}

// ------------------------------------------------------------------- clock skew

/**
 * The clock-skew probe.
 *
 * It forces a visible change at a known `performance.now()`, captures the
 * screencast frame that shows it, converts that frame's timestamp to page
 * time and reports how far the conversion can be trusted.
 *
 * `skew_ms` is the error of the conversion (see the file header): the page's
 * wall-clock/monotonic discrepancy, which the screencast timestamp inherits.
 * `frame_lag_ms` is the compositor's presentation latency — a property of the
 * machine, reported next to it and never folded into the skew.
 */
export async function clockSkew(
  page,
  cdp,
  {
    boundMs = DEFAULT_SKEW_BOUND_MS,
    samples = 9,
    sampleGapMs = 20,
    changeWaitMs = 600,
    manageScreencast = true,
    recorder: givenRecorder = null,
  } = {},
) {
  const recorder = givenRecorder || getRecorder(cdp, { manageScreencast });
  await ensureScreencast(recorder);

  const clock = await pageClock(page);
  const offsets = await page.evaluate(
    async ({ count, gap }) => {
      const out = [];
      for (let i = 0; i < count; i++) {
        const t = performance.now();
        out.push(Date.now() - performance.timeOrigin - t);
        await new Promise((resolve) => setTimeout(resolve, gap));
      }
      return out;
    },
    { count: samples, gap: sampleGapMs },
  );
  const pageOffsetMs = median(offsets);

  const anchor = await anchorFrame(page, recorder, clock, { waitMs: changeWaitMs });
  const kind = anchor.frame
    ? detectTimestampKind(anchor.frame)
    : recorder.frames.length
      ? detectTimestampKind(recorder.frames[recorder.frames.length - 1])
      : { kind: 'unknown', field: null };
  clock.timestamp_kind = kind.kind;

  const skewMs = kind.kind === 'epoch_seconds' ? pageOffsetMs : null;
  const acceptable =
    typeof skewMs === 'number' && Math.abs(skewMs) <= boundMs && kind.kind !== 'unknown';

  return {
    kind: 'clock_skew',
    skew_ms: skewMs === null ? null : round(skewMs, 3),
    method: 'page_clock_offset+frame_anchor',
    timestamp_kind: kind.kind,
    timestamp_field: kind.field,
    bound_ms: boundMs,
    acceptable,
    page_offset_ms: round(pageOffsetMs, 3),
    page_offset_samples: offsets.map((v) => round(v, 3)),
    page_offset_spread_ms: round(
      offsets.length ? Math.max(...offsets) - Math.min(...offsets) : null,
      3,
    ),
    time_origin_ms: round(clock.time_origin_ms, 3),
    change_page_ms: round(anchor.change_page_ms, 3),
    frame_page_ms: anchor.frame_page_ms === null ? null : round(anchor.frame_page_ms, 3),
    frame_lag_ms: anchor.frame_lag_ms === null ? null : round(anchor.frame_lag_ms, 3),
    frame_monotonic_ms: anchor.frame
      ? round(typeof anchor.frame.mono === 'number' ? anchor.frame.mono * 1000 : null, 3)
      : null,
    frames_total: recorder.frames.length,
    notes: [
      'skew_ms is the error of the screencast->page-time conversion, measured as the page wall-clock/monotonic discrepancy since navigation',
      'frame_lag_ms is the compositor presentation latency, not a clock error',
      kind.kind === 'epoch_seconds'
        ? 'metadata.timestamp is an epoch reading; page_ms = timestamp*1000 - performance.timeOrigin'
        : `metadata.timestamp is not an epoch reading (${kind.kind}); the conversion cannot be trusted without an anchor`,
    ],
  };
}

/**
 * Force a visible change at a known page time and find the frame that shows
 * it. The frame is chosen by its pixels, not by its timestamp, so the choice
 * does not depend on the conversion it then measures.
 */
async function anchorFrame(page, recorder, clock, { waitMs }) {
  const before = recorder.frames.length;
  const change = await page.evaluate(() => {
    const t = performance.now();
    let probe = document.getElementById('__witness_probe__');
    if (!probe) {
      probe = document.createElement('div');
      probe.id = '__witness_probe__';
      probe.setAttribute(
        'style',
        'position:fixed;left:0;top:0;width:8px;height:8px;background:#ff00ff;z-index:2147483647',
      );
      document.body.appendChild(probe);
    }
    return t;
  });
  const deadline = Date.now() + waitMs;
  let found = null;
  while (Date.now() < deadline && !found) {
    for (let i = before; i < recorder.frames.length; i++) {
      const frame = recorder.frames[i];
      const kind = detectTimestampKind(frame);
      if (kind.kind !== 'epoch_seconds' && kind.kind !== 'monotonic_seconds') continue;
      const pageMs = convertFrameToPageMs(frame, { ...clock, timestamp_kind: kind.kind });
      if (pageMs === null || pageMs < change) continue;
      found = { frame, pageMs, kind };
      break;
    }
    if (!found) await sleep(5);
  }
  await page
    .evaluate(() => {
      const probe = document.getElementById('__witness_probe__');
      if (probe && probe.parentNode) probe.parentNode.removeChild(probe);
    })
    .catch(() => {});
  if (!found) {
    return { change_page_ms: change, frame_page_ms: null, frame_lag_ms: null, frame: null };
  }
  return {
    change_page_ms: change,
    frame_page_ms: found.pageMs,
    frame_lag_ms: found.pageMs - change,
    frame: found.frame,
  };
}

// ----------------------------------------------------------------- frame witness

/**
 * The frame witness: the first acked screencast frame at or after
 * `afterPageMs` (in the page's clock) whose decoded pixels differ from the
 * baseline frame by more than `threshold`.
 *
 * `baseline` may be a frame from the recorder, a base64 PNG string, or null
 * (the recorder's most recent frame is used; if the page has not painted yet,
 * the module forces one repaint and takes the frame after it). The caret is
 * masked before the baseline is taken, and the record says so.
 *
 * A refusal is `outcome: "no_frame"` and it keeps the payload.
 */
export async function witnessFrame(
  page,
  cdp,
  {
    afterPageMs = null,
    arm = null,
    windowMs = DEFAULT_WINDOW_MS,
    baseline = null,
    threshold = DEFAULT_THRESHOLD,
    minPixels = DEFAULT_MIN_PIXELS,
    channelTolerance = DEFAULT_CHANNEL_TOLERANCE,
    caretMask = true,
    settleMs = 250,
    manageScreencast = true,
    recorder: givenRecorder = null,
    clockSkewMs = null,
  } = {},
) {
  const recorder = givenRecorder || getRecorder(cdp, { manageScreencast });
  await ensureScreencast(recorder);
  const clock = await pageClock(page);
  const first = recorder.frames[0];
  const kind = first ? detectTimestampKind(first) : { kind: 'unknown', field: null };
  clock.timestamp_kind = kind.kind;

  const caret = caretMask
    ? await injectCaretMask(page)
    : { caret_masked: false, caret_mask_css: CARET_MASK_CSS, caret_mask_error: null };
  if (caretMask) await sleep(settleMs);

  // The baseline must be the picture *before* the change, so it is taken
  // before the page is armed.
  const base = await resolveBaseline(page, recorder, baseline);
  const baseDecoded = base.frame ? decodeFrame(recorder, base.frame) : null;

  if (arm) {
    const armed = await arm();
    const value =
      typeof armed === 'number'
        ? armed
        : armed && typeof armed === 'object'
          ? (armed.after_page_ms ?? armed.marker_ms ?? null)
          : null;
    if (typeof value === 'number') afterPageMs = value;
  }

  const offset = clockSkewMs === null ? await pageClockOffset(page) : null;
  const skewMs = clockSkewMs === null ? offset?.page_offset_ms ?? null : clockSkewMs;

  const startedAt = Date.now();
  const deadline = startedAt + windowMs;
  let checked = 0;
  let framesAfter = 0;
  let best = null;
  let outcome = 'no_frame';
  let framePageMs = null;
  let diffRatioValue = null;
  let usedKind = kind.kind;

  while (Date.now() < deadline) {
    for (let i = checked; i < recorder.frames.length; i++) {
      const frame = recorder.frames[i];
      checked = i + 1;
      const frameKind = detectTimestampKind(frame);
      const effectiveKind = frameKind.kind === 'unknown' ? kind.kind : frameKind.kind;
      const pageMs = convertFrameToPageMs(frame, {
        ...clock,
        timestamp_kind: effectiveKind,
      });
      if (pageMs === null) continue;
      if (effectiveKind !== 'unknown') usedKind = effectiveKind;
      if (afterPageMs !== null && pageMs < afterPageMs) continue;
      framesAfter += 1;
      if (!baseDecoded) continue;
      if (frame.data === base.frame.data) continue; // identical bytes: identical pixels
      const decoded = decodeFrame(recorder, frame);
      if (!decoded) continue;
      const diff = diffRatio(baseDecoded, decoded, { channelTolerance });
      if (best === null || diff.ratio > best.ratio) {
        best = { ratio: diff.ratio, changed: diff.changed, total: diff.total };
      }
      if (diff.ratio > threshold && diff.changed >= minPixels) {
        outcome = 'witnessed';
        framePageMs = pageMs;
        diffRatioValue = diff.ratio;
        break;
      }
    }
    if (outcome === 'witnessed') break;
    await sleep(4);
  }

  return {
    kind: 'frame_witness',
    outcome,
    frame_page_ms: framePageMs === null ? null : round(framePageMs, 3),
    frames_total: recorder.frames.length,
    frames_after: framesAfter,
    diff_ratio: diffRatioValue === null ? (best ? round(best.ratio, 6) : 0) : round(diffRatioValue, 6),
    threshold,
    min_pixels: minPixels,
    caret_masked: caret.caret_masked,
    caret_mask_css: caret.caret_mask_css,
    caret_mask_error: caret.caret_mask_error,
    window_ms: windowMs,
    after_page_ms: afterPageMs === null ? null : round(afterPageMs, 3),
    baseline_page_ms:
      base.frame && base.frame.seq >= 0
        ? round(convertFrameToPageMs(base.frame, { ...clock, timestamp_kind: usedKind }), 3)
        : null,
    baseline_source: base.source,
    changed_pixels: best ? best.changed : 0,
    total_pixels: best ? best.total : 0,
    max_diff_ratio: best ? round(best.ratio, 6) : 0,
    timestamp_kind: usedKind,
    time_origin_ms: round(clock.time_origin_ms, 3),
    clock_skew_ms: skewMs === null || skewMs === undefined ? null : round(skewMs, 3),
    clock_skew_method: 'page_clock_offset',
    clock_skew_bound_ms: DEFAULT_SKEW_BOUND_MS,
    clock_skew_acceptable:
      typeof skewMs === 'number' && Math.abs(skewMs) <= DEFAULT_SKEW_BOUND_MS,
    elapsed_ms: Date.now() - startedAt,
  };
}

/**
 * Take the baseline frame of a witness: the picture the witness compares
 * against. A caller that arms the page itself takes the baseline first and
 * hands it to `witnessFrame`.
 */
export async function captureBaseline(page, cdp, options = {}) {
  const recorder = options.recorder || getRecorder(cdp, options);
  await ensureScreencast(recorder);
  const base = await resolveBaseline(page, recorder, options.baseline || null);
  return { ...base, recorder };
}

/**
 * The baseline frame: the one the witness compares against. A caller may hand
 * one over; otherwise the recorder's most recent frame is used, and a page
 * that has not painted yet is forced to paint one.
 */
async function resolveBaseline(page, recorder, baseline) {
  if (baseline) {
    if (typeof baseline === 'string') {
      return { frame: { data: baseline, seq: -1 }, source: 'caller', page_ms: null };
    }
    return { frame: baseline, source: 'caller', page_ms: baseline.page_ms ?? null };
  }
  const last = recorder.frames[recorder.frames.length - 1];
  if (last) return { frame: last, source: 'screencast_frame', page_ms: null };
  // Nothing has painted: force a repaint outside the document and take the
  // frame that follows it.
  await page
    .evaluate(() => {
      const probe = document.createElement('div');
      probe.id = '__witness_baseline__';
      probe.setAttribute(
        'style',
        'position:fixed;left:0;top:0;width:4px;height:4px;outline:1px solid #00ffff;z-index:2147483647',
      );
      document.body.appendChild(probe);
    })
    .catch(() => {});
  const deadline = Date.now() + 1000;
  while (Date.now() < deadline && recorder.frames.length === 0) await sleep(5);
  await page
    .evaluate(() => {
      const probe = document.getElementById('__witness_baseline__');
      if (probe && probe.parentNode) probe.parentNode.removeChild(probe);
    })
    .catch(() => {});
  const deadline2 = Date.now() + 1000;
  while (Date.now() < deadline2 && recorder.frames.length < 2) await sleep(5);
  const frame = recorder.frames[recorder.frames.length - 1];
  return { frame: frame || null, source: frame ? 'forced_repaint' : 'none', page_ms: null };
}

// ------------------------------------------------------------------- renderer

const GPU_RENDERER_PATTERNS = [
  /GL_RENDERER[^\n]*?:\s*([^\n]+)/i,
  /SwiftShader[^\n]*/i,
  /Software only[^\n]*/i,
  /GL_VENDOR[^\n]*?:\s*([^\n]+)/i,
];

/**
 * The renderer string, with the fallback chain the plan asks for:
 * `chrome://gpu` text, then the WebGL unmasked renderer, then the launch args
 * and the Chromium version. The record never carries an empty renderer
 * without a reason.
 */
export async function rendererInfo(browser, page, { timeoutMs = 10000, launchArgs = null } = {}) {
  const chain = [];
  let renderer = '';
  let source = null;
  let why = null;

  const gpu = await readChromeGpu(browser, page, { timeoutMs });
  chain.push(gpu);
  if (gpu.ok && gpu.text) {
    const found = findGpuRenderer(gpu.text);
    if (found) {
      renderer = found;
      source = 'chrome://gpu';
    }
  }

  if (!renderer) {
    const webgl = await readWebglRenderer(page);
    chain.push(webgl);
    if (webgl.ok && webgl.unmasked_renderer) {
      renderer = webgl.unmasked_renderer;
      source = 'webgl_unmasked_renderer';
    }
  }

  const chromiumVersion = browser.version();
  const args = launchArgs || browser.__witnessLaunchArgs || null;
  if (!renderer) {
    why = chain
      .map((step) => `${step.source}: ${step.reason || 'no renderer string'}`)
      .join('; ');
    renderer = `Chromium ${chromiumVersion} (renderer string not exposed by this build)`;
    source = 'launch_args_and_version';
  }

  let headless = null;
  let userAgent = null;
  try {
    userAgent = await page.evaluate(() => navigator.userAgent);
    headless = /Headless/i.test(userAgent || '');
  } catch (error) {
    chain.push({ source: 'user_agent', ok: false, reason: String(error).slice(0, 160) });
  }

  return {
    kind: 'renderer_info',
    renderer,
    source,
    why,
    headless,
    chromium_version: chromiumVersion,
    user_agent: userAgent,
    launch_args: args,
    webgl_unmask_flag: WEBGL_UNMASK_FLAG,
    chain,
  };
}

function findGpuRenderer(text) {
  for (const pattern of GPU_RENDERER_PATTERNS) {
    const match = text.match(pattern);
    if (match) {
      const value = (match[1] || match[0] || '').trim();
      if (value) return value;
    }
  }
  return null;
}

async function readChromeGpu(browser, page, { timeoutMs }) {
  let gpuPage = null;
  try {
    gpuPage = await browser.newPage();
    await gpuPage.goto('chrome://gpu', { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const text = await gpuPage.evaluate(() => document.body ? document.body.innerText : '');
    if (!text || !text.trim()) {
      return { source: 'chrome://gpu', ok: false, reason: 'the page rendered no text' };
    }
    return { source: 'chrome://gpu', ok: true, text: text.slice(0, 4000) };
  } catch (error) {
    return { source: 'chrome://gpu', ok: false, reason: String(error).split('\n')[0].slice(0, 200) };
  } finally {
    if (gpuPage) await gpuPage.close().catch(() => {});
  }
}

async function readWebglRenderer(page) {
  try {
    const info = await page.evaluate(() => {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) return { error: 'no WebGL context' };
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      const out = {
        vendor: gl.getParameter(gl.VENDOR),
        renderer: gl.getParameter(gl.RENDERER),
        version: gl.getParameter(gl.VERSION),
        unmask_extension: Boolean(ext),
      };
      if (ext) {
        out.unmasked_vendor = gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
        out.unmasked_renderer = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
      }
      return out;
    });
    if (info.error) return { source: 'webgl', ok: false, reason: info.error };
    if (!info.unmasked_renderer) {
      return {
        source: 'webgl',
        ok: true,
        reason: 'WEBGL_debug_renderer_info did not expose an unmasked renderer',
        ...info,
      };
    }
    return { source: 'webgl', ok: true, ...info };
  } catch (error) {
    return { source: 'webgl', ok: false, reason: String(error).split('\n')[0].slice(0, 200) };
  }
}

// ----------------------------------------------------------------------- CLI

function parseArgs(argv) {
  const opt = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith('--')) continue;
    const key = arg.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith('--')) {
      opt[key] = true;
    } else {
      opt[key] = next;
      i += 1;
    }
  }
  return opt;
}

const number = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

async function main(argv) {
  const opt = parseArgs(argv);
  const op = opt.op || 'all';
  const url = typeof opt.url === 'string' ? opt.url : 'about:blank';
  const viewport = String(opt.viewport || '800x600')
    .split('x')
    .map((v) => number(v, 800));
  const { chromium } = await loadPlaywright();
  const launchArgs = [
    '--font-render-hinting=none',
    '--disable-lcd-text',
    WEBGL_UNMASK_FLAG,
  ];
  const browser = await chromium.launch({ headless: true, args: launchArgs });
  browser.__witnessLaunchArgs = launchArgs;
  const context = await browser.newContext({
    viewport: { width: viewport[0], height: viewport[1] },
  });
  const page = await context.newPage();
  const sections = {};
  try {
    if (url !== 'about:blank') {
      await page.goto(url, { waitUntil: 'load', timeout: number(opt.timeout, 30000) });
    }
    if (op === 'renderer' || op === 'all') {
      sections.renderer = await rendererInfo(browser, page, { launchArgs });
    }
    if (op === 'frame-interval' || op === 'all') {
      sections.frame_interval = await frameInterval(page, {
        frames: number(opt.frames, 60),
      });
    }
    const needsCdp = op === 'clock-skew' || op === 'witness-frame' || op === 'all';
    let cdp = null;
    let recorder = null;
    if (needsCdp) {
      cdp = await context.newCDPSession(page);
      recorder = getRecorder(cdp, { manageScreencast: true });
      await ensureScreencast(recorder);
    }
    if (op === 'clock-skew' || op === 'all') {
      sections.clock_skew = await clockSkew(page, cdp, {
        boundMs: number(opt.bound, DEFAULT_SKEW_BOUND_MS),
        recorder,
      });
    }
    if (op === 'witness-frame' || op === 'all') {
      // The arm runs *after* the baseline frame is taken, so the baseline is
      // the picture before the change and the witness sees the change.
      const armExpression =
        typeof opt['after-js'] === 'string'
          ? opt['after-js']
          : 'window.__witnessArm ? window.__witnessArm() : null';
      sections.witness_frame = await witnessFrame(page, cdp, {
        arm: () => page.evaluate(armExpression),
        afterPageMs:
          opt['after-page-ms'] !== undefined ? number(opt['after-page-ms'], null) : null,
        windowMs: number(opt['window-ms'], DEFAULT_WINDOW_MS),
        threshold: number(opt.threshold, DEFAULT_THRESHOLD),
        caretMask: opt['caret-mask'] !== 'off' && opt['caret-mask'] !== false,
        recorder,
      });
      sections.witness_frame.marker_page_ms = sections.witness_frame.after_page_ms;
    }
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
  // One operation prints its own record; `--op all` prints the whole run.
  const sectionKey = {
    renderer: 'renderer',
    'frame-interval': 'frame_interval',
    'clock-skew': 'clock_skew',
    'witness-frame': 'witness_frame',
  }[op];
  const record =
    op === 'all'
      ? { kind: 'witness_run', url, ...sections }
      : sectionKey
        ? sections[sectionKey]
        : { kind: 'witness_run', url, error: `unknown op ${op}` };
  const json = JSON.stringify(record);
  if (typeof opt.out === 'string' && opt.out !== '-') {
    fs.writeFileSync(opt.out, `${json}\n`, { flag: 'w' });
  }
  process.stdout.write(`${json}\n`);
}

const invokedDirectly =
  Boolean(process.argv[1]) &&
  path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`witness: ${error && error.stack ? error.stack : error}\n`);
    process.exit(1);
  });
}

export { main as runWitnessCli };
