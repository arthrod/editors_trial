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
  const flat = normalizeNewlines(text).replace(/\n/g, '');
  // Editors paint composed characters. "cafe" + combining acute and "café"
  // are the same document text. NFC does not hide a dropped mark.
  return typeof flat.normalize === 'function' ? flat.normalize('NFC') : flat;
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

/**
 * A caret is on the clicked line when the two boxes overlap vertically by at
 * least half the caret's height. A 2 px top bound rejects a caret that sits
 * on the line and sticks a pixel above it.
 */
export function caretOverlapsLine(caret, line) {
  if (!caret || !line) return false;
  const top = Number(caret.top);
  const bottom = Number(caret.bottom);
  const lineTop = Number(line.top);
  const lineBottom = Number(line.bottom);
  const height =
    Number.isFinite(Number(caret.height)) && Number(caret.height) > 0
      ? Number(caret.height)
      : bottom - top;
  if (![top, bottom, height, lineTop, lineBottom].every((n) => Number.isFinite(n)) || !(height > 0)) {
    return false;
  }
  const overlap = Math.min(bottom, lineBottom) - Math.max(top, lineTop);
  return overlap >= height / 2;
}

export const DOCUMENT_PROTECTED_READ_ONLY = 'document_protected_read_only';
export const CARET_MOVE_NOT_PAINTED = 'caret_move_not_painted';

function adapterGate(adapter) {
  if (!adapter) {
    return 'no_correctness_adapter: canvas surface without model API or pixel probe';
  }
  if (adapter === 'dom_innerText' || adapter.startsWith('dom_')) {
    // Usable means a click and a key change the document. The selector node
    // being contenteditable is not that question.
    return null;
  }
  return `correctness_adapter_not_implemented: ${adapter}`;
}

function domAdapter(adapter) {
  return adapter === 'dom_innerText' || (typeof adapter === 'string' && adapter.startsWith('dom_'));
}

function bodyAfterInsertion(fixtureBody, insertText, offset) {
  const text = normalizeNewlines(fixtureBody);
  const at = Math.max(0, Math.min(offset === null || offset === undefined ? text.length : offset, text.length));
  return text.slice(0, at) + insertText + text.slice(at);
}

/** True when `after` is `before` with exactly one copy of `ch` inserted. */
function differsBySingleInsertion(before, after, ch) {
  const left = String(before || '');
  const right = String(after || '');
  const needle = String(ch || '');
  if (!needle || right.length !== left.length + needle.length) return false;
  let i = 0;
  while (i < left.length && left[i] === right[i]) i += 1;
  return right.slice(i, i + needle.length) === needle && right.slice(i + needle.length) === left.slice(i);
}

function textDeltaNote(actual, expected) {
  const got = comparableDocumentText(actual);
  const exp = comparableDocumentText(expected);
  let i = 0;
  const n = Math.min(got.length, exp.length);
  while (i < n && got[i] === exp[i]) i += 1;
  const code = (text) => {
    if (!text) return 'end';
    const point = text.codePointAt(0);
    return `U+${point.toString(16)}`;
  };
  return `text delta at ${i}: expected ${code(exp.slice(i))} got ${code(got.slice(i))} (expected_len ${exp.length}, got_len ${got.length})`;
}

function assertFixtureBodyMatches(state, expectedBody) {
  if (expectedBody === null) return { ok: true };
  if (!state || state.error) {
    return { ok: false, reason: `${CORRECTNESS_PREFIX} ${state?.error || 'text_unreadable'}` };
  }
  if (comparableDocumentText(state.text) !== comparableDocumentText(expectedBody)) {
    return {
      ok: false,
      reason: `${CORRECTNESS_PREFIX} fixture_body_mismatch`,
      detail: textDeltaNote(state.text, expectedBody),
    };
  }
  return { ok: true };
}

