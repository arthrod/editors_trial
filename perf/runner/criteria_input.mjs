/**
 * Criteria C04 / C07 / C08 / C09 on one page load: deferred work, hit testing,
 * undo, and bulk insertion.
 *
 * Imported by `warm_cold_browser.mjs` when `--criteria` names at least one of
 * these ids. The probe never writes a trial: it emits the payload below and the
 * Python side writes one immutable attempt per criterion with `write_attempt`.
 *
 * ---------------------------------------------------------------------------
 * Usage (a dev server is already listening; run from `harness/ui` so the
 * bundled Playwright resolves):
 *
 *   node perf/runner/warm_cold_browser.mjs \
 *     --driver playwright \
 *     --editor plate \
 *     --criteria C04,C07,C09,C08 \
 *     --url http://127.0.0.1:5208/ \
 *     --corpus /abs/path/micro-paragraphs.docx \
 *     --corpus-route /corpus.docx \
 *     --ready-selector ".status-ok" \
 *     --edit-selector '[contenteditable="true"]' \
 *     [--frame-timeout 2000] [--quiescence-ms 500] \
 *     [--quiescence-timeout 10000] [--bulk-chars 1500]
 *
 * The payload is written to stdout as JSON. An unknown criterion id exits 2.
 * Without `--criteria` the file keeps its original paired warm/cold behaviour.
 *
 * ---------------------------------------------------------------------------
 * Payload schema (schema id: `perf.criteria_input/1`)
 * ---------------------------------------------------------------------------
 * {
 *   "probe": "criteria_input",
 *   "probe_version": 1,
 *   "schema": "perf.criteria_input/1",
 *   "driver": "playwright",
 *   "editor_id": "<label passed with --editor, else null>",
 *   "url": "<page url>",
 *   "corpus_route": "/corpus.docx",
 *   "viewport": {"width": 1280, "height": 900},
 *   "ready": {"selector": "...", "ready_ms": <driver-observed>, "ready_page_ms": <page clock>},
 *   "editable": {
 *     "selector": "<--edit-selector>",
 *     "box": {"left","top","right","bottom"},
 *     "is_content_editable": <bool>,
 *     "text_length": <int>,
 *     "dom_caret": <bool>,          // caret/selection readable through the DOM
 *     "click_point_source": "text_line_rects" | "box_fraction"
 *   },
 *   "paint_witness": {
 *     "mechanism": "cdp_screencast_frame",
 *     "frames_seen": <int>, "timeout_ms": <int>,
 *     "message": "<why it is unavailable>" | null
 *   },
 *   "criteria_requested": ["C04","C07","C09","C08"],
 *   "criteria": {"C04": <entry>, "C07": <entry>, "C09": <entry>, "C08": <entry>},
 *   "bulk_block": {"chars": 1500, "sha256_prefix": "<first 16 hex>"},
 *   "modifier": "Meta" | "Control",
 *   "started_at": "<ISO 8601>", "duration_ms": <int>
 * }
 *
 * <entry> (one per requested criterion):
 * {
 *   "criterion_id": "C07",
 *   "layer": "browser_visible",
 *   "boundary": "input_to_next_paint",
 *   "evidence": "presented_frame",
 *   "outcome": "measured" | "failed" | "unsupported" | "unverified",
 *   "samples_ms": [<number>, ...],       // empty unless outcome is "measured"
 *   "failure_reason": null | "<short reason>",
 *   "assertion": {"name","passed","scope","checks":{...},"failures":[...]},
 *   "trial_hints": {"cache_state","repetition_unit","run_kind","feature_profile"},
 *   "observations": [ {...one per sample or per attempted action...} ],
 *   "notes": ["..."]
 * }
 *
 * Rules the payload obeys (and `perf/tests/test_input_criteria.py` enforces on
 * the Python side):
 *   - A sample is the measured number for one action and is only emitted when
 *     that action's assertion held. An action whose assertion fails makes the
 *     whole criterion `failed` with `samples_ms: []` and a `failure_reason`:
 *     a group of samples with a broken member is not a distribution.
 *   - `samples_ms` is empty for every outcome other than `measured`.
 *   - Every non-measured entry carries a non-empty `failure_reason`.
 *   - The sample is input -> next compositor frame, both read on the page
 *     clock. The frame timestamp comes from CDP `Page.screencastFrame`
 *     (a real composited frame). A `requestAnimationFrame` callback is never
 *     the sample: it is recorded as `diagnostic_raf_ms` inside an observation
 *     and is not visible-paint evidence (`perf/layers/classify.py`).
 */
import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Buffer } from 'node:buffer';
import { createHash } from 'node:crypto';
import { normalizeDocumentText } from './document_text_normalize.mjs';

const REPO_ROOT = fileURLToPath(new URL('../..', import.meta.url));

