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
 * Clocks, and what this module can and cannot claim about them
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
 * NAME THINGS HONESTLY (this was issue #130's point): the page-local quantity
 *
 *     (Date.now() - performance.timeOrigin) - performance.now()
 *
 * is the page's wall-clock/monotonic discrepancy since navigation. It is
 * reported as `page_offset_ms`. It is **not** the error of the
 * screencast-to-page conversion, and on its own it proves nothing about a
 * second process's timestamps: a screencast clock shifted by a whole second
 * leaves `page_offset_ms` untouched. The records keep two deprecated aliases
 * (`skew_ms` on a clock check, `clock_skew_ms` on a frame witness) that carry
 * the page offset, because B2–B5 were written against them; readers must not
 * interpret them as a conversion-error bound.
 *
 * What the conversion error actually is, and the bound this module PUBLISHES:
 * the only evidence available inside the page is a *pixel anchor* — force a
 * visible change at a known `performance.now()` and take the first delivered
 * frame (arrival order, no timestamp filter) whose pixels show it. For that
 * frame, causality bounds the conversion from below and the anchor's lag
 * bounds it from above:
 *
 *   - lower bound: -2 ms. A frame cannot show a change before the change was
 *     made, so an anchor converted to less than `change_page_ms - 2 ms` (2 ms
 *     of slop for the change's own performance.now() read and the DOM
 *     mutation around it) contradicts causality and the check fails. Hence
 *     no conversion this module accepts claims the frame earlier than 2 ms
 *     before the event it shows.
 *   - upper bound: the anchor lag bound, `max(3 frame intervals, 250 ms)`
 *     (lax layer, owner decision 2026-11-11: the 100 ms floor refused
 *     wordcraft's 101.3–151.8 ms anchor lags on HF), where the frame
 *     interval is the run's measured median rAF delta
 *     (recorded as `frame_interval_ms`). One frame interval is physics (the
 *     change lands mid-frame); the measured presentation lag of the anchor on
 *     this machine is ≈1 interval (~15 ms, under load ~16 ms), so three
 *     intervals with a 250 ms floor stays far above the observed worst case
 *     while the injected-error class this gate exists for (±1000 ms) sits
 *     well above it.
 *
 * The published claim is therefore **[-2 ms, +lag bound]** — an asymmetric
 * interval, never "±2 ms": nothing in this module proves sub-2 ms accuracy
 * on the positive side, and a positive conversion error is only caught once
 * it pushes the anchor past the lag bound. `conversion` in every clock-check
 * record states this bound.
 *
 * `acceptable` on a clock check is the AND of the recorded `checks`, and a
 * refusal names the failed check in `reason`:
 *
 *   timestamp_kind_known, page_offset_within_bound, page_offset_spread_within_bound
 *   (the spread of the page-offset samples, ≤ 2 ms), anchor_found,
 *   anchor_pixel_checked, anchor_converted, anchor_causality (converted anchor
 *   time ≥ change time − 2 ms), anchor_lag_within_bound. A missing anchor
 *   fails closed. `frame_lag_ms` stays what it always was — the compositor's
 *   presentation latency of the anchor, a property of the machine, never a
 *   clock error.
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
 * the mask, the clock check) so the caller can record why.
 *
 * ---------------------------------------------------------------------------
 * The document region (#130: only document damage is the document's paint)
 * ---------------------------------------------------------------------------
 * A whole-frame diff lets a toolbar recolor, a spinner or any other shell
 * animation publish a "document paint" time, so `witnessFrame` takes an
 * optional `region`: `{selector: '#doc'}` (resolved to its bounding rect) or
 * `{rect: {x, y, width, height}}` in CSS pixels. The rect is converted to
 * device pixels (device pixel ratio recorded) and clamped to the captured
 * frame; every diff — `changed_pixels`, `total_pixels`, `diff_ratio`,
 * `max_diff_ratio` — is then scoped to those pixels. Without a region the
 * record says `document_scoped: false`, nothing is thrown, and the Python
 * validator refuses the record for publication (`not_document_scoped`). A
 * region that cannot be resolved (unknown selector, empty rect) is recorded
 * in `document_region_error` and also leaves the record unscoped.
 *
 * ---------------------------------------------------------------------------
 * How a lane calls this
 * ---------------------------------------------------------------------------
 *   const cdp = await context.newCDPSession(page);
 *   // once per run: the clock check every sample of the run refers to
 *   const check = await clockSkew(page, cdp);
 *   if (!check.acceptable) { ...refuse the run, with check.reason... }
 *   const frame = await witnessFrame(page, cdp, {
 *     afterPageMs: eventPageMs,
 *     region: { selector: '#doc' },
 *     clockCheck: check,          // echoed into the record (clock_check_source)
 *   });
 *
 * `witnessFrame` masks the caret, takes its baseline frame and only then
 * looks for the frame that shows the change, so the caller may pass
 * `afterPageMs` (a page-clock instant) or an `arm` callback that produces the
 * change and returns that instant. `afterPageMs` must be a page-clock value
 * (`performance.now()`), never a driver wall-clock value.
 *
 * Without a `clockCheck` the witness runs the full check inline (a lane that
 * samples often should measure once per run and pass it in). A record's
 * `clock_check.acceptable` is what the Python validator gates publication on;
 * the legacy `clockSkewMs` number alone carries no anchor evidence and is
 * recorded as an explicit unacceptable check. The window is clamped to at
 * least `DEFAULT_WINDOW_MS` (500 ms, per the plan), and a frame counts as
 * seen only once its screencast ack has completed.
 */

import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '../..');

/** The default bound on |page_offset_ms|; a clock check refuses above it.
 * Lax layer (owner decision 2026-11-11): 2 ms -> 5 ms; the page-offset
 * measurement on the HF campaign sat inside ±2 ms for every accepted cell,
 * and the refused wordcraft cells refused on the anchor lag, not here — but
 * the 2 ms edge left no room for scheduler noise on the shared hosts. The
 * bound is recorded on every clock check (bound_ms / clock_skew_bound_ms). */
export const DEFAULT_SKEW_BOUND_MS = 5;
/** The bound on the spread of the page-offset samples (check d of the gate). */
export const PAGE_OFFSET_SPREAD_BOUND_MS = 2;
/**
 * The causality slop, in ms: a frame cannot show a change before the change
 * was made, so an anchor converted below `change_page_ms - CAUSALITY_SLOP_MS`
 * fails the gate. The 2 ms covers the change's own performance.now() read and
 * the DOM mutation around it. This is the published LOWER bound of the
 * conversion: no accepted conversion claims a frame more than 2 ms before
 * the event it shows.
 */
export const CAUSALITY_SLOP_MS = 2;
/**
 * The anchor lag bound is `max(ANCHOR_LAG_BOUND_INTERVALS frame intervals,
 * ANCHOR_LAG_BOUND_MIN_MS)`. One interval is physics (a change lands
 * mid-frame); the measured anchor lag is ≈1 interval (~15–16 ms here, loaded
 * or not), so 3 intervals with a 100 ms floor is ~6x the observed worst
 * case, and the injected ±1000 ms error class sits 10x above it. This is the
 * published UPPER bound of the conversion (see the module header).
 * Lax layer (owner decision 2026-11-11): the floor moves 100 ms -> 250 ms.
 * HF shakedown evidence: wordcraft's anchor frame lags ran 101.3–151.8 ms
 * (e.g. e2-wordcraft C10 cells, frame_lag 107.9–151.8 ms over a 100 ms
 * bound), refusing C10/C11 and the document lane's C14 clock checks while
 * the conversion itself stayed sound; 250 ms keeps a ≥1.6x margin over the
 * worst observed lag. The bound is recomputed and recorded on every record
 * (lag_bound_ms + lag_bound_rule) so the trial discloses it.
 */
export const ANCHOR_LAG_BOUND_INTERVALS = 3;
export const ANCHOR_LAG_BOUND_MIN_MS = 250;
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

/**
 * Compare two decoded frames; the ratio of pixels that differ. With a
 * `region` ({x, y, width, height} in frame/device pixels, clamped to the
 * frame) only the pixels inside it are compared and the ratio's denominator
 * is the region's pixel count; without one the whole frame is compared.
 */
export function diffRatio(
  a,
  b,
  { channelTolerance = DEFAULT_CHANNEL_TOLERANCE, region = null } = {},
) {
  const totalAll = a.width * a.height;
  if (!totalAll) return { ratio: 1, changed: 0, total: 0, comparable: false };
  if (a.width !== b.width || a.height !== b.height) {
    return { ratio: 1, changed: totalAll, total: totalAll, comparable: false };
  }
  let x0 = 0;
  let y0 = 0;
  let x1 = a.width;
  let y1 = a.height;
  if (region) {
    x0 = Math.max(0, Math.floor(region.x));
    y0 = Math.max(0, Math.floor(region.y));
    x1 = Math.min(a.width, Math.ceil(region.x + region.width));
    y1 = Math.min(a.height, Math.ceil(region.y + region.height));
    if (x1 <= x0 || y1 <= y0) {
      return { ratio: 0, changed: 0, total: 0, comparable: false };
    }
  }
  const total = (x1 - x0) * (y1 - y0);
  if (!total) return { ratio: 1, changed: 0, total: 0, comparable: false };
  const da = a.data;
  const db = b.data;
  let changed = 0;
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const i = y * a.width + x;
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
  }
  return { ratio: changed / total, changed, total, comparable: true };
}