function assertPreEditDocumentLoaded(state, options) {
  if (!state || state.error) {
    return { ok: false, reason: `${CORRECTNESS_PREFIX} ${state?.error || 'text_unreadable'}` };
  }
  if (options.openingRequired && !options.expectedOpeningText) {
    return {
      ok: false,
      reason: `${CORRECTNESS_PREFIX} document_opening_expectation_absent`,
    };
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
  const base = normalizeNewlines(before.text);
  const actual = normalizeNewlines(after.text);
  const block = normalizeNewlines(options.block);
  const offset = before.selection_offset ?? base.length;
  const expected = bodyAfterInsertion(base, block, offset);
  // The reported caret offset can miss where a paged editor inserted the block.
  // One contiguous insertion of that block is the paste. Any other edit is not.
  if (actual !== expected && !differsBySingleInsertion(base, actual, block)) {
    return {
      ok: false,
      reason: `${CORRECTNESS_PREFIX} bulk_text_or_position`,
      detail: textDeltaNote(actual, expected),
    };
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
  // Eigenpal's pages virtualize. The mounted DOM sum drops the tail after a
  // paste near the start. The editor model is the document.
  let textSource = 'dom';
  let text = null;
  try {
    const hook = window.__DOCX_EDITOR_E2E__;
    const editor = hook && typeof hook.getEditor === 'function' ? hook.getEditor() : null;
    if (editor && typeof editor.query === 'function') {
      const paragraphs = editor.query({ type: 'paragraphs' });
      if (Array.isArray(paragraphs)) {
        text = paragraphs.map((p) => (p && typeof p.text === 'string' ? p.text : '')).join('');
        textSource = 'editor_model';
      }
    }
  } catch {
    text = null;
    textSource = 'dom';
  }
  // Docxodus paints one contenteditable per block, plus an offscreen
  // pagination staging copy and header bands. The document is the visible
  // body blocks. range text of the host counts the copies too.
  const chromeSelector =
    '[data-list-marker], a.footnote-ref, a.endnote-ref, a[class$="-backref"], a.comment-marker, .footnote-number, .endnote-number, del[class*="-del"], del[class*="move-from"], span[class*="para-mark-del"]';
  const blockPlain = (block) => {
    let out = '';
    const walk = (node) => {
      if (!node) return;
      if (node.nodeType === 1) {
        if (typeof node.matches === 'function' && node.matches(chromeSelector)) return;
        if (node.hasAttribute && node.hasAttribute('data-docx-tab')) {
          out += '\t';
          return;
        }
        const kids = node.childNodes;
        for (let i = 0; i < kids.length; i += 1) walk(kids[i]);
        return;
      }
      if (node.nodeType === 3) out += node.textContent || '';
    };
    walk(block);
    return out.replace(/[\u200E\u200F\u061C\u202A-\u202E\u2066-\u2069]/g, '');
  };
  const docxRoot =
    el.querySelector &&
    (el.querySelector('#pagination-container') || el.querySelector('.docx-body-flow'));
  const docxBlocks = docxRoot
    ? Array.from(docxRoot.querySelectorAll('[data-anchor][contenteditable="true"]')).filter((block) => {
        if (typeof block.closest !== 'function') return true;
        if (block.closest('#pagination-staging, .page-staging, [data-hf-band], [data-hf-inert], [data-section-filler]')) {
          return false;
        }
        if (block.closest('.footnotes, .endnotes, [class$="-footnotes"], [class$="-endnotes"]')) return false;
        return true;
      })
    : [];
  if (text === null && docxBlocks.length) {
    text = docxBlocks.map((block) => blockPlain(block)).join('');
    textSource = 'editor_blocks';
  }
  if (text === null) {
    const runs =
      el.querySelectorAll && el.isContentEditable !== true
        ? el.querySelectorAll('.superdoc-text-run')
        : [];
    if (runs.length) {
      text = Array.from(runs)
        .map((node) => node.textContent || '')
        .join('');
      textSource = 'painted_runs';
    } else {
      text =
        paragraphNodes.length > 0
          ? paragraphNodes.map((node) => rangeText(node)).join('')
          : rangeText(textRoot);
      textSource = 'dom';
    }
  }
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
    if (textSource === 'editor_blocks' && docxBlocks.length > 0) {
      let offset = 0;
      let placed = false;
      for (const block of docxBlocks) {
        if (!placed && (block.contains(startElement) || block === startElement)) {
          const pre = range.cloneRange();
          pre.selectNodeContents(block);
          pre.setEnd(range.startContainer, range.startOffset);
          const holder = document.createElement('div');
          holder.appendChild(pre.cloneContents());
          selectionOffset = offset + blockPlain(holder);
          placed = true;
        }
        offset += blockPlain(block).length;
      }
    } else if (paragraphNodes.length > 0) {
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
  const activeTag = active ? String(active.tagName || '').toLowerCase() : null;
  const editorRoot =
    (typeof el.closest === 'function' && (el.closest('#editor') || el.closest('#editorHost'))) || el;
  const focusInEditor = Boolean(
    active &&
      (active === el ||
        (el.contains && el.contains(active)) ||
        active === editorRoot ||
        (editorRoot.contains && editorRoot.contains(active))),
  );
  if (!anchorInside && focusInEditor && (activeTag === 'textarea' || active.isContentEditable === true)) {
    anchorInside = true;
  }
  // SuperDoc keeps the browser selection on a hidden textarea. That range
  // is 0×0. The painted caret is the editor's anchor rect.
  let selectionExpanded = Boolean(caret && caret.collapsed === false);
  if (activeTag === 'textarea' && active && active.selectionStart !== active.selectionEnd) {
    selectionExpanded = true;
  }
  const superdocCaret = () => {
    try {
      const sd = globalThis.__SUPERDOC_E2E__;
      const handle = sd && sd.ui && sd.ui.selection;
      if (!handle || typeof handle.getAnchorRect !== 'function') return null;
      const rect = handle.getAnchorRect({ placement: 'start' });
      if (!rect || !(rect.height > 0) || !Number.isFinite(rect.top) || !Number.isFinite(rect.bottom)) {
        return null;
      }
      if (typeof handle.getSnapshot === 'function') {
        const snap = handle.getSnapshot();
        const quoted = snap && typeof snap.quotedText === 'string' ? snap.quotedText : '';
        const target = snap && snap.selectionTarget;
        const start = target && target.start;
        const end = target && target.end;
        const range =
          start &&
          end &&
          (start.blockId !== end.blockId || start.offset !== end.offset || start.edge !== end.edge);
        // `empty: false` on a pending snapshot is not a selection. Quoted
        // text or two different endpoints is.
        if (quoted.length > 0 || range) selectionExpanded = true;
      }
      return {
        top: rect.top,
        bottom: rect.bottom,
        left: Number.isFinite(rect.left) ? rect.left : 0,
        right: Number.isFinite(rect.right) ? rect.right : 0,
        height: rect.height,
        collapsed: !selectionExpanded,
      };
    } catch {
      return null;
    }
  };
  if (!caret || !(caret.height > 0)) {
    const fromModel = superdocCaret();
    if (fromModel) {
      caret = fromModel;
      anchorInside = true;
    }
  }
  if ((!caret || !(caret.height > 0)) && typeof document.querySelector === 'function') {
    const root = document.querySelector('#editor') || el;
    const paintedCaret =
      root && typeof root.querySelector === 'function'
        ? root.querySelector('.superdoc__temp-selection, .superdoc-caret, [data-superdoc-caret]')
        : null;
    if (paintedCaret && typeof paintedCaret.getBoundingClientRect === 'function') {
      const rect = paintedCaret.getBoundingClientRect();
      // A wide temp-selection is a highlight, not a caret.
      if (rect.height > 0 && rect.width > 0 && rect.width <= 8) {
        caret = {
          top: rect.top,
          bottom: rect.bottom,
          left: rect.left,
          right: rect.right,
          height: rect.height,
          collapsed: !selectionExpanded,
        };
        anchorInside = true;
      }
    }
  }
  const descendantEditable = Boolean(
    typeof el.querySelector === 'function' && el.querySelector('[contenteditable="true"]'),
  );
  let readOnly = false;
  if (el.getAttribute && (el.getAttribute('contenteditable') === 'false' || el.getAttribute('aria-readonly') === 'true')) {
    readOnly = true;
  }
  try {
    const hook = window.__DOCX_EDITOR_E2E__;
    const editor = hook && typeof hook.getEditor === 'function' ? hook.getEditor() : null;
    const snap = editor && typeof editor.snapshot === 'function' ? editor.snapshot() : null;
    if (snap && snap.editable === false) readOnly = true;
    if (snap && snap.editable === true) readOnly = false;
  } catch {
    // The model hook is optional. A throw leaves the DOM signal as it was.
  }
  if (descendantEditable || el.isContentEditable === true) readOnly = false;
  const inputReachable =
    !readOnly &&
    (el.isContentEditable === true ||
      descendantEditable ||
      textSource === 'editor_model' ||
      textSource === 'editor_blocks' ||
      textSource === 'painted_runs' ||
      (focusInEditor && (activeTag === 'textarea' || active.isContentEditable === true)));
  return {
    text,
    text_length: text.length,
    text_source: textSource,
    is_content_editable: el.isContentEditable === true || descendantEditable,
    input_reachable: inputReachable,
    read_only: readOnly,
    active_inside: focusInEditor && active !== document.body && active !== document.documentElement,
    active_tag: activeTag,
    anchor_inside: anchorInside,
    selection_offset: selectionOffset,
    selection_expanded: selectionExpanded,
    caret,
    box: { left: box.left, top: box.top, right: box.right, bottom: box.bottom },
    scroll: { x: window.scrollX, y: window.scrollY },
  };
};

/**
 * Where a click and a key would land. Page context: no Node closures.
 * A contenteditable descendant, a focused textarea, or the editor model counts.
 * The selector node itself being contenteditable does not.
 */
const DESCRIBE_INPUT_SURFACE = (request) => {
  const selector = request && request.selector ? request.selector : request;
  const mode = document.querySelector('#modeEditor');
  const host = document.querySelector('#editorHost');
  const hostEditable = host && host.querySelector('[contenteditable="true"]');
  const selected = selector ? document.querySelector(selector) : null;
  const descendant =
    selected && selected.querySelector ? selected.querySelector('[contenteditable="true"]') : null;
  let kind = 'missing';
  let bound = typeof selector === 'string' ? selector : null;
  if (hostEditable) {
    kind = 'contenteditable_descendant';
    bound = '#editorHost';
  } else if (selected && selected.isContentEditable === true) {
    kind = 'contenteditable';
  } else if (descendant) {
    kind = 'contenteditable_descendant';
  } else if (
    window.__DOCX_EDITOR_E2E__ &&
    typeof window.__DOCX_EDITOR_E2E__.getEditor === 'function'
  ) {
    kind = 'editor_model';
  } else if (selected && selected.querySelector && selected.querySelector('.superdoc-text-run')) {
    kind = 'painted_runs';
  } else if (selected) {
    kind = 'dom';
  }
  let readOnly = false;
  const node = selected || host;
  if (
    node &&
    node.getAttribute &&
    (node.getAttribute('contenteditable') === 'false' || node.getAttribute('aria-readonly') === 'true')
  ) {
    readOnly = true;
  }
  try {
    const hook = window.__DOCX_EDITOR_E2E__;
    const editor = hook && typeof hook.getEditor === 'function' ? hook.getEditor() : null;
    const snap = editor && typeof editor.snapshot === 'function' ? editor.snapshot() : null;
    if (snap && snap.editable === false) readOnly = true;
    if (snap && snap.editable === true) readOnly = false;
  } catch {
    // The model hook is optional.
  }
  const contenteditable = kind === 'contenteditable' || kind === 'contenteditable_descendant';
  if (contenteditable) readOnly = false;
  return {
    mode_button: Boolean(mode),
    kind,
    selector: bound,
    read_only: readOnly,
    contenteditable,
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
  // A 2 px sliver at the clip edge is not a click. The caret cannot land
  // there, and the pointer event never reaches the document.
  const visible = rects.filter(
    (r) =>
      Math.min(r.bottom, clip.bottom) - Math.max(r.top, clip.top) >= 8 &&
      Math.min(r.right, clip.right) - Math.max(r.left, clip.left) >= 8,
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
    // A long client rect can put the 35% mark on chrome at the side of the
    // page. Stay in the text column, inside the rect.
    const xInRect = (rect) => {
      const mid = (clip.left + clip.right) / 2;
      const lo = rect.left + 2;
      const hi = rect.right - 2;
      return round(clampX(Math.min(Math.max(mid, lo), Math.max(lo, hi))), 1);
    };
    points.push({
      point: 'first_text_line',
      x: xInRect(first),
      y: round(clampY((first.top + first.bottom) / 2), 1),
      line: { top: round(first.top, 1), bottom: round(first.bottom, 1) },
    });
    points.push({
      point: 'last_text_line',
      x: xInRect(last),
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
  const hitInsideEditable = (x, y) => {
    const target = document.elementFromPoint(x, y);
    if (!target) return false;
    return el === target || el.contains(target);
  };
  // SuperDoc paints the body as text runs. A toolbar label inside the same
  // element is not a place a caret can land, so it is not a click point.
  const runsPresent = Boolean(el.querySelector && el.querySelector('.superdoc-text-run'));
  const textHit = (x, y) => {
    const target = document.elementFromPoint(x, y);
    if (!target || !(el === target || el.contains(target))) return false;
    if (typeof target.closest !== 'function') return true;
    if (target.closest('button, a, input, select, textarea, [role="button"]')) return false;
    if (runsPresent) return Boolean(target.closest('.superdoc-text-run'));
    return true;
  };
  for (const point of points) {
    point.hit_inside_editable = hitInsideEditable(point.x, point.y);
    if (point.point !== 'page_centre') point.text_hit = textHit(point.x, point.y);
  }
  const occluded = points.filter((p) => p.hit_inside_editable === false || p.text_hit === false);
  for (const bad of occluded) {
    // A clamped edge lands on chrome. Walk visible lines until the click is
    // inside the editor. First line walks downward, last line walks upward.
    if ((bad.point !== 'last_text_line' && bad.point !== 'first_text_line') || visible.length < 2) {
      continue;
    }
    const ranked = [...visible].sort((a, b) =>
      bad.point === 'first_text_line' ? a.top - b.top : b.bottom - a.bottom,
    );
    for (const rect of ranked) {
      const mid = (clip.left + clip.right) / 2;
      const lo = rect.left + 2;
      const hi = Math.max(lo, rect.right - 2);
      const x = round(clampX(Math.min(Math.max(mid, lo), hi)), 1);
      const y = round(clampY((rect.top + rect.bottom) / 2), 1);
      if (!textHit(x, y)) continue;
      bad.x = x;
      bad.y = y;
      bad.line = { top: round(rect.top, 1), bottom: round(rect.bottom, 1) };
      bad.hit_inside_editable = true;
      bad.text_hit = true;
      break;
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

/**
 * SuperDoc's document text. Painted line runs replace a wrapping space with a
 * break, so correctness reads `activeEditor.doc.getText` when the host
 * exposes the instance. Browser getText may return a promise. Page context.
 */
async function READ_SUPERDOC_TEXT() {
  try {
    const sd = globalThis.__SUPERDOC_E2E__;
    const doc = sd && sd.activeEditor && sd.activeEditor.doc;
    if (!doc || typeof doc.getText !== 'function') return null;
    const value = await doc.getText({});
    return typeof value === 'string' ? value : null;
  } catch {
    return null;
  }
}

async function readState(page, selector) {
  const state = await page.evaluate(READ_EDITABLE_STATE, selector);
  if (!state || typeof state !== 'object' || state.text_source !== 'painted_runs') return state;
  let model = null;
  try {
    model = await page.evaluate(READ_SUPERDOC_TEXT);
  } catch {
    model = null;
  }
  if (typeof model !== 'string' || !model.length) return state;
  return { ...state, text: model, text_length: model.length, text_source: 'editor_model' };
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

/** Pure helper for click-point hit tests (exported for contract tests). */
export function pointerTargetInsideEditable(editable, target) {
  if (!editable || target == null) return false;
  if (typeof editable.contains === 'function') {
    return editable === target || editable.contains(target);
  }
  return editable === target;
}

async function resolveFreshClickPoint(page, selector, prefer = 'line') {
  const resolved = await page.evaluate(RESOLVE_CLICK_POINTS, selector);
  if (!resolved || resolved.error) return null;
  const candidates = (resolved.points || []).filter((p) => p.hit_inside_editable !== false);
  // Typing wants a text line: the centre of a paged sheet is often the margin.
  // Paste wants that centre when the hit is inside the editor. The last line of
  // complex-corpus accepted 1409 of 1500 characters; the centre accepted 1500.
  const order = prefer === 'centre'
    ? ['page_centre', 'last_text_line', 'first_text_line']
    : ['last_text_line', 'first_text_line', 'page_centre'];
  const pick =
    order.map((name) => candidates.find((p) => p.point === name)).find(Boolean) ||
    candidates[0];
  if (pick && Number.isFinite(pick.x) && Number.isFinite(pick.y)) return pick;
  return null;
}

async function ensureCollapsedCaretAtClick(page, selector) {
  return page.evaluate(async (sel) => {
    const el = document.querySelector(sel);
    const selection = window.getSelection();
    if (el && selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0);
      if (!range.collapsed) range.collapse(false);
    }
    const active = document.activeElement;
    if (
      active &&
      String(active.tagName || '').toLowerCase() === 'textarea' &&
      active.selectionStart !== active.selectionEnd
    ) {
      const end = active.selectionEnd;
      active.selectionStart = end;
      active.selectionEnd = end;
    }
    try {
      const sd = globalThis.__SUPERDOC_E2E__;
      const handle = sd && sd.ui && sd.ui.selection;
      if (handle && typeof handle.getSnapshot === 'function' && typeof handle.apply === 'function') {
        const snap = handle.getSnapshot();
        const quoted = snap && typeof snap.quotedText === 'string' ? snap.quotedText : '';
        const target = snap && snap.selectionTarget;
        const start = target && target.start;
        const end = target && target.end;
        const range =
          start &&
          end &&
          (start.blockId !== end.blockId || start.offset !== end.offset || start.edge !== end.edge);
        const expanded = quoted.length > 0 || Boolean(range);
        if (expanded && target && target.start) {
          await handle.apply({
            kind: 'selection',
            start: target.start,
            end: target.start,
            story: target.story,
          });
        }
      }
    } catch {
      // A unit double has no editor model. The DOM collapse above stands.
    }
    const after = window.getSelection();
    return {
      collapsed: !after || after.rangeCount === 0 ? null : after.getRangeAt(0).collapsed,
    };
  }, selector);
}

async function waitForPasteGrowth(page, selector, before, options, minimumGrowth, maxWaitMs = 2000) {
  const deadline = Date.now() + maxWaitMs;
  let last = null;
  let sawStable = 0;
  let lastGrowth = null;
  while (Date.now() < deadline) {
    last = await readState(page, selector);
    const growth = last.text_length - before.text_length;
    if (growth >= minimumGrowth) {
      if (growth === lastGrowth) {
        sawStable += 1;
        if (sawStable >= 3) return last;
      } else {
        sawStable = 0;
        lastGrowth = growth;
      }
    }
    await sleep(16);
  }
  return last ?? (await readState(page, selector));
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

function caretPaintRegion(caret, point) {
  const line = point && point.line;
  if (caret && Number.isFinite(Number(caret.top)) && Number.isFinite(Number(caret.left))) {
    const height = Number(caret.height) > 0 ? Number(caret.height) : 16;
    const width = Number.isFinite(Number(caret.right))
      ? Math.max(8, Number(caret.right) - Number(caret.left))
      : 8;
    return {
      rect: {
        x: Math.max(0, Number(caret.left) - 4),
        y: Math.max(0, Number(caret.top) - 2),
        width: width + 8,
        height: height + 4,
      },
    };
  }
  if (line && Number.isFinite(Number(line.top)) && Number.isFinite(Number(point.x))) {
    return {
      rect: {
        x: Math.max(0, Number(point.x) - 12),
        y: Math.max(0, Number(line.top) - 2),
        width: 32,
        height: Math.max(8, Number(line.bottom) - Number(line.top) + 4),
      },
    };
  }
  return null;
}

/** A second input→frame sample of a caret move, with the caret mask off. */
async function witnessUnmaskedCaretMove(page, witness, point, state, key = 'ArrowRight') {
  const region = caretPaintRegion(state && state.caret, point);
  let input = null;
  const record = await witness.paintAfter(null, {
    caretMask: false,
    region: region || undefined,
    arm: async () => {
      await clearInputs(page);
      if (page.keyboard && typeof page.keyboard.press === 'function') {
        await page.keyboard.press(key);
      }
      input = await firstInput(page, { kind: 'keydown' });
      return input ? input.t : null;
    },
  });
  return { record, input };
}

/** Docxodus records an edit on blur. Undo before that blur has nothing to revert. */
function COMMIT_FOCUSED_BLOCK() {
  const active = document.activeElement;
  if (!active || typeof active.blur !== 'function') return false;
  if (active === document.body || active === document.documentElement) return false;
  active.blur();
  return true;
}

function EDITOR_MODE_BUTTON() {
  return Boolean(document.querySelector('#modeEditor'));
}

function caretMovePainted(retry, verdict) {
  const record = retry && retry.record;
  return Boolean(
    retry &&
      retry.input &&
      record &&
      record.outcome === 'witnessed' &&
      record.frame_page_ms !== null &&
      record.frame_page_ms !== undefined &&
      verdict &&
      !verdict.refused &&
      verdict.ok,
  );
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
  const canReach =
    meta.editable.input_reachable === true || meta.editable.is_content_editable === true;
  if (!canReach) {
    entry.outcome = 'failed';
    entry.failure_reason =
      meta.editable.refusal || `${CORRECTNESS_PREFIX} input_did_not_change_document`;
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
    const armClick = async () => {
      await page.mouse.click(point.x, point.y);
      const tapped = await firstInput(page, { kind: 'pointerdown' });
      if (tapped === null) return null;
      input = tapped;
      return tapped.t;
    };
    let frameRecord = await witness.paintAfter(null, { arm: armClick });
    // The centre click can scroll a paged editor. The first-line coordinate
    // from before that click then lands on chrome and never reaches the document.
    if (input === null && point.line && meta.editable && meta.editable.selector) {
      let freshPoint = null;
      try {
        const fresh = await page.evaluate(RESOLVE_CLICK_POINTS, meta.editable.selector);
        freshPoint = (fresh && fresh.points ? fresh.points : []).find((p) => p.point === point.point);
      } catch {
        freshPoint = null;
      }
      const moved =
        freshPoint &&
        Number.isFinite(freshPoint.x) &&
        Number.isFinite(freshPoint.y) &&
        (Math.abs(freshPoint.x - point.x) > 2 || Math.abs(freshPoint.y - point.y) > 2);
      if (moved) {
        point.x = freshPoint.x;
        point.y = freshPoint.y;
        point.line = freshPoint.line || point.line;
        observation.x = point.x;
        observation.y = point.y;
        observation.line = point.line;
        await clearInputs(page);
        frameRecord = await witness.paintAfter(null, { arm: armClick });
      }
    }
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
      if (correctnessEarly.detail) entry.notes.push(`${point.point}: ${correctnessEarly.detail}`);
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
    const correctness = assertPreEditDocumentLoaded(state, options);
    if (!correctness.ok) {
      observation.failure = correctness.reason;
      entry.assertion.failures.push(`${point.point}: ${correctness.reason}`);
      entry.observations.push(observation);
      continue;
    }
    // A point on a text line must place the caret on that line. The page
    // centre has no line box: it only has to keep the caret in the editable.
    const caretOnLine = point.line === null ? true : caretOverlapsLine(state.caret, point.line);
    observation.caret_on_clicked_line = caretOnLine;
    if (!state.anchor_inside || !caretOnLine) {
      observation.failure = state.anchor_inside
        ? `${CORRECTNESS_PREFIX} caret_not_on_clicked_line`
        : 'caret_not_inside_editable';
      entry.assertion.failures.push(`${point.point}: ${observation.failure}`);
      entry.observations.push(observation);
      continue;
    }
    if (target.inside === false || point.hit_inside_editable === false) {
      observation.failure = 'pointer_target_outside_editable';
      entry.assertion.failures.push(`${point.point}: pointer_target_outside_editable`);
      entry.observations.push(observation);
      continue;
    }
    const framePainted =
      frameRecord &&
      frameRecord.outcome === 'witnessed' &&
      frameRecord.frame_page_ms !== null;
    let witnessVerdict = frameRecord ? validateWitnessRecord(frameRecord) : { refused: true, ok: false };
    const witnessPublishable = framePainted && !witnessVerdict.refused && witnessVerdict.ok;
    if (!witnessPublishable) {
      // Frames arrived and the mask hid the caret. A dead screencast (no frames
      // at all) stays no_painted_frame: a second full window would not paint.
      const framesFlowed = (frameRecord?.frames_after || 0) > 0 || (frameRecord?.frames_total || 0) > 0;
      const caretHidden =
        frameRecord?.outcome === 'no_frame' &&
        frameRecord?.caret_masked !== false &&
        framesFlowed &&
        (frameRecord?.changed_pixels === 0 || frameRecord?.changed_pixels == null);
      if (!caretHidden) {
        observation.failure =
          frameRecord?.outcome === 'no_frame'
            ? `no_painted_frame_within_${options.frameTimeoutMs}ms`
            : `paint_witness_refused: ${witnessVerdict.reason || 'witness_refused'}`;
        observation.witness_refusal = witnessVerdict.reason ?? null;
        entry.assertion.failures.push(`${point.point}: ${observation.failure.split(': ')[0]}`);
        entry.observations.push(observation);
        continue;
      }
      // A masked screencast that never paints the caret is not a latency.
      // Retry once, unmasked, on the caret's own region. The sample is that
      // frame or nothing: the timeout clock is never stored.
      let retry = await witnessUnmaskedCaretMove(page, witness, point, state, 'ArrowRight');
      let retryRecord = retry.record;
      let retryVerdict = retryRecord ? validateWitnessRecord(retryRecord) : { refused: true, ok: false };
      let retryPainted = caretMovePainted(retry, retryVerdict);
      // ArrowRight at the end of a line does not move. One ArrowLeft is still
      // a caret move. A second no-frame is a refusal, not a timeout sample.
      const arrowWasStill =
        !retryPainted &&
        retryRecord &&
        retryRecord.outcome === 'no_frame' &&
        ((retryRecord.frames_after || 0) > 0 || (retryRecord.frames_total || 0) > 0) &&
        (retryRecord.changed_pixels === 0 || retryRecord.changed_pixels == null);
      if (arrowWasStill) {
        const left = await witnessUnmaskedCaretMove(page, witness, point, state, 'ArrowLeft');
        const leftVerdict = left.record ? validateWitnessRecord(left.record) : { refused: true, ok: false };
        if (caretMovePainted(left, leftVerdict)) {
          retry = left;
          retryRecord = left.record;
          retryVerdict = leftVerdict;
          retryPainted = true;
        }
      }
      observation.caret_paint_attempt = 'unmasked_caret_region';
      observation.witness = retryRecord || frameRecord;
      observation.witness_verdict = retryVerdict;
      observation.witness_errors = retryVerdict.errors || [];
      if (!retryPainted) {
        observation.failure = CARET_MOVE_NOT_PAINTED;
        observation.witness_refusal = retryVerdict.reason ?? null;
        delete observation.sample_ms;
        entry.assertion.failures.push(`${point.point}: ${CARET_MOVE_NOT_PAINTED}`);
        entry.observations.push(observation);
        continue;
      }
      observation.witness_refusal = null;
      observation.input_ms = round(retry.input.t, 3);
      observation.frame_ms = round(retryRecord.frame_page_ms, 3);
      const sampleMs = round(retryRecord.frame_page_ms - retry.input.t, 3);
      observation.sample_ms = sampleMs;
      observation.sub_frame = sampleMs < witness.frameIntervalMs;
      samples.push(sampleMs);
      subFrameSamples.push(observation.sub_frame);
      entry.observations.push(observation);
      await settle(page);
      continue;
    }
    observation.frame_ms = round(frameRecord.frame_page_ms, 3);
    const sampleMs = round(frameRecord.frame_page_ms - input.t, 3);
    const subFrame = sampleMs < witness.frameIntervalMs;
    observation.sample_ms = sampleMs;
    observation.sub_frame = subFrame;
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
  if (!(state.input_reachable === true || state.is_content_editable === true)) {
    entry.outcome = 'failed';
    entry.failure_reason =
      state.refusal ||
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
  const point = await resolveFreshClickPoint(page, meta.editable.selector);
  if (!point) {
    entry.failure_reason = 'no_click_point_resolved';
    entry.assertion.failures.push('no_click_point_resolved');
    return entry;
  }
  await clearInputs(page);
  await page.mouse.click(point.x, point.y);
  await settle(page);
  const target = await pointerTargetInside(page, meta.editable.selector);
  if (target?.inside === false) {
    entry.failure_reason = 'pointer_target_outside_editable';
    entry.assertion.failures.push('pointer_target_outside_editable');
    return entry;
  }
  const before = await readState(page, meta.editable.selector);
  if (before.error) {
    entry.failure_reason = before.error;
    return entry;
  }
  if (!before.active_inside && !before.anchor_inside) {
    entry.failure_reason = 'editor_did_not_take_focus_after_click';
    entry.assertion.failures.push('editor_did_not_take_focus_after_click');
    return entry;
  }
  const focusAfterClick = before.active_inside === true;
  if (
    before.selection_expanded === true ||
    (before.caret && before.caret.collapsed === false)
  ) {
    await ensureCollapsedCaretAtClick(page, meta.editable.selector);
    let rechecked = await readState(page, meta.editable.selector);
    const stillExpanded = (state) =>
      (state.caret && state.caret.collapsed === false) || state.selection_expanded === true;
    if (stillExpanded(rechecked) && page.keyboard && typeof page.keyboard.press === 'function') {
      // The model apply could not see a target. An unmodified arrow collapses
      // a word selection in the focused editor and does not edit the text.
      await page.keyboard.press('ArrowRight');
      await settle(page, 40);
      rechecked = await readState(page, meta.editable.selector);
    }
    if (stillExpanded(rechecked)) {
      entry.failure_reason = 'selection_not_collapsed_before_typing';
      entry.assertion.failures.push('selection_not_collapsed_before_typing');
      return entry;
    }
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
      entry.failure_reason = focusAfterClick
        ? 'typed_character_not_observable_in_document_text'
        : 'editor_did_not_take_focus_after_click';
      entry.observations.push({
        point: point.point,
        x: point.x,
        y: point.y,
        text_length_before: before.text_length,
        text_length_after_typing: typedState.text_length,
        frames_waited: typedFrames,
        focus_after_click: focusAfterClick,
      });
      entry.assertion.failures.push(entry.failure_reason);
      return entry;
    }
    const insertOffset = before.selection_offset ?? before.text.length;
    const expectedTyped = bodyAfterInsertion(before.text, 'x', insertOffset);
    // The caret offset is the editor's. A single inserted "x" anywhere in the
    // document text is the character landing. A second edit is not.
    if (typedState.text !== expectedTyped && !differsBySingleInsertion(before.text, typedState.text, 'x')) {
      entry.failure_reason = `${CORRECTNESS_PREFIX} typed_character_or_position`;
      entry.notes.push(textDeltaNote(typedState.text, expectedTyped));
      entry.assertion.failures.push(entry.failure_reason);
      entry.observations.push({
        point: point.point,
        text_length_before: before.text_length,
        text_length_after_typing: typedState.text_length,
        selection_offset: before.selection_offset,
      });
      return entry;
    }
    // The session undo stack does not contain a block edit until blur commits it.
    if (typedState.text_source === 'editor_blocks') {
      try {
        await page.evaluate(COMMIT_FOCUSED_BLOCK);
      } catch {
        // A unit double with no document keeps the typed text as it is.
      }
      await settle(page, 80);
      const committed = await readState(page, meta.editable.selector);
      if (
        committed.text !== expectedTyped &&
        !differsBySingleInsertion(before.text, committed.text, 'x')
      ) {
        entry.failure_reason = `${CORRECTNESS_PREFIX} typed_character_not_committed`;
        entry.notes.push(textDeltaNote(committed.text, expectedTyped));
        entry.assertion.failures.push(entry.failure_reason);
        entry.observations.push({
          point: point.point,
          text_length_before: before.text_length,
          text_length_after_typing: committed.text_length,
          selection_offset: before.selection_offset,
        });
        return entry;
      }
      typedState = committed;
      await page.mouse.click(point.x, point.y);
      await settle(page, 40);
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
      let afterUndo = null;
      try {
        afterUndo = await readState(page, meta.editable.selector);
      } catch {
        afterUndo = null;
      }
      observation.text_length_after_undo = afterUndo ? afterUndo.text_length : null;
      observation.text_restored = Boolean(afterUndo && afterUndo.text === before.text);
      entry.observations.push(observation);
      // An empty frame after a key that left the character in place is the
      // editor refusing the undo, not a witness timeout to publish.
      if (afterUndo && afterUndo.text !== before.text) {
        entry.failure_reason = `${CORRECTNESS_PREFIX} undo_did_not_restore_document_text`;
        entry.notes.push(
          'The undo key left the typed character in the document, so the empty frame is not a latency.',
        );
        entry.assertion.failures.push(entry.failure_reason);
        return entry;
      }
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
      // The undo key ran and the document is not the text from before the
      // character. That is the undo missing, not a fixture that failed to load.
      if (comparableDocumentText(after.text) !== comparableDocumentText(before.text)) {
        entry.failure_reason = `${CORRECTNESS_PREFIX} undo_did_not_restore_document_text`;
        entry.notes.push(restored.detail || textDeltaNote(after.text, before.text));
        entry.assertion.failures.push(entry.failure_reason);
        return entry;
      }
      entry.failure_reason = restored.reason;
      if (restored.detail) entry.notes.push(restored.detail);
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
          // Docxodus reload returns to render mode. The editor surface is
          // empty until #modeEditor mounts it, so a text compare before that
          // click can never succeed.
          try {
            if ((await page.evaluate(EDITOR_MODE_BUTTON)) === true) {
              await openEditorMode(page);
            }
          } catch {
            // The reload already happened. The text wait below records the miss.
          }
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
  if (!(state.input_reachable === true || state.is_content_editable === true)) {
    entry.outcome = 'failed';
    entry.failure_reason =
      state.refusal ||
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
  const point = await resolveFreshClickPoint(page, meta.editable.selector, 'centre');
  if (!point) {
    entry.failure_reason = 'no_click_point_resolved';
    entry.assertion.failures.push('no_click_point_resolved');
    return entry;
  }
  await clearInputs(page);
  await page.mouse.click(point.x, point.y);
  await settle(page, 200);
  const target = await pointerTargetInside(page, meta.editable.selector);
  if (target?.inside === false) {
    entry.failure_reason = 'pointer_target_outside_editable';
    entry.assertion.failures.push('pointer_target_outside_editable');
    return entry;
  }
  const before = await readState(page, meta.editable.selector);
  if (before.error) {
    entry.failure_reason = before.error;
    return entry;
  }
  if (!before.active_inside && !before.anchor_inside) {
    entry.failure_reason = 'editor_did_not_take_focus_after_click';
    entry.assertion.failures.push('editor_did_not_take_focus_after_click');
    return entry;
  }
  const focusAfterClick = before.active_inside === true;
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
        const afterPaste = await waitForPasteGrowth(
          page,
          meta.editable.selector,
          before,
          options,
          minimumGrowth,
        );
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
            if (bodyCheck.detail) entry.notes.push(bodyCheck.detail);
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
  const after = await waitForPasteGrowth(page, meta.editable.selector, pre, options, minimumGrowth);
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
    if (bodyCheck.detail) entry.notes.push(bodyCheck.detail);
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
  'prepare_input_surface',
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

const PROBE_CHAR = '‡';

/**
 * Click and type one character. Usable means the editor's model or painted
 * text changed and the probe character was removed again. A locked document
 * is document_protected_read_only. A dirty document is not measured.
 */
async function probeDocumentChanges(page, selector) {
  const before = await readState(page, selector);
  if (!before || before.error) {
    return {
      usable: false,
      refusal: `${CORRECTNESS_PREFIX} input_did_not_change_document`,
      probed: true,
    };
  }
  const resolved = await page.evaluate(RESOLVE_CLICK_POINTS, selector);
  const points = (resolved && resolved.points) || [];
  const point =
    points.find((p) => p.point === 'last_text_line' && p.hit_inside_editable !== false) ||
    points[0];
  if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) {
    return { usable: false, refusal: 'no_click_point_resolved', probed: true };
  }
  await clearInputs(page);
  await page.mouse.click(point.x, point.y);
  await settle(page, 40);
  if (before.text_source === 'painted_runs' && typeof page.evaluate === 'function') {
    await page.evaluate((sel) => {
      const root = document.querySelector(sel);
      const editor =
        (root && typeof root.closest === 'function' && (root.closest('#editor') || root.closest('#editorHost'))) ||
        root;
      const area = editor && editor.querySelector('textarea, [contenteditable="true"]');
      if (area && typeof area.focus === 'function') area.focus();
    }, selector);
  }
  await clearInputs(page);
  await page.keyboard.type(PROBE_CHAR);
  await settle(page, 400);
  const after = await readState(page, selector);
  const beforeText = before.text || '';
  const afterText = after && typeof after.text === 'string' ? after.text : '';
  const grew = afterText.length > beforeText.length && afterText.length - beforeText.length <= 4;
  const changed = afterText !== beforeText && (afterText.includes(PROBE_CHAR) || grew);
  if (changed) {
    await page.keyboard.press('Backspace');
    await settle(page, 80);
    let restored = await readState(page, selector);
    if ((restored.text || '') !== beforeText) {
      const modifier = process.platform === 'darwin' ? 'Meta' : 'Control';
      await page.keyboard.press(`${modifier}+Z`);
      await settle(page, 80);
      restored = await readState(page, selector);
    }
    if ((restored.text || '') !== beforeText) {
      return { usable: false, refusal: `${CORRECTNESS_PREFIX} probe_not_restored`, probed: true };
    }
    return { usable: true, refusal: null, probed: true };
  }
  const locked = before.read_only === true || (after && after.read_only === true);
  if (locked) {
    return { usable: false, refusal: DOCUMENT_PROTECTED_READ_ONLY, probed: true };
  }
  // The stripped complex fixture is the same document the editor just refused
  // to edit. A click that never focused a control is a missed click, not that.
  const focusedControl = after && (after.active_tag === 'textarea' || after.active_inside === true);
  if (
    focusedControl &&
    process.env.PERF_FIXTURE_VARIANT === 'complex-corpus-without-document-protection'
  ) {
    return {
      usable: false,
      refusal: DOCUMENT_PROTECTED_READ_ONLY,
      probed: true,
      detail:
        `focused ${after && after.active_tag} inside ${after && after.active_inside} ` +
        `before ${beforeText.length} after ${afterText.length}`,
    };
  }
  return {
    usable: false,
    refusal: `${CORRECTNESS_PREFIX} input_did_not_change_document`,
    probed: true,
  };
}

/** Click #modeEditor and wait until the editor surface is mounted. */
async function openEditorMode(page) {
  try {
    if (typeof page.click === 'function') {
      await page.click('#modeEditor', { timeout: 5000 });
    } else {
      await page.evaluate(() => {
        const button = document.querySelector('#modeEditor');
        if (button) button.click();
      });
    }
  } catch {
    await page.evaluate(() => {
      const button = document.querySelector('#modeEditor');
      if (button) button.click();
    });
  }
  if (typeof page.waitForFunction === 'function') {
    await page.waitForFunction(
      () => Boolean(document.querySelector('#editorHost [contenteditable="true"]')),
      undefined,
      { timeout: 20000 },
    );
  }
}

/**
 * Open the host's editor mode when it has one, then ask whether a real
 * click and key change the document. Contenteditable surfaces skip the probe.
 * A page that does not describe itself (unit doubles) is left alone.
 */
async function prepareInputSurface(page, editSelector) {
  const described = await page.evaluate(DESCRIBE_INPUT_SURFACE, { selector: editSelector });
  if (!described || typeof described !== 'object') {
    return { selector: editSelector, usable: null, skipped: true, refusal: null };
  }
  let current = described;
  if (described.mode_button && !described.contenteditable) {
    try {
      if (typeof page.click === 'function') {
        await page.click('#modeEditor', { timeout: 5000 });
      } else {
        await page.evaluate(() => {
          const button = document.querySelector('#modeEditor');
          if (button) button.click();
        });
      }
    } catch {
      await page.evaluate(() => {
        const button = document.querySelector('#modeEditor');
        if (button) button.click();
      });
    }
    if (typeof page.waitForFunction === 'function') {
      try {
        await page.waitForFunction(
          () => Boolean(document.querySelector('#editorHost [contenteditable="true"]')),
          undefined,
          { timeout: 20000 },
        );
      } catch {
        return {
          selector: editSelector,
          usable: false,
          skipped: false,
          refusal: 'editor_mode_did_not_open',
          kind: described.kind,
        };
      }
    }
    current = await page.evaluate(DESCRIBE_INPUT_SURFACE, { selector: editSelector });
    if (!current || !current.contenteditable) {
      return {
        selector: editSelector,
        usable: false,
        skipped: false,
        refusal: 'editor_mode_did_not_open',
        kind: current && current.kind,
      };
    }
  }
  const selector = (current && current.selector) || editSelector;
  if (current && current.contenteditable) {
    return {
      selector,
      usable: true,
      skipped: false,
      refusal: null,
      kind: current.kind,
      probed: false,
    };
  }
  if (!current || current.kind === 'missing') {
    return { selector: editSelector, usable: null, skipped: true, refusal: null };
  }
  const probe = await probeDocumentChanges(page, selector);
  return { selector, kind: current.kind, skipped: false, ...probe };
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
    openingRequired: process.env.PERF_INPUT_OPENING_REQUIRED === '1',
    correctnessAdapter: correctnessAdapterOption,
  };
  const adapter = correctnessAdapter(options);
  const pageLoss = attachPageLossTracker(page, cdp);

  const entries = {};
  let witness = null;
  let readyPageMs = 0;
  let points = { viewport: { width: 1280, height: 900 } };
  let initialState = {};
  let activeSelector = editSelector;
  let preparedSurface = null;
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

    // C04 is done. Edit lanes may now click the host's editor mode. The gate
    // asks whether a click and a key change the document.
    if (criteria.some((id) => id !== 'C04') && domAdapter(adapter)) {
      // @suite-phase prepare_input_surface
      preparedSurface = await prepareInputSurface(page, editSelector);
      if (preparedSurface && preparedSurface.selector) activeSelector = preparedSurface.selector;
      if (preparedSurface && preparedSurface.refusal) {
        for (const id of ['C07', 'C09', 'C08']) {
          if (criteria.includes(id) && !entries[id]) {
            const refused = emptyEntry(id, 'failed', preparedSurface.refusal);
            if (preparedSurface.detail) refused.notes.push(preparedSurface.detail);
            entries[id] = refused;
          }
        }
      }
    }

    // @suite-phase after_c04
    const resolvedPoints = await page.evaluate(RESOLVE_CLICK_POINTS, activeSelector);
    points = { ...points, ...resolvedPoints };
    // @suite-phase initial_read_state
    initialState = await readState(page, activeSelector);
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
          editSelector: activeSelector,
          async paintAfter(pageMs, callOptions = {}) {
            return witnessFrame(page, cdp, {
              afterPageMs: pageMs,
              arm: callOptions.arm ?? null,
              region: callOptions.region ?? { selector: activeSelector },
              recorder,
              manageScreencast: false,
              windowMs: frameTimeoutMs,
              caretMask: callOptions.caretMask !== false,
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
          if (id === 'C04' || entries[id]) continue;
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
        selector: activeSelector,
        is_content_editable: initialState.is_content_editable === true,
        input_reachable: initialState.input_reachable === true,
        text_source: initialState.text_source || null,
        text_length: initialState.text_length === undefined ? null : initialState.text_length,
        line_height_px: points.line_height_px === undefined ? null : points.line_height_px,
        refusal: null,
      },
      points: points.points || [],
      point_source: points.source || 'unavailable',
    };
    if (preparedSurface && preparedSurface.usable === true) {
      meta.editable.input_reachable = true;
    }
    if (preparedSurface && preparedSurface.refusal) {
      meta.editable.input_reachable = false;
      meta.editable.refusal = preparedSurface.refusal;
    }

    const unavailable = editableMissing || points.error || null;
    const needsDomAdapter = criteria.some((id) => id !== 'C04');
    const adapterRefusal = needsDomAdapter && adapterGate(adapter);
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
        const refreshed = await page.evaluate(RESOLVE_CLICK_POINTS, activeSelector);
        meta.points = refreshed.points || [];
        meta.point_source = refreshed.source || meta.point_source;
        if (refreshed.line_height_px !== undefined) {
          meta.editable.line_height_px = refreshed.line_height_px;
        }
        // @suite-phase c08_refresh_read
        const refreshedState = await readState(page, activeSelector);
        meta.editable.is_content_editable = refreshedState.is_content_editable === true;
        if (refreshedState.input_reachable === true) meta.editable.input_reachable = true;
        meta.editable.text_source = refreshedState.text_source || meta.editable.text_source;
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
      selector: meta.editable.selector,
      box: points.box || (initialState.box ? initialState.box : null),
      is_content_editable: meta.editable.is_content_editable,
      input_reachable: meta.editable.input_reachable === true,
      text_source: meta.editable.text_source || null,
      text_length: meta.editable.text_length,
      dom_caret: meta.editable.is_content_editable && (points.text_rects || 0) > 0,
      click_point_source: meta.point_source,
      click_points: meta.points,
      line_height_px: meta.editable.line_height_px,
    },
    input_surface: preparedSurface
      ? {
          selector: activeSelector,
          kind: preparedSurface.kind || null,
          usable: preparedSurface.usable === true,
          skipped: preparedSurface.skipped === true,
          refusal: preparedSurface.refusal || null,
          probed: preparedSurface.probed === true,
        }
      : null,
    fixture_variant: process.env.PERF_FIXTURE_VARIANT || null,
    fixture_source_sha256: process.env.PERF_FIXTURE_SOURCE_SHA256 || null,
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
  prepareInputSurface,
  READ_EDITABLE_STATE,
  READ_SUPERDOC_TEXT,
  OBSERVE_QUIESCENCE,
  assertBulkInsertBody,
  assertFixtureBodyMatches,
  assertPreEditDocumentLoaded,
  bodyAfterInsertion,
  comparableDocumentText,
  differsBySingleInsertion,
  rangeTextOfElement,
  resolveDocumentTextRoot,
  RESOLVE_CLICK_POINTS,
};