export function validateWitnessRecord(record) {
  if (!record || typeof record !== 'object') {
    return {
      ok: false,
      refused: true,
      reason: 'record_not_a_mapping',
      errors: ['the witness record must be a JSON object'],
    };
  }
  let dir;
  try {
    dir = mkdtempSync(join(tmpdir(), 'perf-witness-'));
  } catch (err) {
    return {
      ok: false,
      refused: true,
      reason: 'witness_validator_failed',
      errors: [String(err && err.message ? err.message : err)],
    };
  }
  const file = join(dir, 'witness.json');
  try {
    writeFileSync(file, JSON.stringify(record));
    const witnessPy = join(REPO_ROOT, 'perf/runner/witness.py');
    const proc = spawnSync('python3', ['-I', witnessPy, '--file', file], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    if (proc.status !== 0 && proc.status !== 1) {
      return {
        ok: false,
        refused: true,
        reason: 'witness_validator_failed',
        errors: [(proc.stderr || proc.stdout || 'validator exit %s').trim()],
      };
    }
    return JSON.parse(proc.stdout);
  } catch (err) {
    return {
      ok: false,
      refused: true,
      reason: 'witness_validator_failed',
      errors: [String(err && err.message ? err.message : err)],
    };
  } finally {
    try {
      rmSync(dir, { recursive: true, force: true });
    } catch {
      // A cleanup error must not replace the validator's evidence or verdict.
    }
  }
}

import {
  frameInterval,
  getRecorder,
  stopRecorder,
  witnessFrame,
} from './witness.mjs';

export const CRITERIA_INPUT_VERSION = 1;
export const CRITERIA_SCHEMA = 'perf.criteria_input/1';

export const CRITERIA_META = Object.freeze({
  C04: Object.freeze({
    layer: 'model',
    boundary: 'deferred_quiescence',
    evidence: 'quiescence_or_timeout',
    cache_state: 'process_cold_fs_warm',
  }),
  C07: Object.freeze({
    layer: 'browser_visible',
    boundary: 'input_to_next_paint',
    evidence: 'presented_frame',
    cache_state: 'warm_steady',
  }),
  C08: Object.freeze({
    layer: 'browser_visible',
    boundary: 'input_to_next_paint',
    evidence: 'presented_frame',
    cache_state: 'warm_steady',
  }),
  C09: Object.freeze({
    layer: 'browser_visible',
    boundary: 'input_to_next_paint',
    evidence: 'presented_frame',
    cache_state: 'warm_steady',
  }),
});

/**
 * C04 runs first: it watches the document as it was left by the load, and any
 * click we send first would be its own deferred work. C09 runs before C08 so
 * the undo reverts one typed character and not a 1500-character insertion in
 * the same history group; the bulk edit is then the last mutation of the load.
 */
export const SUITE_ORDER = Object.freeze(['C04', 'C07', 'C09', 'C08']);

const BULK_SENTENCE = 'The quick brown fox jumps over the lazy dog and keeps running. ';

export function bulkBlock(chars) {
  const want = Math.max(1, Math.floor(chars));
  let text = '';
  while (text.length < want) text += BULK_SENTENCE;
  return text.slice(0, want);
}

export function parseCriteriaList(raw) {
  if (raw === true || raw === undefined || raw === null) return [];
  const parts = String(raw)
    .split(/[,\s]+/)
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
  const unknown = parts.filter((id) => !(id in CRITERIA_META));
  if (unknown.length) {
    throw new Error(
      `unknown criteria ${unknown.join(', ')}; known: ${Object.keys(CRITERIA_META).join(', ')}`,
    );
  }
  const wanted = new Set(parts);
  return SUITE_ORDER.filter((id) => wanted.has(id));
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const round = (value, digits = 3) => {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
};

const EVENT_TIMING_THRESHOLD_MS = 16;
const CORRECTNESS_PREFIX = 'correctness:';

function normalizeNewlines(text) {
  return String(text || '').replace(/\r\n/g, '\n');
}

/** Fixture w:t has no paragraph breaks; DOM range text may insert newlines only between blocks. */
function comparableDocumentText(text) {
  return normalizeNewlines(text).replace(/\n/g, '');
}

function rangeTextOfElement(el) {
  if (!el || typeof el.ownerDocument?.createRange !== 'function') {
    return '';
  }
  const range = el.ownerDocument.createRange();
  range.selectNodeContents(el);
  return range.toString();
}

function resolveDocumentTextRoot(el) {
  if (el && typeof el.matches === 'function' && el.matches('[data-paragraph-id][data-start]')) {
    const root = typeof el.closest === 'function' ? el.closest('.docx-page-content') : null;
    if (root) return root;
  }
  return el;
}

function loadExpectedBody(options) {
  const inline = options.expectedBodyText;
  if (typeof inline === 'string' && inline.length) return inline;
  const b64 = process.env.PERF_EXPECTED_BODY_B64;
  if (typeof b64 === 'string' && b64) {
    return Buffer.from(b64, 'base64').toString('utf8');
  }
  const path = process.env.PERF_EXPECTED_BODY_PATH || options.expectedBodyPath;
  if (typeof path === 'string' && path && fs.existsSync(path)) {
    return fs.readFileSync(path, 'utf8');
  }
  return null;
}

function loadExpectedOpening() {
  const raw = process.env.PERF_EXPECTED_OPENING_TEXT;
  if (typeof raw === 'string' && raw.trim()) {
    return raw;
  }
  return null;
}

function correctnessAdapter(options) {
  const raw = options.correctnessAdapter ?? process.env.PERF_CORRECTNESS_ADAPTER ?? 'dom_innerText';
  if (raw === false || raw === 'none' || raw === '') return null;
  return String(raw);
}

function adapterGate(adapter, isContentEditable) {
  if (!adapter) {
    return 'no_correctness_adapter: canvas surface without model API or pixel probe';
  }
  if (adapter === 'dom_innerText' || adapter.startsWith('dom_')) {
    if (!isContentEditable) {
      return 'correctness_adapter_unusable_on_surface: dom_innerText requires a contenteditable DOM';
    }
    return null;
  }
  return `correctness_adapter_not_implemented: ${adapter}`;
}

function bodyAfterInsertion(fixtureBody, insertText, offset) {
  const text = normalizeNewlines(fixtureBody);
  const at = Math.max(0, Math.min(offset === null || offset === undefined ? text.length : offset, text.length));
  return text.slice(0, at) + insertText + text.slice(at);
}

function assertFixtureBodyMatches(state, expectedBody) {
  if (expectedBody === null) return { ok: true };
  if (!state || state.error) {
    return { ok: false, reason: `${CORRECTNESS_PREFIX} ${state?.error || 'text_unreadable'}` };
  }
  if (comparableDocumentText(state.text) !== comparableDocumentText(expectedBody)) {
    return { ok: false, reason: `${CORRECTNESS_PREFIX} fixture_body_mismatch` };
  }
  return { ok: true };
}

function assertPreEditDocumentLoaded(state, options) {
  if (!state || state.error) {
    return { ok: false, reason: `${CORRECTNESS_PREFIX} ${state?.error || 'text_unreadable'}` };
  }
  if (options.expectedOpeningText) {
    const expected = normalizeDocumentText(options.expectedOpeningText);
    const actual = normalizeDocumentText(state.text);
    if (!expected || !actual || !actual.includes(expected)) {
      return { ok: false, reason: `${CORRECTNESS_PREFIX} document_opening_mismatch` };
    }
    return { ok: true };
  }
  return assertFixtureBodyMatches(state, options.expectedBodyText);
}

function assertBulkInsertBody(before, after, options) {
  const fixture = options.expectedBodyText;
  if (fixture !== null) {
    const beforeMatch = assertFixtureBodyMatches(before, fixture);
    if (!beforeMatch.ok) return beforeMatch;
  }
  const base = fixture ?? before.text;
  const offset = before.selection_offset ?? before.text.length;
  const expected = bodyAfterInsertion(base, options.block, offset);
  if (normalizeNewlines(after.text) !== normalizeNewlines(expected)) {
    return { ok: false, reason: `${CORRECTNESS_PREFIX} bulk_text_or_position` };
  }
  return { ok: true, expected };
}

function attachPaintWitnessFailure(observation, painted) {
  if (!painted || typeof painted !== 'object') {
    return;
  }
  if (painted.record) {
    observation.witness = painted.record;
    const verdict = painted.witness_verdict ?? validateWitnessRecord(painted.record);
    observation.witness_verdict = verdict;
    observation.witness_refusal = verdict.refused ? verdict.reason : null;
    observation.witness_errors = verdict.errors || [];
  }
  if (painted.witness_refusal) {
    observation.witness_refusal = painted.witness_refusal;
  }
  if (painted.witness_errors && painted.witness_errors.length) {
    observation.witness_errors = painted.witness_errors;
  }
  if (painted.frame_page_ms !== null && painted.frame_page_ms !== undefined) {
    observation.frame_ms = round(painted.frame_page_ms, 3);
  }
  if (painted.sampleMs !== null && painted.sampleMs !== undefined) {
    observation.sample_ms = painted.sampleMs;
  }
}

async function sampleAfterInput(witness, inputMs, options, callOptions = {}) {
  if (!witness || typeof witness.paintAfter !== 'function') {
    return { ok: false, reason: 'paint_witness_unavailable' };
  }
  const record = await witness.paintAfter(inputMs, callOptions);
  const verdict = validateWitnessRecord(record);
  const evidence = { record, witness_verdict: verdict,
    witness_refusal: verdict.refused ? verdict.reason : null,
    witness_errors: verdict.errors || [] };
  if (!record || record.outcome !== 'witnessed' || record.frame_page_ms === null) {
    return { ok: false, reason: 'no_painted_frame', ...evidence };
  }
  const inputRef =
    typeof inputMs === 'number' && Number.isFinite(inputMs)
      ? inputMs
      : typeof record.after_page_ms === 'number'
        ? record.after_page_ms
        : null;
  if (inputRef === null) {
    return { ok: false, reason: 'no_input_timestamp', ...evidence };
  }
  const sampleMs = round(record.frame_page_ms - inputRef, 3);
  if (verdict.refused || !verdict.ok) {
    return {
      ok: false,
      reason: `paint_witness_refused: ${verdict.reason || 'witness_refused'}`,
      ...evidence,
      sampleMs,
    };
  }
  const subFrame = sampleMs < witness.frameIntervalMs;
  if (subFrame) {
    return {
      ok: true,
      sampleMs,
      ...evidence,
      frame_page_ms: record.frame_page_ms,
      sub_frame: true,
    };
  }
  return {
    ok: true,
    sampleMs,
    record,
    frame_page_ms: record.frame_page_ms,
    ...evidence,
    sub_frame: false,
  };
}

// --------------------------------------------------------------------- frame witness

/**
 * A composited-frame witness built on CDP screencast. Chromium emits a frame
 * only when the compositor produces new pixels, so a click or key that changes
 * nothing yields no frame and therefore no sample.
 *
 * `frame.page_ms` is the frame timestamp moved onto the page clock:
 * `metadata.timestamp` is epoch seconds from the browser process, and
 * `performance.timeOrigin` is the same clock at navigation start, so
 * `timestamp * 1000 - timeOrigin` is comparable with `performance.now()`.
 */
export async function createFrameWitness(cdp, page, { timeoutMs = 2000 } = {}) {
  const timeOrigin = await page.evaluate(() => performance.timeOrigin);
  const frames = [];
  const ackErrors = [];
  let started = false;
  let startError = null;
  const onFrame = (event) => {
    frames.push({
      page_ms: event.metadata.timestamp * 1000 - timeOrigin,
      session_id: event.sessionId,
    });
    cdp.send('Page.screencastFrameAck', { sessionId: event.sessionId }).catch((err) => {
      if (ackErrors.length < 5) ackErrors.push(String(err));
    });
  };
  cdp.on('Page.screencastFrame', onFrame);
  try {
    await cdp.send('Page.startScreencast', {
      format: 'jpeg',
      quality: 30,
      maxWidth: 1280,
      maxHeight: 900,
      everyNthFrame: 1,
    });
    started = true;
  } catch (err) {
    startError = String(err);
  }
  return {
    timeoutMs,
    get frames() {
      return frames;
    },
    get started() {
      return started;
    },
    get startError() {
      return startError;
    },
    ackErrors,
    /** First composited frame strictly after `pageMs`, or null on timeout. */
    async nextAfter(pageMs, timeout = timeoutMs) {
      if (!started) return null;
      const deadline = Date.now() + timeout;
      while (Date.now() < deadline) {
        // Every frame already received, not only the ones that arrive from now
        // on: the input may have painted before this call was made.
        let best = null;
        for (const frame of frames) {
          if (frame.page_ms > pageMs && (best === null || frame.page_ms < best.page_ms)) {
            best = frame;
          }
        }
        if (best !== null) return best;
        await sleep(2);
      }
      return null;
    },
    stop() {
      cdp.off('Page.screencastFrame', onFrame);
      if (started) cdp.send('Page.stopScreencast').catch(() => {});
    },
  };
}

// --------------------------------------------------------------------- in-page probes

const INSTALL_INPUT_TAP = () => {
  window.__perfCriteria = { inputs: [], timeOrigin: performance.timeOrigin, target: null };
  const tap = window.__perfCriteria;
  const push = (kind, extra) => {
    if (tap.inputs.length < 200) {
      tap.inputs.push(Object.assign({ kind, t: performance.now() }, extra || {}));
    }
    return tap.inputs[tap.inputs.length - 1];
  };
  const opts = { capture: true, passive: true };
  document.addEventListener(
    'pointerdown',
    (event) => {
      // The event target is the hit-test result: an element inside the editable
      // surface means the click reached the editor and not a surrounding chrome.
      tap.target = event.target;
      const el = event.target;
      push('pointerdown', {
        x: event.clientX,
        y: event.clientY,
        target: el
          ? {
              tag: String(el.tagName || '').toLowerCase(),
              id: el.id || null,
              class: typeof el.className === 'string' ? el.className.slice(0, 120) : null,
            }
          : null,
      });
    },
    opts,
  );
  document.addEventListener('keydown', (event) => push('keydown', { key: event.key }), opts);
  document.addEventListener('paste', () => push('paste'), opts);
  document.addEventListener(
    'beforeinput',
    (event) => push('beforeinput', { inputType: event.inputType }),
    opts,
  );
  window.__perfInputPush = push;
};

const READ_EDITABLE_STATE = (selector) => {
  const el = document.querySelector(selector);
  if (!el) return { error: 'editable_not_found' };
  const box = el.getBoundingClientRect();
  const fragmentParagraph = typeof el.matches === 'function' && el.matches('[data-paragraph-id][data-start]');
  const paragraphNodes = fragmentParagraph
    ? Array.from(document.querySelectorAll('.docx-page-content [data-paragraph-id][data-start]'))
    : [];
  const rangeText = (node) => {
    const range = document.createRange();
    range.selectNodeContents(node);
    return range.toString();
  };
  let textRoot = el;
  if (fragmentParagraph) {
    const pageContent = typeof el.closest === 'function' ? el.closest('.docx-page-content') : null;
    if (pageContent) textRoot = pageContent;
  }
  const text =
    paragraphNodes.length > 0
      ? paragraphNodes.map((node) => rangeText(node)).join('')
      : rangeText(textRoot);
  const selection = window.getSelection();
  let caret = null;
  let anchorInside = false;
  let selectionOffset = null;
  if (selection && selection.rangeCount > 0) {
    const range = selection.getRangeAt(0);
    const startNode = range.startContainer;
    const startElement = startNode && startNode.nodeType === 3 ? startNode.parentNode : startNode;
    anchorInside = Boolean(startElement && el.contains(startElement));
    const rect = range.getBoundingClientRect();
    caret = {
      top: rect.top,
      bottom: rect.bottom,
      left: rect.left,
      right: rect.right,
      height: rect.height,
      collapsed: range.collapsed,
    };
    if (paragraphNodes.length > 0) {
      let offset = 0;
      for (const paragraph of paragraphNodes) {
        if (paragraph.contains(startElement) || paragraph === startElement) {
          const pre = range.cloneRange();
          pre.selectNodeContents(paragraph);
          pre.setEnd(range.startContainer, range.startOffset);
          selectionOffset = offset + pre.toString().length;
          break;
        }
        offset += rangeText(paragraph).length;
      }
    } else {
      const pre = range.cloneRange();
      pre.selectNodeContents(textRoot);
      pre.setEnd(range.startContainer, range.startOffset);
      selectionOffset = pre.toString().length;
    }
  }
  const active = document.activeElement;
  return {
    text,
    text_length: text.length,
    is_content_editable: el.isContentEditable === true,
    active_inside: Boolean(active && (active === el || el.contains(active))),
    active_tag: active ? String(active.tagName || '').toLowerCase() : null,
    anchor_inside: anchorInside,
    selection_offset: selectionOffset,
    caret,
    box: { left: box.left, top: box.top, right: box.right, bottom: box.bottom },
    scroll: { x: window.scrollX, y: window.scrollY },
  };
};

const RESOLVE_CLICK_POINTS = (selector) => {
  // Page context: no Node helpers here.
  const round = (value, digits = 1) => {
    const factor = 10 ** digits;
    return Math.round(value * factor) / factor;
  };
  const el = document.querySelector(selector);
  if (!el) return { error: 'editable_not_found' };
  let box = el.getBoundingClientRect();
  const viewport = { width: window.innerWidth, height: window.innerHeight };
  const onScreen = (r) =>
    Math.min(r.bottom, viewport.height) - Math.max(r.top, 0) >= 8 &&
    Math.min(r.right, viewport.width) - Math.max(r.left, 0) >= 8;
  if (!onScreen(box)) {
    // A long paged document can put the first matched paragraph below the fold;
    // scroll it in before resolving points, otherwise the hit-test would refuse
    // a surface that is perfectly clickable one scroll away.
    el.scrollIntoView({ block: 'center', inline: 'nearest' });
    box = el.getBoundingClientRect();
  }
  const clip = {
    left: Math.max(box.left, 0),
    top: Math.max(box.top, 0),
    right: Math.min(box.right, viewport.width),
    bottom: Math.min(box.bottom, viewport.height),
  };
  if (clip.right - clip.left < 8 || clip.bottom - clip.top < 8) {
    return { error: 'editable_not_in_viewport', box, viewport };
  }
  const rects = [];
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
  let node = null;
  let guard = 0;
  while ((node = walker.nextNode()) !== null && guard < 4000 && rects.length < 2000) {
    guard += 1;
    const value = node.nodeValue || '';
    if (!value.trim()) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const rect of range.getClientRects()) {
      if (rect.width > 1 && rect.height > 1) {
        rects.push({
          left: rect.left,
          top: rect.top,
          right: rect.right,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
        });
      }
      if (rects.length >= 2000) break;
    }
  }
  const visible = rects.filter(
    (r) =>
      r.bottom > clip.top + 2 &&
      r.top < clip.bottom - 2 &&
      r.right > clip.left + 2 &&
      r.left < clip.right - 2,
  );
  const clampX = (x) => Math.min(Math.max(x, clip.left + 2), clip.right - 2);
  const clampY = (y) => Math.min(Math.max(y, clip.top + 2), clip.bottom - 2);
  const points = [];
  let source = 'box_fraction';
  let lineHeights = [];
  if (visible.length > 0) {
    source = 'text_line_rects';
    let first = visible[0];
    let last = visible[0];
    for (const rect of visible) {
      if (rect.top < first.top) first = rect;
      if (rect.bottom > last.bottom) last = rect;
    }
    lineHeights = visible.map((r) => r.height).sort((a, b) => a - b);
    points.push({
      point: 'page_centre',
      x: round(clampX((clip.left + clip.right) / 2), 1),
      y: round(clampY((clip.top + clip.bottom) / 2), 1),
      line: null,
    });
    points.push({
      point: 'first_text_line',
      x: round(clampX(first.left + 0.35 * (first.right - first.left)), 1),
      y: round(clampY((first.top + first.bottom) / 2), 1),
      line: { top: round(first.top, 1), bottom: round(first.bottom, 1) },
    });
    points.push({
      point: 'last_text_line',
      x: round(clampX(last.left + 0.65 * (last.right - last.left)), 1),
      y: round(clampY((last.top + last.bottom) / 2), 1),
      line: { top: round(last.top, 1), bottom: round(last.bottom, 1) },
    });
  } else {
    const height = clip.bottom - clip.top;
    for (const [point, fraction] of [
      ['page_centre', 0.5],
      ['first_text_line', 0.2],
      ['last_text_line', 0.8],
    ]) {
      points.push({
        point,
        x: round(clampX((clip.left + clip.right) / 2), 1),
        y: round(clampY(clip.top + fraction * height), 1),
        line: null,
      });
    }
  }
  const medianHeight = lineHeights.length
    ? lineHeights[Math.floor(lineHeights.length / 2)]
    : null;
  return {
    points,
    source,
    clip: {
      left: round(clip.left, 1),
      top: round(clip.top, 1),
      right: round(clip.right, 1),
      bottom: round(clip.bottom, 1),
    },
    box: { left: round(box.left, 1), top: round(box.top, 1), right: round(box.right, 1), bottom: round(box.bottom, 1) },
    viewport,
    line_height_px: medianHeight === null ? null : round(medianHeight, 1),
    text_rects: visible.length,
  };
};

/**
 * Quiescence watch (C04). Activity is a DOM mutation, a long task, or a main
 * thread gap wider than 200 ms between animation frames; anything else (an
 * animation-frame callback with no work behind it) is not deferred work.
 */
const OBSERVE_QUIESCENCE = async ({ quietMs, timeoutMs }) => {
  // Page context: no Node helpers here.
  const round = (value, digits = 3) => {
    const factor = 10 ** digits;
    return Math.round(value * factor) / factor;
  };
  const startedAt = performance.now();
  const activities = [];
  let lastActivity = startedAt;
  const note = (kind, detail) => {
    const t = performance.now();
    lastActivity = t;
    if (activities.length < 400) activities.push({ kind, t, detail: detail || null });
  };
  const observer = new MutationObserver((records) => note('mutation', { count: records.length }));
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    characterData: true,
  });
  let longTasks = 0;
  let longTaskObserver = null;
  try {
    longTaskObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        longTasks += 1;
        note('longtask', { duration: entry.duration });
      }
    });
    longTaskObserver.observe({ type: 'longtask', buffered: true });
  } catch (err) {
    longTaskObserver = null;
  }
  let rafCount = 0;
  let lastRaf = performance.now();
  let maxRafGap = 0;
  let running = true;
  const tick = () => {
    const t = performance.now();
    const gap = t - lastRaf;
    if (gap > maxRafGap) maxRafGap = gap;
    if (gap > 200) note('main_thread_gap', { gap });
    lastRaf = t;
    rafCount += 1;
    if (running) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  const deadline = startedAt + timeoutMs;
  let quietAt = null;
  let quiescenceConfirmedMs = null;
  while (performance.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 50));
    if (performance.now() - lastActivity >= quietMs) {
      quietAt = lastActivity;
      quiescenceConfirmedMs = performance.now();
      break;
    }
  }
  running = false;
  observer.disconnect();
  if (longTaskObserver) longTaskObserver.disconnect();
  const endedAt = performance.now();
  const deferredKinds = new Set(['mutation', 'longtask', 'main_thread_gap']);
  const deferred_work_seen = activities.some((a) => deferredKinds.has(a.kind)) || longTasks > 0;
  return {
    quiescent: quietAt !== null,
    quiet_at: quietAt,
    quiet_window_ms: quietMs,
    quiescence_confirmed_ms: quiescenceConfirmedMs === null ? null : round(quiescenceConfirmedMs, 3),
    quiescence_event: quietAt === null ? null : 'last_activity_before_quiet_window',
    observed_for_ms: round(endedAt - startedAt, 3),
    activity_count: activities.length,
    long_tasks: longTasks,
    raf_count: rafCount,
    max_raf_gap_ms: round(maxRafGap, 3),
    deferred_work_seen,
    activities: activities.slice(-25).map((a) => ({ kind: a.kind, t: round(a.t, 3), detail: a.detail })),
  };
};