// ------------------------------------------------------------------- recorder

const recorders = new WeakMap();

/**
 * The frame recorder: it listens to `Page.screencastFrame`, acks every frame
 * (an unacked frame stops the screencast) and keeps the frames with their
 * metadata. One recorder per CDP session, so the lanes can share it.
 *
 * A frame is recorded with `ack: 'pending'` and becomes `'acked'` (or
 * `'error'`) when its `Page.screencastFrameAck` settles: the witness counts a
 * frame as seen only once the ack completed, so a sample never rests on a
 * frame the compositor was never told it could send past (#130).
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
    const frame = {
      data: event.data,
      ts: typeof metadata.timestamp === 'number' ? metadata.timestamp : null,
      mono:
        typeof metadata.monotonicTimestamp === 'number' ? metadata.monotonicTimestamp : null,
      receipt_ms: Date.now(),
      seq: recorder.frames.length,
      ack: 'pending',
    };
    recorder.frames.push(frame);
    if (recorder.frames.length > 1200) {
      const drop = recorder.frames.length - 1200;
      recorder.frames.splice(0, drop);
      recorder.decoded.clear();
    }
    Promise.resolve()
      .then(() => cdp.send('Page.screencastFrameAck', { sessionId: event.sessionId }))
      .then(
        () => {
          frame.ack = 'acked';
        },
        () => {
          frame.ack = 'error';
          /* the session may be gone; the frame is kept, never counted as seen */
        },
      );
  };
  cdp.on('Page.screencastFrame', recorder.listener);
  recorders.set(cdp, recorder);
  return recorder;
}