// --------------------------------------------------------------------- helpers

function emptyEntry(criterionId, outcome, failureReason, extra) {
  const meta = CRITERIA_META[criterionId];
  return Object.assign(
    {
      criterion_id: criterionId,
      layer: meta.layer,
      boundary: meta.boundary,
      evidence: meta.evidence,
      outcome,
      samples_ms: [],
      failure_reason: failureReason || null,
      assertion: { name: null, passed: false, scope: null, checks: {}, failures: [] },
      trial_hints: {
        cache_state: meta.cache_state,
        repetition_unit: 'fresh_process',
        run_kind: 'timing',
        feature_profile: 'P0',
      },
      observations: [],
      notes: [],
    },
    extra || {},
  );
}

async function readState(page, selector) {
  return page.evaluate(READ_EDITABLE_STATE, selector);
}

async function clearInputs(page) {
  await page.evaluate(() => {
    if (window.__perfCriteria) window.__perfCriteria.inputs.length = 0;
  });
}

/**
 * First tapped input matching a plain descriptor (no `eval`, so a CSP on the
 * host page cannot break the probe). Descriptors:
 *   {kind: "pointerdown"} | {kind: "keydown", key: "x"} |
 *   {kinds: ["paste"], inputTypePrefix: "insertFromPaste"}
 */
async function firstInput(page, spec) {
  return page.evaluate((query) => {
    const inputs = window.__perfCriteria ? window.__perfCriteria.inputs : [];
    const kinds = query.kinds || [query.kind];
    for (const entry of inputs) {
      if (!kinds.includes(entry.kind)) continue;
      if (query.key !== undefined && entry.key !== query.key) continue;
      if (
        query.inputTypePrefix !== undefined &&
        !String(entry.inputType || '').startsWith(query.inputTypePrefix)
      ) {
        continue;
      }
      return entry;
    }
    return null;
  }, spec);
}

async function pointerTargetInside(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    const target = window.__perfCriteria ? window.__perfCriteria.target : null;
    if (!el) return { inside: null, reason: 'editable_not_found' };
    if (!target) return { inside: null, reason: 'no_pointer_target' };
    return { inside: el === target || el.contains(target), reason: null };
  }, selector);
}

/** Two animation frames plus a short idle so the next action starts on a quiet page. */
async function settle(page, idleMs = 120) {
  await page.evaluate(
    () =>
      new Promise((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve(null)));
      }),
  );
  await sleep(idleMs);
}

async function rafDelta(page, sincePageMs) {
  return page.evaluate(async (since) => {
    await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
    await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
    return performance.now() - since;
  }, sincePageMs);
}

// --------------------------------------------------------------------- criteria

async function measureQuiescence(page, options, readyPageMs) {
  const result = await page.evaluate(OBSERVE_QUIESCENCE, {
    quietMs: options.quiescenceMs,
    timeoutMs: options.quiescenceTimeoutMs,
  });
  const entry = emptyEntry('C04', 'unverified', null);
  entry.observations.push({
    ready_page_ms: round(readyPageMs, 3),
    quiescent: result.quiescent,
    quiet_at_page_ms: result.quiet_at === null ? null : round(result.quiet_at, 3),
    quiet_window_ms: result.quiet_window_ms,
    quiescence_confirmed_page_ms:
      result.quiescence_confirmed_ms === null ? null : round(result.quiescence_confirmed_ms, 3),
    elapsed_from_ready_ms: result.quiescent ? round(result.quiet_at - readyPageMs, 3) : null,
    observed_for_ms: result.observed_for_ms,
    activity_count: result.activity_count,
    long_tasks: result.long_tasks,
    max_raf_gap_ms: result.max_raf_gap_ms,
    activities: result.activities,
  });
  entry.assertion = {
    name: 'deferred_work_settles',
    passed: result.quiescent,
    scope: `no_mutation_no_long_task_and_no_main_thread_gap_over_200ms_for_${options.quiescenceMs}ms`,
    checks: {
      quiescent: result.quiescent,
      within_timeout: result.quiescent,
    },
    failures: result.quiescent ? [] : ['quiescence_not_reached'],
  };
  if (!result.quiescent) {
    entry.outcome = 'unverified';
    entry.failure_reason = `quiescence_not_reached_within_${options.quiescenceTimeoutMs}ms`;
    entry.notes.push(
      'The page kept mutating or blocking the main thread for the whole window; no quiescence timestamp exists, so no sample is recorded.',
    );
    return entry;
  }
  if (!result.deferred_work_seen) {
    entry.outcome = 'not_applicable';
    entry.failure_reason = 'no_deferred_work';
    entry.assertion.passed = false;
    entry.assertion.failures = ['no_deferred_work'];
    entry.notes.push(
      'No deferred work was observed after ready; C04 does not apply and no latency is recorded.',
    );
    return entry;
  }
  entry.outcome = 'measured';
  const sample = round(result.quiet_at - readyPageMs, 3);
  entry.observations[0].elapsed_from_ready_ms = sample;
  entry.observations[0].quiescence_event = result.quiescence_event;
  entry.samples_ms = [sample];
  entry.assertion.passed = true;
  entry.notes.push(
    'One sample per page load: elapsed time ends at the last deferred-work activity before the quiet window; quiescence_confirmed_page_ms is when the window was satisfied.',
  );
  return entry;
}

async function resolveClickPoint(page, meta) {
  // A host whose edit surface is a single non-block element (a bare span or
  // canvas) can resolve zero click points. Falling back to the editable's own
  // box keeps C07/C08/C09 measurable there instead of throwing a TypeError;
  // if even the box is unavailable the caller records a refusal.
  const points = meta.points || [];
  const preferred = points.find((p) => p.point === 'last_text_line') || points[0];
  if (preferred && Number.isFinite(preferred.x) && Number.isFinite(preferred.y)) {
    return preferred;
  }
  const selector = meta.editable && meta.editable.selector;
  if (!selector) return null;
  const box = await page.locator(selector).first().boundingBox().catch(() => null);
  if (!box || !(box.width > 0) || !(box.height > 0)) return null;
  return {
    point: 'editable_box_centre',
    x: box.x + box.width / 2,
    y: box.y + box.height / 2,
    line: null,
  };
}