/**
 * Wait for a frame's screencast ack to settle (bounded); returns the final
 * ack state ('pending' on timeout, 'acked' or 'error' otherwise).
 */
export async function frameAckSettled(frame, timeoutMs = 400) {
  const deadline = Date.now() + timeoutMs;
  while (frame.ack === 'pending' && Date.now() < deadline) await sleep(2);
  return frame.ack;
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

export async function ensureScreencast(recorder) {
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

export async function pageClock(page, extra = {}) {
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

export function convertFrameToPageMs(frame, clock) {
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
    await page.evaluate((css) => {
      // The DOM is the cache: navigation/removal requires a fresh mask, and
      // concurrent callers execute this check-and-insert atomically.
      const selector = 'style[data-perf-caret-mask]';
      let style = document.querySelector(selector);
      if (!style) {
        style = document.createElement('style');
        style.setAttribute('data-perf-caret-mask', '');
        (document.head || document.documentElement).appendChild(style);
      }
      if (style.textContent !== css) style.textContent = css;
    }, CARET_MASK_CSS);
    return { caret_masked: true, caret_mask_css: CARET_MASK_CSS, caret_mask_error: null };
  } catch (error) {
    return {
      caret_masked: false,
      caret_mask_css: CARET_MASK_CSS,
      caret_mask_error: String(error).slice(0, 200),
    };
  }
}

/** Drop a mask left by an earlier sample. A caret retry that stays masked cannot paint. */
export async function removeCaretMask(page) {
  try {
    const removed = await page.evaluate(() => {
      const style = document.querySelector('style[data-perf-caret-mask]');
      if (!style) return false;
      style.remove();
      return true;
    });
    return {
      caret_masked: false,
      caret_mask_css: null,
      caret_mask_error: null,
      caret_mask_removed: removed === true,
    };
  } catch (error) {
    return {
      caret_masked: false,
      caret_mask_css: null,
      caret_mask_error: String(error).slice(0, 200),
      caret_mask_removed: false,
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

// ------------------------------------------------------------------- clock check

/**
 * The clock check (the probe earlier layers called "the clock-skew probe").
 *
 * It masks the caret, measures the page-local clock offset
 * (`page_offset_ms`, with its spread) and the frame interval, forces a
 * visible change at a known `performance.now()` and finds, by pixels in
 * arrival order, the first delivered frame that shows it — the pixel anchor.
 * The anchor is what the screencast->page-time conversion is proven on; the
 * page offset alone proves nothing about a second process's timestamps.
 *
 * `acceptable` is the AND of the recorded `checks` (see the module header);
 * a refusal names the failed check in `reason`. The published conversion
 * bound — [-2 ms by causality, +`lag_bound_ms`] — is stated in `conversion`.
 *
 * `skew_ms` is a DEPRECATED alias of `page_offset_ms`, kept because B2–B5
 * read it; it is not a conversion-error bound.
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
    frameIntervalMs = null,
    caretMask = true,
    settleMs = 200,
  } = {},
) {
  const recorder = givenRecorder || getRecorder(cdp, { manageScreencast });
  await ensureScreencast(recorder);

  const caret = caretMask
    ? await injectCaretMask(page)
    : { caret_masked: false, caret_mask_css: CARET_MASK_CSS, caret_mask_error: null };
  if (caretMask) await sleep(settleMs);

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
  const spreadMs = offsets.length ? Math.max(...offsets) - Math.min(...offsets) : null;

  const interval =
    typeof frameIntervalMs === 'number' && Number.isFinite(frameIntervalMs)
      ? { median_ms: round(frameIntervalMs, 3), count: 0, source: 'caller' }
      : await frameInterval(page, { frames: 60 });
  const intervalMs = typeof interval.median_ms === 'number' ? interval.median_ms : null;
  const lagBoundMs = Math.max(
    intervalMs === null ? 0 : ANCHOR_LAG_BOUND_INTERVALS * intervalMs,
    ANCHOR_LAG_BOUND_MIN_MS,
  );

  const anchor = await anchorFrame(page, recorder, clock, { waitMs: changeWaitMs });
  const kind = anchor.frame
    ? detectTimestampKind(anchor.frame)
    : recorder.frames.length
      ? detectTimestampKind(recorder.frames[recorder.frames.length - 1])
      : { kind: 'unknown', field: null };
  clock.timestamp_kind = kind.kind;

  const anchorPageMs = anchor.frame_page_ms;
  const anchorLagMs =
    anchorPageMs === null || anchorPageMs === undefined
      ? null
      : anchorPageMs - anchor.change_page_ms;

  const checks = {
    timestamp_kind_known: kind.kind !== 'unknown',
    page_offset_within_bound:
      typeof pageOffsetMs === 'number' && Math.abs(pageOffsetMs) <= boundMs,
    page_offset_spread_within_bound:
      typeof spreadMs === 'number' && spreadMs <= PAGE_OFFSET_SPREAD_BOUND_MS,
    anchor_found: Boolean(anchor.frame),
    anchor_pixel_checked: anchor.pixel_checked === true,
    anchor_converted: anchorPageMs !== null && anchorPageMs !== undefined,
    anchor_causality:
      anchorPageMs !== null &&
      anchorPageMs !== undefined &&
      anchorPageMs >= anchor.change_page_ms - CAUSALITY_SLOP_MS,
    anchor_lag_within_bound: anchorLagMs !== null && anchorLagMs <= lagBoundMs,
  };
  // The refusal names the first failed check, in this order.
  const reasonOrder = [
    ['timestamp_kind_known', 'timestamp_kind_unknown'],
    ['anchor_found', 'anchor_missing'],
    ['anchor_pixel_checked', 'anchor_not_pixel_checked'],
    ['anchor_converted', 'anchor_not_converted'],
    ['anchor_causality', 'anchor_before_change'],
    ['anchor_lag_within_bound', 'anchor_lag_above_bound'],
    ['page_offset_within_bound', 'page_offset_above_bound'],
    ['page_offset_spread_within_bound', 'page_offset_spread_above_bound'],
  ];
  let reason = null;
  for (const [key, name] of reasonOrder) {
    if (!checks[key]) {
      reason = name;
      break;
    }
  }

  return {
    kind: 'clock_skew',
    acceptable: reason === null,
    reason,
    checks,
    method: 'page_clock_offset+pixel_anchor',
    timestamp_kind: kind.kind,
    timestamp_field: kind.field,
    bound_ms: boundMs,
    page_offset_ms: round(pageOffsetMs, 3),
    page_offset_samples: offsets.map((v) => round(v, 3)),
    page_offset_spread_ms: round(spreadMs, 3),
    // DEPRECATED alias of page_offset_ms (B2–B5 read it). Not a conversion
    // error; never gate on it alone.
    skew_ms: round(pageOffsetMs, 3),
    time_origin_ms: round(clock.time_origin_ms, 3),
    change_page_ms: round(anchor.change_page_ms, 3),
    frame_page_ms: anchorPageMs === null || anchorPageMs === undefined ? null : round(anchorPageMs, 3),
    frame_lag_ms: anchorLagMs === null ? null : round(anchorLagMs, 3),
    frame_monotonic_ms: anchor.frame
      ? round(typeof anchor.frame.mono === 'number' ? anchor.frame.mono * 1000 : null, 3)
      : null,
    frames_total: recorder.frames.length,
    anchor_pixel_checked: anchor.pixel_checked,
    anchor_diff_ratio:
      anchor.frame_diff_ratio === null || anchor.frame_diff_ratio === undefined
        ? null
        : round(anchor.frame_diff_ratio, 6),
    anchor_probe_region_px: anchor.probe_region_px,
    frame_interval_ms: intervalMs,
    frame_interval_source: interval.source || 'raf_delta',
    frame_interval_samples: interval.count ?? null,
    lag_bound_ms: round(lagBoundMs, 3),
    lag_bound_rule: `max(${ANCHOR_LAG_BOUND_INTERVALS} frame intervals, ${ANCHOR_LAG_BOUND_MIN_MS} ms)`,
    conversion: {
      formula: 'page_ms = timestamp * 1000 - performance.timeOrigin',
      error_lower_ms: -CAUSALITY_SLOP_MS,
      error_lower_why: 'causality: a frame cannot show a change before it was made (2 ms slop for the change timestamp)',
      error_upper_ms: round(lagBoundMs, 3),
      error_upper_why: 'the anchor lag bound: a positive conversion error is caught once it pushes the anchor past it',
      published: `[-${CAUSALITY_SLOP_MS} ms, +${round(lagBoundMs, 3)} ms] (never "\u00b12 ms")`,
    },
    caret_masked: caret.caret_masked,
    caret_mask_error: caret.caret_mask_error,
    notes: [
      'page_offset_ms is the page-local wall/monotonic discrepancy; it is NOT the screencast conversion error and never gates alone',
      'the conversion is proven by the pixel anchor: the first delivered frame whose probe region changed, chosen in arrival order with no timestamp filter',
      `the published conversion bound is [-${CAUSALITY_SLOP_MS} ms, +${round(lagBoundMs, 3)} ms]; the anchor is refused outside it`,
      'frame_lag_ms is the compositor presentation latency of the anchor, not a clock error',
      kind.kind === 'epoch_seconds'
        ? 'metadata.timestamp is an epoch reading; page_ms = timestamp*1000 - performance.timeOrigin'
        : `metadata.timestamp is not an epoch reading (${kind.kind}); the conversion cannot be trusted without an anchor`,
    ],
  };
}

/**
 * The `token: detail` refusal string for a failed `clockSkew` record. The
 * token is `reason` verbatim, except `page_offset_above_bound`, which keeps
 * the established cross-lane token `clock_skew_above_bound` (the Python
 * validator's name for the same check). No other failed check may carry that
 * token: an in-bound signed offset such as -0.7 ms is not "above the bound",
 * and the failing check — e.g. wordcraft's `anchor_lag_above_bound` — must be
 * named honestly.
 */
export function clockSkewRefusalReason(skew) {
  const reason = (skew && skew.reason) || 'clock_check_not_acceptable';
  const token = reason === 'page_offset_above_bound' ? 'clock_skew_above_bound' : reason;
  const details = {
    timestamp_kind_unknown: () =>
      'the screencast timestamp kind is ' + skew.timestamp_kind +
      ', so a frame cannot be placed in the page clock',
    anchor_missing: () => 'no screencast frame carries the change',
    anchor_not_pixel_checked: () => 'the anchor frame could not be pixel-checked against the change',
    anchor_not_converted: () => 'the anchor frame could not be placed in the page clock',
    anchor_before_change: () => 'the anchor frame precedes the change it must prove',
    anchor_lag_above_bound: () =>
      'the anchor frame lag ' + skew.frame_lag_ms + ' ms is above the bound of ' +
      skew.lag_bound_ms + ' ms',
    page_offset_above_bound: () =>
      'the clock skew ' + skew.skew_ms + ' ms is above the bound of ' + skew.bound_ms + ' ms',
    page_offset_spread_above_bound: () =>
      'the clock skew spread ' + skew.page_offset_spread_ms + ' ms is above the bound',
  };
  const detail = details[reason];
  return token + ': ' + (detail ? detail() : 'the clock check failed');
}

/**
 * Force a visible change at a known page time and find the frame that shows
 * it: the first delivered frame, in arrival order, whose pixels differ from
 * the pre-change baseline inside the probe's own 8x8 region. There is NO
 * timestamp filter here — the anchor must be chosen by pixels, or a wrong
 * conversion would simply lose its own proof frame instead of failing the
 * gate (#130 defect 1). The frame's ack must have completed before it counts.
 */
async function anchorFrame(page, recorder, clock, { waitMs }) {
  // A baseline frame must exist before the change, so the anchor is always
  // proven by pixels.
  const baselineWait = Date.now() + 1000;
  while (recorder.frames.length === 0 && Date.now() < baselineWait) await sleep(5);
  const before = recorder.frames.length;
  const baselineFrame = recorder.frames[before - 1] || null;
  const baselineDecoded = baselineFrame ? decodeFrame(recorder, baselineFrame) : null;

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
  const dpr = await page.evaluate(() => window.devicePixelRatio || 1).catch(() => 1);
  // The probe's own corner of the frame: an unrelated damage elsewhere on
  // the page (a spinner, a caret that survived the mask) must not become the
  // anchor.
  const probeRegion = {
    x: 0,
    y: 0,
    width: Math.max(1, Math.round(8 * dpr)),
    height: Math.max(1, Math.round(8 * dpr)),
  };

  const deadline = Date.now() + waitMs;
  let found = null;
  let pixelChecked = false;
  while (Date.now() < deadline && !found) {
    for (let i = before; i < recorder.frames.length; i++) {
      const frame = recorder.frames[i];
      if (frame.ack === 'pending') {
        if ((await frameAckSettled(frame)) !== 'acked') continue;
      } else if (frame.ack !== 'acked') {
        continue;
      }
      if (!baselineDecoded || !baselineFrame) break; // nothing to compare against
      if (frame.data === baselineFrame.data) continue; // identical bytes: identical pixels
      const decoded = decodeFrame(recorder, frame);
      if (!decoded) continue;
      const diff = diffRatio(baselineDecoded, decoded, { region: probeRegion });
      if (diff.ratio > DEFAULT_THRESHOLD && diff.changed >= DEFAULT_MIN_PIXELS) {
        const kind = detectTimestampKind(frame);
        const pageMs =
          kind.kind === 'unknown'
            ? null
            : convertFrameToPageMs(frame, { ...clock, timestamp_kind: kind.kind });
        found = { frame, pageMs, kind, diff: diff.ratio };
        pixelChecked = true;
        break;
      }
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
    return {
      change_page_ms: change,
      frame_page_ms: null,
      frame_lag_ms: null,
      frame: null,
      pixel_checked: pixelChecked,
      probe_region_px: probeRegion,
    };
  }
  return {
    change_page_ms: change,
    frame_page_ms: found.pageMs,
    frame_lag_ms: found.pageMs === null ? null : found.pageMs - change,
    frame: found.frame,
    pixel_checked: pixelChecked,
    frame_diff_ratio: found.diff,
    probe_region_px: probeRegion,
  };
}

// ----------------------------------------------------------------- frame witness

/**
 * Resolve the document region of a witness: `{selector}` (its bounding rect)
 * or `{rect}` in CSS pixels, converted to device pixels and clamped to the
 * captured frame. The result says whether the diff is document-scoped; a
 * region that cannot be resolved is an error in the record, never a throw.
 */
async function resolveRegion(page, region, frameDecoded) {
  if (!region || typeof region !== 'object') {
    return {
      scoped: false,
      source: null,
      selector: null,
      rect_css: null,
      rect_device: null,
      dpr: null,
      error: null,
    };
  }
  let rect = null;
  let source = null;
  let selector = null;
  let error = null;
  try {
    if (typeof region.selector === 'string' && region.selector) {
      selector = region.selector;
      const box = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: r.left, y: r.top, width: r.width, height: r.height };
      }, selector);
      if (!box) {
        error = `selector ${selector} matched no element`;
      } else {
        rect = box;
        source = 'selector';
      }
    } else if (region.rect && typeof region.rect === 'object') {
      const r = region.rect;
      if (
        [r.x, r.y, r.width, r.height].every(
          (v) => typeof v === 'number' && Number.isFinite(v),
        )
      ) {
        rect = { x: r.x, y: r.y, width: r.width, height: r.height };
        source = 'rect';
      } else {
        error = 'region.rect needs finite numbers x, y, width, height';
      }
    } else {
      error = 'region needs {selector} or {rect}';
    }
  } catch (e) {
    error = String(e).split('\n')[0].slice(0, 200);
  }
  if (error) {
    return {
      scoped: false,
      source,
      selector,
      rect_css: null,
      rect_device: null,
      dpr: null,
      error,
    };
  }
  const dpr = await page
    .evaluate(() => window.devicePixelRatio || 1)
    .catch(() => 1);
  let device = {
    x: Math.round(rect.x * dpr),
    y: Math.round(rect.y * dpr),
    width: Math.round(rect.width * dpr),
    height: Math.round(rect.height * dpr),
  };
  if (frameDecoded) {
    // Clamp to the captured frame: the document's visible part is what the
    // witness can see.
    const x0 = Math.max(0, device.x);
    const y0 = Math.max(0, device.y);
    const x1 = Math.min(frameDecoded.width, device.x + device.width);
    const y1 = Math.min(frameDecoded.height, device.y + device.height);
    device = {
      x: x0,
      y: y0,
      width: Math.max(0, x1 - x0),
      height: Math.max(0, y1 - y0),
    };
  }
  if (device.width < 1 || device.height < 1) {
    return {
      scoped: false,
      source,
      selector,
      rect_css: rect,
      rect_device: device,
      dpr,
      error: 'the region is empty in the captured frame (outside the viewport?)',
    };
  }
  return {
    scoped: true,
    source,
    selector,
    rect_css: rect,
    rect_device: device,
    dpr,
    error: null,
  };
}

/**
 * The frame witness: the first acked screencast frame at or after
 * `afterPageMs` (in the page's clock) whose decoded pixels differ from the
 * baseline frame by more than `threshold` — scoped to the document `region`
 * when one is given (#130: damage outside the document is not the document's
 * paint). Without a region the record is `document_scoped: false` and the
 * Python validator refuses it for publication; nothing is thrown.
 *
 * `baseline` may be a frame from the recorder, a base64 PNG string, or null
 * (the recorder's most recent frame is used; if the page has not painted yet,
 * the module forces one repaint and takes the frame after it). The caret is
 * masked before the baseline is taken, and the record says so.
 *
 * The record carries the run's clock check: pass `clockCheck` (a `clockSkew()`
 * record, measured once per run) or the witness runs the full check inline;
 * `clock_check.acceptable` is what publication is gated on. The legacy
 * `clockSkewMs` number alone carries no anchor evidence and is recorded as an
 * explicitly unacceptable check. The window is clamped to at least
 * `DEFAULT_WINDOW_MS`.
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
    clockCheck = null,
    region = null,
    quietMs = 0,
    quietBudgetMs = 8000,
  } = {},
) {
  const recorder = givenRecorder || getRecorder(cdp, { manageScreencast });
  await ensureScreencast(recorder);
  const windowRequestedMs = windowMs;
  if (windowMs < DEFAULT_WINDOW_MS) windowMs = DEFAULT_WINDOW_MS;
  const clock = await pageClock(page);
  const first = recorder.frames[0];
  const kind = first ? detectTimestampKind(first) : { kind: 'unknown', field: null };
  clock.timestamp_kind = kind.kind;

  // The clock check this sample is gated on (#130 defect 1/3): the run's
  // check when the caller measured one, a full inline check by default. A
  // bare page-offset number is NOT a check and is recorded as such.
  let check = null;
  let checkSource = null;
  if (clockCheck && typeof clockCheck === 'object' && clockCheck.kind === 'clock_skew') {
    check = clockCheck;
    checkSource = 'caller';
  } else if (typeof clockSkewMs === 'number' && Number.isFinite(clockSkewMs)) {
    checkSource = 'page_offset_only';
    check = {
      kind: 'clock_skew',
      acceptable: false,
      reason: 'no_anchor_evidence',
      checks: null,
      method: 'page_clock_offset',
      page_offset_ms: round(clockSkewMs, 3),
      bound_ms: DEFAULT_SKEW_BOUND_MS,
      notes: [
        'clockSkewMs carries only the page-local offset; the pixel anchor was not run for this sample, so the screencast conversion is unproven',
      ],
    };
  } else {
    check = await clockSkew(page, cdp, { recorder });
    checkSource = 'inline';
  }

  const caret = caretMask ? await injectCaretMask(page) : await removeCaretMask(page);
  // Unmasking paints. Settle that paint into the baseline so the sample is the
  // next input, not the stylesheet removal.
  if (caretMask || caret.caret_mask_removed) await sleep(settleMs);

  // The baseline must be the picture *before* the change, so it is taken
  // before the page is armed.
  let base = await resolveBaseline(page, recorder, baseline);
  let baseDecoded = base.frame ? decodeFrame(recorder, base.frame) : null;

  // The document region is resolved before the page is armed, so a change
  // that moves the layout cannot move its own target rect.
  const scope = await resolveRegion(page, region, baseDecoded);
  const diffRegion = scope.scoped ? scope.rect_device : null;
  const wallStart = Date.now();
  let usedKindEarly = kind.kind;
  let quietAckSkipped = 0;

  // r3c07b ruling #1: the watched box must be shown quiet — no changed pixel
  // inside the region — for at least quietMs before the page is armed. The
  // screencast is the same witness that later times the input: a composited
  // frame that differs from the baseline inside the region is a repaint the
  // click could borrow. A change resets the quiet clock rather than refusing
  // outright — a one-off settle paint may still leave a provably quiet box —
  // but a box that repaints periodically (a blinking caret, a hover, a
  // toolbar) never reaches quiet inside the budget and the sample is refused
  // before the arm ever fires.
  let quiet_window = null;
  if (quietMs > 0) {
    // The watch floor is the baseline's own page time when it is a real
    // screencast frame: a repaint between the baseline capture and this
    // point would otherwise slip through the floor uncounted. Only frames
    // at or before the baseline are skipped — their pixels ARE the picture
    // the diff compares against.
    let watchStartPageMs =
      base.frame && base.frame.seq >= 0
        ? convertFrameToPageMs(base.frame, { ...clock, timestamp_kind: usedKindEarly })
        : null;
    if (watchStartPageMs === null) {
      watchStartPageMs = await page.evaluate(() => performance.now()).catch(() => null);
    }
    const events = [];
    let changesSeen = 0;
    let quietSince = watchStartPageMs;
    let observedMs = 0;
    let proven = false;
    let checkedQuiet = 0;
    const quietDeadline = Date.now() + quietBudgetMs;
    while (Date.now() < quietDeadline) {
      for (let i = checkedQuiet; i < recorder.frames.length; i++) {
        const frame = recorder.frames[i];
        checkedQuiet = i + 1;
        if (frame.ack === 'pending') {
          if ((await frameAckSettled(frame)) !== 'acked') {
            quietAckSkipped += 1;
            continue;
          }
        } else if (frame.ack !== 'acked') {
          quietAckSkipped += 1;
          continue;
        }
        const frameKind = detectTimestampKind(frame);
        const effectiveKind = frameKind.kind === 'unknown' ? kind.kind : frameKind.kind;
        const pageMs = convertFrameToPageMs(frame, {
          ...clock,
          timestamp_kind: effectiveKind,
        });
        if (pageMs === null) continue;
        if (effectiveKind !== 'unknown') usedKindEarly = effectiveKind;
        // A frame that predates the watch carries pre-watch pixels; it cannot
        // prove or break quiet for this window.
        if (watchStartPageMs !== null && pageMs <= watchStartPageMs) continue;
        if (!baseDecoded) continue;
        if (base.frame && frame.data === base.frame.data) continue;
        const decoded = decodeFrame(recorder, frame);
        if (!decoded) continue;
        const diff = diffRegion
          ? diffRatio(baseDecoded, decoded, { channelTolerance, region: diffRegion })
          : diffRatio(baseDecoded, decoded, { channelTolerance });
        if (diff.comparable && diff.ratio > threshold && diff.changed >= minPixels) {
          changesSeen += 1;
          if (events.length < 12) {
            events.push({
              frame_page_ms: round(pageMs, 3),
              changed: diff.changed,
              ratio: round(diff.ratio, 6),
            });
          }
          quietSince = pageMs;
        }
      }
      const nowPageMs = await page
        .evaluate(() => performance.now())
        .catch(() => null);
      if (nowPageMs !== null && quietSince !== null) {
        observedMs = nowPageMs - quietSince;
      }
      if (quietSince !== null && observedMs >= quietMs) {
        proven = true;
        break;
      }
      await sleep(4);
    }
    const violated = !proven && changesSeen > 0;
    quiet_window = {
      required_ms: quietMs,
      budget_ms: quietBudgetMs,
      proven,
      observed_ms: round(observedMs, 3),
      start_page_ms: watchStartPageMs === null ? null : round(watchStartPageMs, 3),
      end_page_ms:
        watchStartPageMs === null ? null : round(watchStartPageMs + observedMs, 3),
      changes_seen: changesSeen,
      events,
      exhausted: !proven,
      violated,
    };
    if (!proven) {
      // A box that was not quiet before the click is a named refusal: the arm
      // never fires and there is no frame to read as the input's paint.
      return {
        kind: 'frame_witness',
        outcome: 'no_frame',
        frame_page_ms: null,
        frames_total: recorder.frames.length,
        frames_after: 0,
        frames_ack_skipped: quietAckSkipped,
        diff_ratio: 0,
        threshold,
        min_pixels: minPixels,
        caret_masked: caret.caret_masked,
        caret_mask_css: caret.caret_mask_css,
        caret_mask_error: caret.caret_mask_error,
        window_ms: windowMs,
        window_requested_ms: windowRequestedMs,
        after_page_ms: afterPageMs === null ? null : round(afterPageMs, 3),
        baseline_page_ms:
          base.frame && base.frame.seq >= 0
            ? round(
                convertFrameToPageMs(base.frame, { ...clock, timestamp_kind: usedKindEarly }),
                3,
              )
            : null,
        baseline_source: base.source,
        document_scoped: scope.scoped,
        document_region: scope.scoped
          ? {
              source: scope.source,
              selector: scope.selector,
              rect_css_px: scope.rect_css,
              rect_device_px: scope.rect_device,
              device_pixel_ratio: scope.dpr,
            }
          : null,
        document_region_error: scope.error,
        region_pixels: scope.scoped
          ? scope.rect_device.width * scope.rect_device.height
          : null,
        changed_pixels: 0,
        total_pixels: 0,
        max_diff_ratio: 0,
        timestamp_kind: usedKindEarly,
        time_origin_ms: round(clock.time_origin_ms, 3),
        clock_check: check,
        clock_check_source: checkSource,
        clock_skew_ms:
          check.page_offset_ms == null ? null : round(check.page_offset_ms, 3),
        clock_skew_method: check.method || null,
        clock_skew_bound_ms: check.bound_ms ?? DEFAULT_SKEW_BOUND_MS,
        clock_skew_acceptable: check.acceptable === true,
        elapsed_ms: Date.now() - wallStart,
        quiet_window,
      };
    }
    // The quiet window ran after the baseline was taken; a frame that painted
    // inside the region during the watch (and reset the quiet clock) must not
    // later read as the input's own paint. Re-baseline on the latest picture.
    const refreshed = await resolveBaseline(page, recorder, null);
    base = refreshed;
    baseDecoded = base.frame ? decodeFrame(recorder, base.frame) : null;
  }

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

  const offset = check.page_offset_ms ?? null;

  const startedAt = Date.now();
  const deadline = startedAt + windowMs;
  let checked = 0;
  let framesAfter = 0;
  let ackSkipped = 0;
  let best = null;
  let outcome = 'no_frame';
  let framePageMs = null;
  let diffRatioValue = null;
  let usedKind = usedKindEarly;

  while (Date.now() < deadline) {
    for (let i = checked; i < recorder.frames.length; i++) {
      const frame = recorder.frames[i];
      checked = i + 1;
      // A frame counts as seen only once its screencast ack completed.
      if (frame.ack === 'pending') {
        if ((await frameAckSettled(frame)) !== 'acked') {
          ackSkipped += 1;
          continue;
        }
      } else if (frame.ack !== 'acked') {
        ackSkipped += 1;
        continue;
      }
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
      const diff = diffRatio(baseDecoded, decoded, { channelTolerance, region: diffRegion });
      if (best === null || diff.ratio > best.ratio) {
        best = { ratio: diff.ratio, changed: diff.changed, total: diff.total };
      }
      if (diff.comparable && diff.ratio > threshold && diff.changed >= minPixels) {
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
    frames_ack_skipped: ackSkipped,
    diff_ratio: diffRatioValue === null ? (best ? round(best.ratio, 6) : 0) : round(diffRatioValue, 6),
    threshold,
    min_pixels: minPixels,
    caret_masked: caret.caret_masked,
    caret_mask_css: caret.caret_mask_css,
    caret_mask_error: caret.caret_mask_error,
    window_ms: windowMs,
    window_requested_ms: windowRequestedMs,
    after_page_ms: afterPageMs === null ? null : round(afterPageMs, 3),
    baseline_page_ms:
      base.frame && base.frame.seq >= 0
        ? round(convertFrameToPageMs(base.frame, { ...clock, timestamp_kind: usedKind }), 3)
        : null,
    baseline_source: base.source,
    document_scoped: scope.scoped,
    document_region: scope.scoped
      ? {
          source: scope.source,
          selector: scope.selector,
          rect_css_px: scope.rect_css,
          rect_device_px: scope.rect_device,
          device_pixel_ratio: scope.dpr,
        }
      : null,
    document_region_error: scope.error,
    region_pixels: scope.scoped
      ? scope.rect_device.width * scope.rect_device.height
      : null,
    // changed/total/max are scoped to the region when one is given
    changed_pixels: best ? best.changed : 0,
    total_pixels: best ? best.total : 0,
    max_diff_ratio: best ? round(best.ratio, 6) : 0,
    timestamp_kind: usedKind,
    time_origin_ms: round(clock.time_origin_ms, 3),
    clock_check: check,
    clock_check_source: checkSource,
    // DEPRECATED aliases (B2–B5 read them): the page-local offset, and the
    // clock check's own verdict. Neither is a conversion-error bound.
    clock_skew_ms: offset === null ? null : round(offset, 3),
    clock_skew_method: check.method || null,
    clock_skew_bound_ms: check.bound_ms ?? DEFAULT_SKEW_BOUND_MS,
    clock_skew_acceptable: check.acceptable === true,
    elapsed_ms: Date.now() - startedAt,
    ...(quiet_window ? { quiet_window } : {}),
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
    let clockRecord = null;
    if (needsCdp) {
      cdp = await context.newCDPSession(page);
      recorder = getRecorder(cdp, { manageScreencast: true });
      await ensureScreencast(recorder);
    }
    if (op === 'clock-skew' || op === 'all') {
      sections.clock_skew = clockRecord = await clockSkew(page, cdp, {
        boundMs: number(opt.bound, DEFAULT_SKEW_BOUND_MS),
        recorder,
      });
    }
    if (op === 'witness-frame' || op === 'all') {
      // The document region: a CSS selector or an explicit rect (CSS px).
      let region = null;
      if (typeof opt.region === 'string' && opt.region) {
        region = { selector: opt.region };
      } else if (typeof opt['region-rect'] === 'string') {
        const parts = opt['region-rect'].split(',').map(Number);
        if (parts.length === 4 && parts.every((v) => Number.isFinite(v))) {
          region = {
            rect: { x: parts[0], y: parts[1], width: parts[2], height: parts[3] },
          };
        }
      }
      // One clock check per run, shared with the witness, exactly as a lane
      // is told to do it.
      if (!clockRecord) {
        clockRecord = await clockSkew(page, cdp, { recorder });
      }
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
        clockCheck: clockRecord,
        region,
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