async function measureClicks(page, witness, options, meta) {
  const entry = emptyEntry('C07', 'failed', null);
  entry.trial_hints.repetition_unit = 'fresh_process';
  const scope = 'dom_caret_on_clicked_line';
  entry.assertion = {
    name: 'hit_test_reaches_editable_and_paints',
    passed: false,
    scope,
    checks: {},
    failures: [],
  };
  if (!meta.editable.is_content_editable) {
    entry.outcome = 'unsupported';
    entry.failure_reason =
      'correctness_adapter_unusable_on_surface: dom_innerText requires a contenteditable DOM';
    entry.assertion.scope = 'not_observable';
    entry.assertion.failures.push(entry.failure_reason);
    return entry;
  }
  const points = meta.points;
  const samples = [];
  const subFrameSamples = [];
  for (const point of points) {
    const observation = {
      observation_id: `click-${entry.observations.length}`,
      point: point.point,
      x: point.x,
      y: point.y,
      line: point.line,
      scope,
    };
    await clearInputs(page);
    let input = null;
    const frameRecord = await witness.paintAfter(null, {
      arm: async () => {
        await page.mouse.click(point.x, point.y);
        const tapped = await firstInput(page, { kind: 'pointerdown' });
        if (tapped === null) return null;
        input = tapped;
        return tapped.t;
      },
    });
    attachPaintWitnessFailure(observation, { record: frameRecord });
    if (input === null) {
      observation.failure = 'no_pointerdown_observed';
      entry.assertion.failures.push(`${point.point}: no_pointerdown_observed`);
      entry.observations.push(observation);
      continue;
    }
    observation.input_ms = round(input.t, 3);
    observation.pointer_target = input.target || null;
    const target = await pointerTargetInside(page, meta.editable.selector);
    observation.pointer_target_inside_editable = target.inside;
    await settle(page, 30);
    const stateAfterClick = await readState(page, meta.editable.selector);
    const correctnessEarly = assertPreEditDocumentLoaded(stateAfterClick, options);
    if (!correctnessEarly.ok) {
      observation.failure = correctnessEarly.reason;
      entry.assertion.failures.push(`${point.point}: ${correctnessEarly.reason}`);
      entry.observations.push(observation);
      continue;
    }
    observation.witness = frameRecord;
    observation.diagnostic_raf_ms = round(await rafDelta(page, input.t), 3);
    const state = await readState(page, meta.editable.selector);
    observation.active_tag = state.active_tag || null;
    observation.active_inside = state.active_inside === true;
    observation.anchor_inside = state.anchor_inside === true;
    observation.caret = state.caret
      ? {
          top: round(state.caret.top, 1),
          bottom: round(state.caret.bottom, 1),
          height: round(state.caret.height, 1),
        }
      : null;
    if (!frameRecord || frameRecord.outcome !== 'witnessed' || frameRecord.frame_page_ms === null) {
      observation.failure =
        frameRecord?.outcome === 'no_frame'
          ? `no_painted_frame_within_${options.frameTimeoutMs}ms`
          : 'paint_witness_refused';
      entry.assertion.failures.push(`${point.point}: no_painted_frame`);
      entry.observations.push(observation);
      continue;
    }
    const witnessVerdict = validateWitnessRecord(frameRecord);
    if (witnessVerdict.refused || !witnessVerdict.ok) {
      observation.failure = `paint_witness_refused: ${witnessVerdict.reason || 'witness_refused'}`;
      observation.witness_refusal = witnessVerdict.reason;
      observation.witness_errors = witnessVerdict.errors || [];
      entry.assertion.failures.push(`${point.point}: paint_witness_refused`);
      entry.observations.push(observation);
      continue;
    }
    observation.frame_ms = round(frameRecord.frame_page_ms, 3);
    const sampleMs = round(frameRecord.frame_page_ms - input.t, 3);
    const subFrame = sampleMs < witness.frameIntervalMs;
    observation.sample_ms = sampleMs;
    observation.sub_frame = subFrame;
    const correctness = assertPreEditDocumentLoaded(state, options);
    if (!correctness.ok) {
      observation.failure = correctness.reason;
      entry.assertion.failures.push(`${point.point}: ${correctness.reason}`);
      entry.observations.push(observation);
      continue;
    }
    // A point on a text line must place the caret on that line. The page
    // centre has no line box: it only has to keep the caret in the editable.
    const caretOnLine =
      point.line === null
        ? true
        : Boolean(
            state.caret &&
              state.caret.top >= point.line.top - 2 &&
              state.caret.top <= point.line.bottom + 2,
          );
    observation.caret_on_clicked_line = caretOnLine;
    if (!state.anchor_inside || !caretOnLine) {
      observation.failure = state.anchor_inside
        ? 'caret_not_on_clicked_line'
        : 'caret_not_inside_editable';
      entry.assertion.failures.push(`${point.point}: ${observation.failure}`);
      entry.observations.push(observation);
      continue;
    }
    if (target.inside === false) {
      observation.failure = 'pointer_target_outside_editable';
      entry.assertion.failures.push(`${point.point}: pointer_target_outside_editable`);
      entry.observations.push(observation);
      continue;
    }
    samples.push(sampleMs);
    subFrameSamples.push(subFrame);
    entry.observations.push(observation);
    await settle(page);
  }
  entry.assertion.checks = {
    points_attempted: points.length,
    points_painted: samples.length,
    pointer_target_inside_editable: entry.observations.every(
      (o) => o.pointer_target_inside_editable !== false,
    ),
    caret_scope: scope,
  };
  if (entry.assertion.failures.length === 0 && samples.length === points.length) {
    entry.outcome = 'measured';
    entry.samples_ms = samples;
    entry.sample_observation_ids = entry.observations.map((o) => o.observation_id);
    entry.sub_frame_samples = subFrameSamples;
    entry.assertion.passed = true;
    entry.assertion.checks = {
      all_points_painted: true,
      all_points_hit_editable: true,
      caret_assertion: scope,
    };
    entry.failure_reason = null;
  } else {
    entry.outcome = 'failed';
    entry.samples_ms = [];
    const correctnessFailure = entry.assertion.failures.find((f) => f.includes(CORRECTNESS_PREFIX));
    entry.failure_reason =
      correctnessFailure?.split(': ').slice(1).join(': ') ||
      (entry.assertion.failures.length > 0
        ? entry.assertion.failures[0]
        : `only_${samples.length}_of_${points.length}_clicks_measured`);
    if (correctnessFailure) {
      entry.failure_reason = correctnessFailure.slice(correctnessFailure.indexOf(CORRECTNESS_PREFIX));
    }
  }
  entry.notes.push(
    'Three deterministic points resolved from the visible text line boxes (page centre, first visible line, last visible line). No scrolling: a point outside the viewport is not used.',
  );
  return entry;
}

async function measureUndo(page, witness, options, meta) {
  const entry = emptyEntry('C09', 'unsupported', null);
  const state = meta.editable;
  if (!state.is_content_editable) {
    entry.failure_reason =
      'surface_not_dom_editable: no document text or caret in the DOM, so "the character was typed and the undo reverted it" cannot be asserted';
    entry.assertion = {
      name: 'typing_then_undo_restores_document_text',
      passed: false,
      scope: 'not_observable',
      checks: {},
      failures: ['text_not_observable'],
    };
    return entry;
  }
  if (!state.text_length) {
    entry.failure_reason = 'editable_has_no_observable_text';
    entry.assertion = {
      name: 'typing_then_undo_restores_document_text',
      passed: false,
      scope: 'not_observable',
      checks: {},
      failures: ['empty_text'],
    };
    return entry;
  }
  entry.outcome = 'failed';
  entry.assertion = {
    name: 'typing_then_undo_restores_document_text',
    passed: false,
    scope: 'dom_text_exact_match',
    checks: {},
    failures: [],
  };
  const point = await resolveClickPoint(page, meta);
  if (!point) {
    entry.failure_reason = 'no_click_point_resolved';
    entry.assertion.failures.push('no_click_point_resolved');
    return entry;
  }
  await page.mouse.click(point.x, point.y);
  await settle(page);
  const before = await readState(page, meta.editable.selector);
  if (before.error) {
    entry.failure_reason = before.error;
    return entry;
  }
  let undoAttempted = false;
  try {
    await clearInputs(page);
    await page.keyboard.type('x');
    const typedInput = await firstInput(page, { kind: 'keydown', key: 'x' });
    if (typedInput === null) {
      entry.failure_reason = 'no_keydown_observed_for_typed_character';
      entry.assertion.failures.push('no_keydown_observed_for_typed_character');
      return entry;
    }
    let typedState = await readState(page, meta.editable.selector);
    let typedFrames = 0;
    while (typedState.text_length !== before.text_length + 1 && typedFrames < 6) {
      await sleep(16);
      typedFrames += 1;
      typedState = await readState(page, meta.editable.selector);
    }
    if (typedState.text_length !== before.text_length + 1) {
      entry.failure_reason = 'typed_character_not_observable_in_document_text';
      entry.observations.push({
        point: point.point,
        x: point.x,
        y: point.y,
        text_length_before: before.text_length,
        text_length_after_typing: typedState.text_length,
        frames_waited: typedFrames,
      });
      entry.assertion.failures.push('typed_character_not_observable_in_document_text');
      return entry;
    }
    const insertOffset = before.selection_offset ?? before.text.length;
    const expectedTyped = bodyAfterInsertion(before.text, 'x', insertOffset);
    if (typedState.text !== expectedTyped) {
      entry.failure_reason = `${CORRECTNESS_PREFIX} typed_character_or_position`;
      entry.assertion.failures.push(entry.failure_reason);
      return entry;
    }
    await settle(page, 60);
    let undoInput = null;
    const observation = {
      observation_id: "undo",
      point: point.point,
      x: point.x,
      y: point.y,
      input_ms: null,
      text_length_before_typing: before.text_length,
      text_length_after_typing: typedState.text_length,
      frames_waited_for_typed_character: typedFrames,
      modifier: options.modifier,
    };
    const painted = await sampleAfterInput(witness, null, options, {
      arm: async () => {
        await clearInputs(page);
        undoAttempted = true;
        await page.keyboard.press(`${options.modifier}+Z`);
        undoInput =
          (await firstInput(page, { kinds: ['keydown'], key: 'z' })) ||
          (await firstInput(page, { kinds: ['keydown'], key: 'Z' }));
        return undoInput?.t ?? null;
      },
    });
    attachPaintWitnessFailure(observation, painted);
    if (undoInput === null) {
      entry.observations.push(observation);
      entry.failure_reason = 'no_keydown_observed_for_undo';
      entry.assertion.failures.push('no_keydown_observed_for_undo');
      return entry;
    }
    observation.input_ms = round(undoInput.t, 3);
    if (!painted.ok) {
      observation.failure = painted.reason;
      attachPaintWitnessFailure(observation, painted);
      entry.observations.push(observation);
      entry.failure_reason = painted.reason;
      entry.assertion.failures.push('undo_not_painted');
      return entry;
    }
    let after = await readState(page, meta.editable.selector);
    let framesToRevert = 1;
    while (after.text !== before.text && framesToRevert < 6) {
      await sleep(16);
      framesToRevert += 1;
      after = await readState(page, meta.editable.selector);
    }
    observation.frame_ms = round(painted.frame_page_ms, 3);
    observation.sample_ms = painted.sampleMs;
    observation.witness = painted.record;
    observation.painted_frames_to_revert = framesToRevert;
    observation.text_length_after_undo = after.text_length;
    observation.text_restored = after.text === before.text;
    observation.diagnostic_raf_ms = round(await rafDelta(page, undoInput.t), 3);
    entry.observations.push(observation);
    const undoExpected = options.expectedOpeningText ? before.text : (options.expectedBodyText ?? before.text);
    const restored = assertFixtureBodyMatches(after, undoExpected);
    if (!restored.ok) {
      entry.failure_reason = restored.reason;
      entry.assertion.failures.push(restored.reason);
      return entry;
    }
    if (!observation.text_restored) {
      entry.failure_reason = `${CORRECTNESS_PREFIX} undo_did_not_restore_document_text`;
      entry.assertion.failures.push(entry.failure_reason);
      entry.notes.push(
        'The typed character was visible before the undo, so the undo keystroke did not revert it within three painted frames.',
      );
      return entry;
    }
    entry.outcome = 'measured';
    entry.samples_ms = [observation.sample_ms];
    entry.sample_observation_ids = [observation.observation_id];
    entry.sub_frame_samples = [Boolean(painted.sub_frame)];
    entry.assertion.passed = true;
    entry.assertion.checks = {
      typed_character_observed: true,
      undo_restored_exact_text: true,
      painted_frames_to_revert: framesToRevert,
    };
    entry.failure_reason = null;
    return entry;
  } finally {
    try {
      let current = await readState(page, meta.editable.selector);
      if (current.text !== before.text && !undoAttempted) {
        undoAttempted = true;
        await page.keyboard.press(`${options.modifier}+Z`);
        await settle(page, 60);
        current = await readState(page, meta.editable.selector);
      }
      if (current.text !== before.text) {
        entry.fixture_reset = { attempted: true, restored: false, reason: 'undo_did_not_restore_original' };
        try {
          await page.reload();
          const waitForBody = options.fixtureWaitForRestore !== false;
          if (waitForBody) {
            // Reload can finish before the editor imports its fixture. Wait for that body.
            for (let attempt = 0; attempt < 100; attempt += 1) {
              current = await readState(page, meta.editable.selector);
              if (current.text === before.text) break;
              await sleep(50);
            }
          } else {
            current = await readState(page, meta.editable.selector);
          }
          entry.fixture_reset.restored = current.text === before.text;
          await page.evaluate(INSTALL_INPUT_TAP);
        } catch (error) {
          entry.fixture_reset.error = String(error);
        }
      }
    } catch (error) {
      if (entry.fixture_reset) {
        if (!entry.fixture_reset.error) {
          entry.fixture_reset.error = String(error);
        }
      } else {
        entry.fixture_reset = { attempted: true, restored: false, error: String(error) };
      }
    }
  }
}

async function measureBulkInsert(page, witness, options, meta) {
  const entry = emptyEntry('C08', 'unsupported', null);
  const state = meta.editable;
  if (!state.is_content_editable) {
    entry.failure_reason =
      'surface_not_dom_editable: no document text in the DOM, so "the inserted text made the document longer" cannot be asserted';
    entry.assertion = {
      name: 'bulk_insert_grows_document_text',
      passed: false,
      scope: 'not_observable',
      checks: {},
      failures: ['text_not_observable'],
    };
    return entry;
  }
  if (!state.text_length) {
    entry.failure_reason = 'editable_has_no_observable_text';
    entry.assertion = {
      name: 'bulk_insert_grows_document_text',
      passed: false,
      scope: 'not_observable',
      checks: {},
      failures: ['empty_text'],
    };
    return entry;
  }
  entry.outcome = 'failed';
  entry.assertion = {
    name: 'bulk_insert_grows_document_text',
    passed: false,
    scope: 'dom_text_length_growth',
    checks: {},
    failures: [],
  };
  const point = await resolveClickPoint(page, meta);
  if (!point) {
    entry.failure_reason = 'no_click_point_resolved';
    entry.assertion.failures.push('no_click_point_resolved');
    return entry;
  }
  await page.mouse.click(point.x, point.y);
  await settle(page, 200);
  const before = await readState(page, meta.editable.selector);
  if (before.error) {
    entry.failure_reason = before.error;
    return entry;
  }
  const minimumGrowth = options.bulkChars;
  const observation = {
    observation_id: "paste",
    point: point.point,
    x: point.x,
    y: point.y,
    block_chars: options.bulkChars,
    minimum_growth: minimumGrowth,
    text_length_before: before.text_length,
  };

  // Clipboard path: write the block, then a real paste keystroke.
  let pasteError = null;
  try {
    await page.evaluate(async (text) => {
      await navigator.clipboard.writeText(text);
    }, options.block);
  } catch (err) {
    pasteError = String(err && err.message ? err.message : err);
  }
  if (pasteError === null) {
    let pasteInput = null;
    const painted = await sampleAfterInput(witness, null, options, {
      arm: async () => {
        await clearInputs(page);
        await page.keyboard.press(`${options.modifier}+V`);
        pasteInput = await firstInput(page, {
          kinds: ['paste', 'beforeinput'],
          inputTypePrefix: undefined,
        });
        return pasteInput?.t ?? null;
      },
    });
    observation.method = 'clipboard_paste_keyboard';
    attachPaintWitnessFailure(observation, painted);
    if (pasteInput !== null) {
      if (painted.ok) {
        const afterPaste = await readState(page, meta.editable.selector);
        const growth = afterPaste.text_length - before.text_length;
        observation.method = 'clipboard_paste_keyboard';
        observation.input_ms = round(pasteInput.t, 3);
        observation.frame_ms = round(painted.frame_page_ms, 3);
        observation.sample_ms = painted.sampleMs;
        observation.witness = painted.record;
        observation.text_length_after = afterPaste.text_length;
        observation.growth = growth;
        observation.diagnostic_raf_ms = round(await rafDelta(page, pasteInput.t), 3);
        if (growth >= minimumGrowth) {
          const bodyCheck = assertBulkInsertBody(before, afterPaste, options);
          if (!bodyCheck.ok) {
            entry.failure_reason = bodyCheck.reason;
            entry.observations.push({ ...observation, failure: entry.failure_reason });
            entry.assertion.failures.push(entry.failure_reason);
            return entry;
          }
          entry.observations.push(observation);
          entry.outcome = 'measured';
          entry.samples_ms = [observation.sample_ms];
          entry.sample_observation_ids = [observation.observation_id];
          entry.sub_frame_samples = [Boolean(painted.sub_frame)];
          entry.assertion.passed = true;
          entry.assertion.checks = {
            text_length_grew: true,
            growth: growth,
            expected_block_chars: options.bulkChars,
          };
          entry.failure_reason = null;
          entry.notes.push(
            'Caret placed on the last visible text line; the block is inserted there, so the document grows instead of being replaced (select-all would make a growth assertion impossible).',
          );
          return entry;
        }
        observation.failure = `${CORRECTNESS_PREFIX} truncated_paste`;
        entry.observations.push(observation);
        entry.failure_reason = observation.failure;
        entry.assertion.failures.push(observation.failure);
        return entry;
      } else {
        const afterPaste = await readState(page, meta.editable.selector);
        const growth = afterPaste.text_length - before.text_length;
        if (growth > 0 && growth < minimumGrowth) {
          entry.failure_reason = `${CORRECTNESS_PREFIX} truncated_paste`;
          entry.observations.push({
            ...observation,
            growth,
            failure: entry.failure_reason,
          });
          entry.assertion.failures.push(entry.failure_reason);
          return entry;
        }
        observation.method = 'clipboard_paste_keyboard';
        observation.input_ms = round(pasteInput.t, 3);
        observation.failure = painted.reason;
        attachPaintWitnessFailure(observation, painted);
        entry.observations.push(observation);
        pasteError = painted.reason;
      }
    } else {
      observation.failure = 'paste_keystroke_did_not_reach_the_page';
      entry.observations.push(observation);
      pasteError = observation.failure;
    }
  } else {
    observation.clipboard_error = pasteError;
  }

  // Fallback explicitly allowed by the design: a DOM insertText when the
  // clipboard path is blocked in headless Chromium. It is recorded as its own
  // method, never merged with a paste sample.
  await page.mouse.click(point.x, point.y);
  await settle(page, 150);
  const pre = await readState(page, meta.editable.selector);
  let stamp = null;
  const painted = await sampleAfterInput(witness, null, options, {
    arm: async () => {
      stamp = await page.evaluate((text) => {
        const start = performance.now();
        if (window.__perfInputPush) window.__perfInputPush('exec_command_insert_text', { start });
        let ok = false;
        let error = null;
        try {
          ok = document.execCommand('insertText', false, text);
        } catch (err) {
          error = String(err && err.message ? err.message : err);
        }
        return { start, ok, error };
      }, options.block);
      return stamp?.start ?? null;
    },
  });
  const after = await readState(page, meta.editable.selector);
  const growth = after.text_length - pre.text_length;
  const fallback = {
    observation_id: "fallback",
    point: point.point,
    x: point.x,
    y: point.y,
    method: 'exec_command_insert_text',
    input_ms: stamp ? round(stamp.start, 3) : null,
    exec_command_ok: stamp ? stamp.ok : null,
    exec_command_error: stamp ? stamp.error : null,
    frame_ms:
      painted.frame_page_ms !== null && painted.frame_page_ms !== undefined
        ? round(painted.frame_page_ms, 3)
        : null,
    sample_ms: painted.sampleMs !== null && painted.sampleMs !== undefined ? painted.sampleMs : null,
    witness: painted.record ?? null,
    witness_refusal: painted.witness_refusal ?? null,
    witness_errors: painted.witness_errors?.length ? painted.witness_errors : null,
    text_length_before: pre.text_length,
    text_length_after: after.text_length,
    growth,
    minimum_growth: minimumGrowth,
    blocked_paste: pasteError,
  };
  attachPaintWitnessFailure(fallback, painted);
  entry.observations.push(fallback);
  if (!painted.ok) {
    entry.failure_reason = painted.reason;
    entry.assertion.failures.push('fallback_insert_not_painted');
    return entry;
  }
  if (growth < minimumGrowth) {
    entry.failure_reason = `${CORRECTNESS_PREFIX} truncated_paste`;
    entry.assertion.failures.push(entry.failure_reason);
    return entry;
  }
  const bodyCheck = assertBulkInsertBody(pre, after, options);
  if (!bodyCheck.ok) {
    entry.failure_reason = bodyCheck.reason;
    entry.assertion.failures.push(entry.failure_reason);
    return entry;
  }
  entry.outcome = 'measured';
  entry.samples_ms = [fallback.sample_ms];
  entry.sample_observation_ids = [fallback.observation_id];
  entry.assertion.passed = true;
  entry.assertion.checks = {
    text_length_grew: true,
    growth,
    expected_block_chars: options.bulkChars,
    insertion_method: 'exec_command_insert_text',
  };
  entry.failure_reason = null;
  entry.notes.push(
    `Clipboard paste was not usable (${pasteError}); the sample is the documented fallback document.execCommand('insertText') path and the payload says so.`,
  );
  return entry;
}

const PAGE_LOSS_RE =
  /Execution context was destroyed|Target (closed|crashed)|Session closed|Frame was detached|Protocol error.*Target closed|Page crashed/i;

const HEALTH_PROBE_MS = 2000;

/** @type {readonly string[]} Canonical suite failure-injection phases (@suite-phase tags must match). */
export const RUN_CRITERIA_SUITE_PHASES = [
  'input_tap',
  'ready_ms',
  'c04_mid',
  'after_c04',
  'initial_read_state',
  'frame_interval',
  'c07_mid',
  'c09_mid',
  'c08_refresh',
  'c08_refresh_read',
  'c08_mid',
  'classify_criterion',
  'classify_suite',
  'classify_health_probe',
  'stop_send',
];

function harnessErrorLabel(error) {
  const msg = String(error);
  const name = error?.name || 'Error';
  const message = error?.message ?? msg;
  return `harness_error: ${name}: ${message}`;
}

function attachPageLossTracker(page, cdp) {
  let lost = false;
  const mark = () => {
    lost = true;
  };
  if (page && typeof page.on === 'function') {
    page.on('crash', mark);
    page.on('close', mark);
  }
  if (cdp && typeof cdp.on === 'function') {
    cdp.on('close', mark);
  }
  return {
    isLost() {
      return lost || page?.isClosed?.() === true;
    },
  };
}

async function runHealthProbe(page, tracker) {
  if (typeof page?.evaluate !== 'function') {
    return { ok: false, error: new Error('health_probe_unavailable') };
  }
  let timer = null;
  try {
    await Promise.race([
      page.evaluate(() => true),
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(new Error(`health_probe_timeout after ${HEALTH_PROBE_MS}ms`)),
          HEALTH_PROBE_MS,
        );
      }),
    ]);
    return { ok: true };
  } catch (probeErr) {
    if (tracker?.isLost()) {
      return { ok: false, error: probeErr, targetLost: true };
    }
    return { ok: false, error: probeErr };
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/**
 * Label suite interruptions as page loss only when the browser target is gone.
 * A live page with a harness bug must read as harness_error, not page_lost.
 */
async function classifySuiteError(page, error, tracker) {
  if (tracker?.isLost() || page?.isClosed?.()) {
    return `page_lost: ${String(error)}`;
  }
  const msg = String(error);
  if (!PAGE_LOSS_RE.test(msg)) {
    return harnessErrorLabel(error);
  }
  // @suite-phase classify_health_probe
  const probe = await runHealthProbe(page, tracker);
  if (tracker?.isLost()) {
    return `page_lost: ${String(error)}`;
  }
  if (probe.ok) {
    return harnessErrorLabel(error);
  }
  if (probe.targetLost) {
    return `page_lost: ${String(error)}`;
  }
  const probeErr = probe.error;
  const probeName = probeErr?.name || 'Error';
  const probeMsg = probeErr?.message ?? String(probeErr);
  return `${harnessErrorLabel(error)}; health_probe: ${probeName}: ${probeMsg}`;
}

// --------------------------------------------------------------------- suite

/**
 * Run the requested criteria on a page that is already ready.
 *
 * @param {object} args
 * @param {import('playwright').Page} args.page
 * @param {import('playwright').CDPSession} args.cdp
 * @param {string} args.editSelector
 * @param {string[]} args.criteria          ids from SUITE_ORDER
 * @param {number} args.frameTimeoutMs
 * @param {number} args.quiescenceMs
 * @param {number} args.quiescenceTimeoutMs
 * @param {number} args.bulkChars
 */
export async function runCriteriaSuite({
  page,
  cdp,
  editSelector,
  criteria,
  frameTimeoutMs = 2000,
  quiescenceMs = 500,
  quiescenceTimeoutMs = 10_000,
  bulkChars = 1500,
  expectedBodyText = null,
  expectedBodyPath = null,
  correctnessAdapter: correctnessAdapterOption = undefined,
}) {
  const startedAt = Date.now();
  const startedIso = new Date(startedAt).toISOString();
  const block = bulkBlock(bulkChars);
  const options = {
    frameTimeoutMs,
    quiescenceMs,
    quiescenceTimeoutMs,
    bulkChars,
    block,
    modifier: process.platform === 'darwin' ? 'Meta' : 'Control',
    expectedBodyText: loadExpectedBody({ expectedBodyText, expectedBodyPath }),
    expectedOpeningText: loadExpectedOpening(),
    correctnessAdapter: correctnessAdapterOption,
  };
  const adapter = correctnessAdapter(options);
  const pageLoss = attachPageLossTracker(page, cdp);

  const entries = {};
  let witness = null;
  let readyPageMs = 0;
  let points = { viewport: { width: 1280, height: 900 } };
  let initialState = {};
  let meta = {
    editable: {
      selector: editSelector,
      is_content_editable: false,
      text_length: null,
      line_height_px: null,
    },
    points: [],
    point_source: 'unavailable',
  };

  async function safeCriterion(criterionId, run) {
    try {
      return await run();
    } catch (error) {
      // @suite-phase classify_criterion
      const reason = await classifySuiteError(page, error, pageLoss);
      return emptyEntry(criterionId, 'failed', reason);
    }
  }

  const fixtureWaitForRestore = criteria.includes('C08');
  const measureOptions = { ...options, fixtureWaitForRestore };

  try {
    // @suite-phase input_tap
    await page.evaluate(INSTALL_INPUT_TAP);
    // @suite-phase ready_ms
    readyPageMs = await page.evaluate(() => performance.now());

    // C04 first and before anything else touches the page: a click of our own is
    // deferred work the criterion would otherwise count.
    if (criteria.includes('C04')) {
      // @suite-phase c04_mid
      entries.C04 = await safeCriterion('C04', () => measureQuiescence(page, options, readyPageMs));
    }

    // @suite-phase after_c04
    const resolvedPoints = await page.evaluate(RESOLVE_CLICK_POINTS, editSelector);
    points = { ...points, ...resolvedPoints };
    // @suite-phase initial_read_state
    initialState = await readState(page, editSelector);
    const editableMissing = initialState.error || null;

    const needsPaint = criteria.some((id) => id !== 'C04');
    if (needsPaint) {
      let recorder = null;
      try {
        recorder = getRecorder(cdp, { manageScreencast: true });
        // @suite-phase frame_interval
        const interval = await frameInterval(page);
        witness = {
          recorder,
          frameIntervalMs: interval.median_ms,
          started: true,
          editSelector,
          async paintAfter(pageMs, callOptions = {}) {
            return witnessFrame(page, cdp, {
              afterPageMs: pageMs,
              arm: callOptions.arm ?? null,
              region: { selector: editSelector },
              recorder,
              manageScreencast: false,
              windowMs: frameTimeoutMs,
              caretMask: true,
            });
          },
        };
      } catch (err) {
        witness = {
          started: false,
          startError: String(err),
          recorder,
          frameIntervalMs: null,
          frames: [],
          ackErrors: [],
        };
      }
      if (!witness.started) {
        // The harness failed to attach the paint witness. That is our failure,
        // not the editor's, and it must be named as such on every entry.
        const reason = `paint_witness_unavailable: ${witness.startError}`;
        for (const id of criteria) {
          if (id === 'C04') continue;
          entries[id] = emptyEntry(id, 'failed', reason, {
            trial_hints: {
              cache_state: CRITERIA_META[id].cache_state,
              repetition_unit: 'fresh_process',
              run_kind: 'timing',
              feature_profile: 'P0',
            },
            assertion: {
              name: null,
              passed: false,
              scope: null,
              checks: { paint_witness_started: false },
              failures: ['paint_witness_unavailable'],
            },
          });
        }
      }
    }

    meta = {
      editable: {
        selector: editSelector,
        is_content_editable: initialState.is_content_editable === true,
        text_length: initialState.text_length === undefined ? null : initialState.text_length,
        line_height_px: points.line_height_px === undefined ? null : points.line_height_px,
      },
      points: points.points || [],
      point_source: points.source || 'unavailable',
    };

    const unavailable = editableMissing || points.error || null;
    const needsDomAdapter = criteria.some((id) => id !== 'C04');
    const adapterRefusal =
      needsDomAdapter && adapterGate(adapter, meta.editable.is_content_editable);
    const canvasWithoutAdapter = adapterRefusal;
    if (criteria.includes('C07')) {
      if (!entries.C07) {
        if (canvasWithoutAdapter) {
          entries.C07 = emptyEntry('C07', 'unsupported', canvasWithoutAdapter);
        } else
        entries.C07 =
          unavailable || meta.points.length !== 3
            ? emptyEntry('C07', 'failed', unavailable || 'click_points_unavailable', {
                assertion: {
                  name: 'hit_test_reaches_editable_and_paints',
                  passed: false,
                  scope: null,
                  checks: { editable_found: !editableMissing, points_resolved: meta.points.length },
                  failures: [unavailable || 'click_points_unavailable'],
                },
              })
            : // @suite-phase c07_mid
              await safeCriterion('C07', () => measureClicks(page, witness, options, meta));
      }
    }
    if (criteria.includes('C09') && !entries.C09) {
      entries.C09 = canvasWithoutAdapter
        ? emptyEntry('C09', 'unsupported', canvasWithoutAdapter)
        : editableMissing
          ? emptyEntry('C09', 'failed', editableMissing)
          : // @suite-phase c09_mid
            await safeCriterion('C09', () => measureUndo(page, witness, measureOptions, meta));
    }
    if (criteria.includes('C08') && entries.C09?.fixture_reset) {
      if (!entries.C09.fixture_reset.restored) {
        entries.C08 = emptyEntry('C08', 'failed', 'fixture_reset_failed_after_C09');
      } else {
        // @suite-phase c08_refresh
        const refreshed = await page.evaluate(RESOLVE_CLICK_POINTS, editSelector);
        meta.points = refreshed.points || [];
        meta.point_source = refreshed.source || meta.point_source;
        if (refreshed.line_height_px !== undefined) {
          meta.editable.line_height_px = refreshed.line_height_px;
        }
        // @suite-phase c08_refresh_read
        const refreshedState = await readState(page, editSelector);
        meta.editable.is_content_editable = refreshedState.is_content_editable === true;
        meta.editable.text_length =
          refreshedState.text_length === undefined ? null : refreshedState.text_length;
      }
    }
    if (criteria.includes('C08') && !entries.C08) {
      entries.C08 = canvasWithoutAdapter
        ? emptyEntry('C08', 'unsupported', canvasWithoutAdapter)
        : editableMissing
          ? emptyEntry('C08', 'failed', editableMissing)
          : // @suite-phase c08_mid
            await safeCriterion('C08', () => measureBulkInsert(page, witness, options, meta));
    }
  } catch (error) {
    // @suite-phase classify_suite
    const reason = await classifySuiteError(page, error, pageLoss);
    for (const id of criteria) {
      if (!entries[id]) {
        entries[id] = emptyEntry(id, 'failed', reason);
      }
    }
  }

  if (witness?.recorder) {
    // @suite-phase stop_send
    await stopRecorder(cdp);
  } else if (witness && typeof witness.stop === 'function') {
    witness.stop();
  }

  const payload = {
    probe: 'criteria_input',
    probe_version: CRITERIA_INPUT_VERSION,
    schema: CRITERIA_SCHEMA,
    driver: 'playwright',
    editor_id: null,
    url: null,
    corpus_route: null,
    viewport: points.viewport || { width: 1280, height: 900 },
    ready: {
      selector: null,
      ready_ms: null,
      ready_page_ms: round(readyPageMs, 3),
      note: 'ready_page_ms is read by the driver after the ready condition resolved, so it lags the host mark by the driver polling interval.',
    },
    editable: {
      selector: editSelector,
      box: points.box || (initialState.box ? initialState.box : null),
      is_content_editable: meta.editable.is_content_editable,
      text_length: meta.editable.text_length,
      dom_caret: meta.editable.is_content_editable && (points.text_rects || 0) > 0,
      click_point_source: meta.point_source,
      click_points: meta.points,
      line_height_px: meta.editable.line_height_px,
    },
    paint_witness: {
      mechanism: 'cdp_screencast_frame',
      frames_seen:
        witness?.recorder?.frames?.length ??
        (Array.isArray(witness?.frames) ? witness.frames.length : 0),
      frame_interval_ms: witness?.frameIntervalMs ?? null,
      timeout_ms: frameTimeoutMs,
      message: witness && witness.started === false ? `screencast unavailable: ${witness.startError}` : null,
      ack_errors:
        witness?.recorder != null ? [] : (witness?.ackErrors ?? []).slice(0, 3),
    },
    criteria_requested: criteria.slice(),
    criteria: entries,
    bulk_block: {
      chars: block.length,
      sha256_prefix: createHash('sha256').update(block).digest('hex').slice(0, 16),
    },
    modifier: options.modifier,
    started_at: startedIso,
    duration_ms: Date.now() - startedAt,
  };
  return payload;
}

export {
  measureBulkInsert,
  measureClicks,
  measureQuiescence,
  measureUndo,
  sampleAfterInput,
  OBSERVE_QUIESCENCE,
  assertFixtureBodyMatches,
  assertPreEditDocumentLoaded,
  bodyAfterInsertion,
  comparableDocumentText,
  rangeTextOfElement,
  resolveDocumentTextRoot,
};
