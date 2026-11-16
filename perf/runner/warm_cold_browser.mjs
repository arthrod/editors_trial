/**
 * Paired warm/cold browser probes for the perf harness.
 *
 * Usage (from repo root, with a dev server already listening):
 *   node perf/runner/warm_cold_browser.mjs \
 *     --driver playwright \
 *     --url http://127.0.0.1:5208/ \
 *     --corpus /abs/fixture.docx \
 *     --corpus-route /corpus.docx \
 *     --ready-selector ".status-ok" \
 *     --edit-selector "[data-slate-editor='true']" \
 *     --pairs 3
 *
 * Criteria mode (no warm/cold pairs, one page load, see criteria_input.mjs):
 *
 *   node perf/runner/warm_cold_browser.mjs \
 *     --driver playwright --editor plate --criteria C04,C07,C09,C08 \
 *     --url http://127.0.0.1:5208/ --corpus /abs/corpus.docx \
 *     --corpus-route /corpus.docx --ready-selector ".status-ok" \
 *     --edit-selector '[contenteditable="true"]'
 *
 * Optional: --frame-timeout, --quiescence-ms, --quiescence-timeout,
 * --bulk-chars. The payload goes to stdout.
 */
import fs from 'node:fs';
import {
  loadPlaywright,
  clockSkew,
  witnessFrame,
  stopRecorder,
  captureBaseline,
  decodePng,
  diffRatio,
  DEFAULT_CHANNEL_TOLERANCE,
  DEFAULT_MIN_PIXELS,
  frameAckSettled,
} from './witness.mjs';
import { startChromeTrace, stopChromeTrace } from './chrome_trace.mjs';

function convertFrameToPageMs(frame, clock) {
  const kind = clock.timestamp_kind || 'epoch_seconds';
  if (kind === 'epoch_seconds') {
    if (typeof frame.ts !== 'number') return null;
    return frame.ts * 1000 - clock.time_origin_ms;
  }
  if (kind === 'monotonic_seconds') {
    const value = typeof frame.mono === 'number' ? frame.mono : frame.ts;
    if (typeof value !== 'number' || typeof clock.monotonic_origin_ms !== 'number') return null;
    return value * 1000 - clock.monotonic_origin_ms;
  }
  return null;
}

function clipRectToDocument(rect, doc) {
  const x = Math.max(rect.x, doc.x);
  const y = Math.max(rect.y, doc.y);
  const right = Math.min(rect.x + rect.width, doc.x + doc.width);
  const bottom = Math.min(rect.y + rect.height, doc.y + doc.height);
  if (right <= x || bottom <= y) return null;
  return { x, y, width: right - x, height: bottom - y };
}

function rectDamageVsBaseline(baselinePixels, framePixels, rects, dpr, doc, tolerance) {
  return rects.map(rect => {
    const clipped = clipRectToDocument(rect, doc);
    if (!clipped) return { rect, changed_pixels: 0 };
    const region = {
      x: clipped.x * dpr,
      y: clipped.y * dpr,
      width: clipped.width * dpr,
      height: clipped.height * dpr,
    };
    const diff = diffRatio(baselinePixels, framePixels, { channelTolerance: tolerance, region });
    return { rect, changed_pixels: diff.comparable ? diff.changed : 0 };
  });
}

import { settleFrames } from './b2_settle.mjs';
import { settlePixels, PIXEL_EDIT_MIN_PIXELS, PIXEL_GLYPH_MIN_PIXELS } from './pixel_settle.mjs';

/** #245: half the height, in CSS pixels, of the band around the caret's click point in which the pixel
 * witness looks for the typed character: one line of body text with room for a larger font. */
const PIXEL_CARET_BAND_CSS_PX = 24;
/** The longest a painted frame is taken to need to reach the recorder: the quiet is read up to now less this. */
const PIXEL_FRAME_DELIVERY_MS = 250;
/** How far right of the caret's input a typed character may begin and still be the edit at the caret. */
const PIXEL_CARET_REACH_CSS_PX = 48;
/** The least the caret's input must move right on its line for a typed character to lie between its two places. */
const PIXEL_CARET_MIN_ADVANCE_CSS_PX = 3;
/** A focused input no larger than this is the editor's keyboard input kept at the caret (Docen 1x1, canvas-editor
 * 100x30), not a text box laid over the page. */
const PIXEL_CARET_INPUT_MAX_CSS_PX = {width: 120, height: 72};
/** The corner of the page the harness's own marks occupy (witness.mjs: an 8x8 anchor, a 4x4 outlined mark). */
const HARNESS_MARK_CSS_PX = 10;
import { loadTimeoutMs } from './load_timeout.mjs';
import { createRegionClassifier } from './b2_pixels.mjs';

import {
  CRITERIA_SCHEMA,
  parseCriteriaList,
  runCriteriaSuite,
  waitForUsableSurface,
} from './criteria_input.mjs';
import { editSurface, hasCaretAdapter, readAndGateDocumentText, usableExpression } from './edit_surface.mjs';
import { confirmLaneEdit, prepareLaneCaret } from './lane_edit_burst.mjs';

/** Light-DOM box for screencast witness when the edit target is model or shadow. */
function witnessRegion(editorId, fallbackSelector) {
  if (editorId === 'canvas') return { selector: '#editor .ce-page-container' };
  if (editorId === 'docen') return { selector: 'docen-document' };
  if (editorId === 'eigenpal') return { selector: '.docx-page[data-materialized="true"]' };
  return { selector: fallbackSelector };
}

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

const driver = opt.driver || 'playwright';
const url = opt.url;
const corpusFile = opt.corpus;
const corpusRoute = opt['corpus-route'] || '/corpus.docx';
const readySelector = opt['ready-selector'] || '.status-ok';
const readyText = opt['ready-text'] || '';
const readyJs = opt['ready-js'] || '';
const editSelector = opt['edit-selector'] || '[contenteditable="true"]';
const preEditClick = opt['pre-edit-click'] || '';
const skipEdit = opt['skip-edit'] === 'true' || opt['skip-edit'] === true;
const pairs = Math.max(1, Number(opt.pairs || 3));
const sampleRoute = opt['sample-route'] || corpusRoute;
const waitAfterReadyMs = Number(opt['wait-after-ready'] || 0);
const editorId = typeof opt.editor === 'string' ? opt.editor : null;
const frameTimeoutMs = Number(opt['frame-timeout'] || 2000);
const quiescenceMs = opt['quiescence-ms'] !== undefined ? Number(opt['quiescence-ms']) : 300;
const settleMaxWaitMs = opt['settle-max-wait-ms'] !== undefined ? Number(opt['settle-max-wait-ms']) : 3000;
const quiescenceTimeoutMs = Number(opt['quiescence-timeout'] || 10_000);
const bulkChars = Number(opt['bulk-chars'] || 1500);
const expectedOpeningText = typeof opt['expected-opening-text'] === 'string' ? opt['expected-opening-text'] : '';
const expectedClosingSentinel =
  typeof opt['expected-closing-sentinel'] === 'string' ? opt['expected-closing-sentinel'] : '';
// r3lanes4 ruling 5b: the fixture body the way the input lane passes it.
const expectedBodyText = (() => {
  const path = process.env.PERF_EXPECTED_BODY_PATH;
  try {
    if (typeof path === 'string' && path && fs.existsSync(path)) {
      return fs.readFileSync(path, 'utf8');
    }
  } catch {
    return null;
  }
  return null;
})();
const fixtureTextChars = Number(opt['fixture-text-chars'] || 0);
const lengthCheckMode = typeof opt['length-check-mode'] === 'string' ? opt['length-check-mode'] : null;
// #196: the select_all_copy oracle's clipboard bound; document_probe uses the
// same --c14-copy-wait-ms flag name.
const copyWaitMs = opt['c14-copy-wait-ms'] !== undefined ? Number(opt['c14-copy-wait-ms']) : null;
const errorJs = typeof opt['error-js'] === 'string' ? opt['error-js'] : '';
let criteriaList = [];
if (opt.criteria !== undefined) {
  try {
    criteriaList = parseCriteriaList(opt.criteria);
  } catch (err) {
    console.error(`warm_cold_browser: ${err.message}`);
    process.exit(2);
  }
  if (criteriaList.length === 0) {
    console.error('warm_cold_browser: --criteria named no criterion');
    process.exit(2);
  }
}

if (!url || !corpusFile) {
  console.error('warm_cold_browser: --url and --corpus are required');
  process.exit(2);
}

const corpusBytes = fs.readFileSync(corpusFile);

const loadTimeout = loadTimeoutMs();

async function awaitReadySignal(page, selector, timeoutMs) {
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
        // Canvas boot stores the import failure here and never sets __DOCX_IMPORTED__.
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
  } else if (readyText) {
    await page.waitForFunction(
      ({ sel, text }) => {
        const el = document.querySelector(sel);
        return Boolean(el && el.textContent && el.textContent.includes(text));
      },
      { sel: selector, text: readyText },
      { timeout: timeoutMs },
    );
  } else {
    await page.waitForSelector(selector, { timeout: timeoutMs, state: 'visible' });
  }
}

async function waitForReady(page, selector, timeoutMs = loadTimeout, t0 = Date.now(), { noCopy = false } = {}) {
  await awaitReadySignal(page, selector, timeoutMs);
  const first_usable_ms = Date.now() - t0;
  const settleStart = Date.now();
  if (waitAfterReadyMs > 0) {
    await page.waitForTimeout(waitAfterReadyMs);
  }
  const settle_ms = Date.now() - settleStart;
  const calibration = await page.context().newCDPSession(page);
  const clock_skew = await clockSkew(page, calibration);
  await stopRecorder(calibration);
  await calibration.detach();
  const content_check = await verifyCanvasOpening(page, { noCopy });
  return { first_usable_ms, settle_ms, clock_skew, content_check };
}

async function verifyCanvasOpening(page, { noCopy = false } = {}) {
  if (!expectedOpeningText) {
    return { content_verified: true, surface_reason: null, skipped: true };
  }
  if (!editorId) {
    return { content_verified: false, surface_reason: 'document_content_unverifiable', skipped: false };
  }
  // A ready signal that fired on the loading shell leaves the document
  // mounting while this one-shot read runs (#168). The same rule as the
  // input suite: return only when this editor's usableExpression is true.
  // At the bound the named refusal is the content refusal. Do not fall
  // through to a gate verdict on a document that never became usable.
  const usableRefusal = await waitForUsableSurface(page, usableExpression(editorId, editSelector));
  if (usableRefusal) {
    return {
      content_verified: false,
      surface_reason: usableRefusal,
      skipped: false,
    };
  }
  const gated = await readAndGateDocumentText(page, editorId, {
    expectedOpening: expectedOpeningText,
    expectedClosing: expectedClosingSentinel,
    fixtureChars: fixtureTextChars,
    lengthCheckMode,
    root: editSelector,
    expectedBody: expectedBodyText,
    copyWaitMs,
    noCopy,
  });
  const { verdict } = gated;
  return {
    content_verified: verdict.content_verified,
    surface_reason: verdict.surface_reason,
    editor_error: gated.error,
    model_oracle: gated.oracle,
    model_source: gated.source,
    document_text_chars: gated.chars,
    // #245: how many of the typed character the document held at ready, for the arm's text count.
    document_token_count: typeof gated.text === 'string' ? (gated.text.match(/x/g) || []).length : null,
    document_text_whole: gated.oracle === 'select_all_copy',
    document_text: gated.text.slice(0, 4000),
    length_check: gated.length_check,
    length_enforced: gated.length_enforced,
    content_check: gated.content_check,
    content_check_reason: gated.content_check_reason,
    model_document_check: gated.modelDocumentCheck,
    dom_document_check: gated.domDocumentCheck,
  };
}

/**
 * #245: confirm an arm's key presses by the text, for an editor whose only adapter is a modified flag.
 *
 * The flag rises once, so it confirms no single key (WordCraft: 40 of 160 in the published runs). After the
 * arm's last key press, and outside every timed interval, the whole text is read with the editor's own
 * select all and copy, as at ready; the count of the typed character must have grown by exactly the number
 * of keys pressed. Then every sample of the arm is confirmed; otherwise none is.
 */
async function confirmArmByText(page, ready, edits) {
  if (!editorId || editSurface(editorId).kind !== 'flag') return;
  const pending = edits.filter(edit => edit?.edit_confirmation?.pending_arm_text_count);
  if (!pending.length) return;
  const pressed = edits.filter(edit => edit?.event_timing?.event?.trusted).length;
  // The ready step's content check holds the whole text it read with the same select all and copy.
  const read = ready?.content_check || {};
  const before = Number.isInteger(read.document_token_count) && read.document_text_whole ? read.document_token_count : null;
  // Without a whole-text read at ready (no content expectation was passed) there is no count to grow from.
  let after = null, error = before === null ? 'no_whole_text_count_at_ready' : null;
  try {
    const { C14_COPY_WAIT_MS, selectAllCopy } = await import('./c14_whole_text.mjs');
    const text = await selectAllCopy(page, editorId, { waitMs: copyWaitMs || C14_COPY_WAIT_MS });
    after = typeof text === 'string' ? (text.match(/x/g) || []).length : null;
  } catch (err) {
    error = String(err && err.message ? err.message : err).slice(0, 200);
  }
  const delta = before !== null && after !== null ? after - before : null;
  const confirmed = delta !== null && pressed === edits.length && delta === pressed;
  for (const edit of pending) {
    edit.edit_confirmation.flag_adapter = edit.edit_confirmation.adapter;
    edit.edit_confirmation.adapter = { adapter: 'text_count', confirmed, before_count: before, after_count: after,
      text_delta: delta, expected_delta: pressed, keys_in_arm: edits.length, error };
    edit.edit_confirmation.pending_arm_text_count = false;
    edit.edit_confirmation.confirmed = confirmed;
    if (!confirmed && edit.outcome === 'measured') {
      edit.outcome = 'failed';
      edit.failure_reason = 'expected_edit_not_confirmed';
      edit.edit_ms = null;
    }
  }
}

async function performEdit(page, selector, cdp) {
  try {
    return await measureEdit(page, selector, cdp);
  } catch (error) {
    return { mechanism: 'cdp_screencast_changed_frame', outcome: 'failed',
      edit_ms: null, paint_ms: null, failure_reason: 'input_probe_error: ' + String(error.message || error) };
  } finally {
    await page.evaluate(() => {
      clearInterval(window.__b2?.pulseTimer);
      window.__b2?.pulse?.remove();
      window.__b2?.observer?.disconnect();
      window.__b2?.mutationObserver?.disconnect();
      if (window.__b2?.onKey) window.removeEventListener('keydown', window.__b2.onKey, true);
    }).catch(() => {}); // A navigation may already have destroyed the context.
    await stopRecorder(cdp);
  }
}

/** The focused element's box, through shadow roots: a canvas editor keeps its keyboard input at the caret. */
function readFocusedInput(page) {
  return page.evaluate(() => {
    let el = document.activeElement;
    while (el && el.shadowRoot && el.shadowRoot.activeElement) el = el.shadowRoot.activeElement;
    if (!el || el === document.body || el === document.documentElement) return null;
    const r = el.getBoundingClientRect();
    return {tag: el.tagName, x: r.x, y: r.y, width: r.width, height: r.height};
  }).catch(() => null);
}

async function measureEdit(page, selector, cdp) {
  // Focus/actionability and witness calibration are preconditioning, outside
  // the event-to-frame interval. No typing delay is introduced.
  const adapterSurface = hasCaretAdapter(editorId) ? editSurface(editorId) : null;
  // Not 'dom': the editors that draw their text on a canvas (canvas-editor, Docen: model; WordCraft: flag).
  // edit_surface.mjs EDIT_SURFACES gives every editor with glyph outlines kind 'dom'.
  const modelOrFlagEdit = adapterSurface && adapterSurface.kind !== 'dom';
  // #245, criterion 4: in a shakedown the settled-pixel witness is also read, as a shadow, for the editors that
  // have glyph outlines, so that the two witnesses can be compared on the same key press. A shadow never
  // changes a sample, and it is never read in a publication run.
  const pixelShadow = !modelOrFlagEdit && process.env.PERF_SHAKEDOWN === '1';
  let lanePrepared = null;
  if (hasCaretAdapter(editorId)) {
    lanePrepared = await prepareLaneCaret(page, editorId, selector);
    if (lanePrepared.placeError) throw new Error(lanePrepared.placeError);
  } else {
    if (preEditClick) await page.click(preEditClick, { timeout: 30_000 });
    await page.locator(selector).first().click({ timeout: 30_000 });
  }
  // #245: where the caret is. A canvas editor keeps its own focused input (a textarea a pixel or two wide,
  // for the keyboard and input methods) at the caret, and that is the caret's line even when the lane moved
  // the caret after its click (Docen: to the start of the paragraph, 200 pixels above the click). Without
  // such an input the caret is on the line the lane clicked: its text line, or the middle of the declared
  // surface, which is where Playwright's click lands.
  let caretPoint = null;
  let focusedInput = null;
  if (modelOrFlagEdit || pixelShadow) {
    const innerSize = page.viewportSize() || {width: Infinity, height: Infinity};
    focusedInput = await readFocusedInput(page);
    const caretSized = focusedInput && ['TEXTAREA', 'INPUT'].includes(focusedInput.tag)
      && focusedInput.width <= PIXEL_CARET_INPUT_MAX_CSS_PX.width && focusedInput.height <= PIXEL_CARET_INPUT_MAX_CSS_PX.height
      && focusedInput.x >= 0 && focusedInput.y >= 0 && focusedInput.x <= innerSize.width && focusedInput.y <= innerSize.height;
    if (caretSized) {
      caretPoint = {x: focusedInput.x, y: focusedInput.y + focusedInput.height / 2, source: 'focused_input'};
    } else if (lanePrepared?.point && Number.isFinite(lanePrepared.point.y)) {
      caretPoint = {x: lanePrepared.point.x, y: lanePrepared.point.y, source: 'clicked_text_line'};
    } else {
      const box = await page.locator(selector).first().boundingBox().catch(() => null);
      if (box) caretPoint = {x: box.x + box.width / 2, y: box.y + box.height / 2, source: 'centre_of_clicked_surface'};
    }
  }
  const skew = await clockSkew(page, cdp);
  const mechanism = 'cdp_screencast_changed_frame';
  if (!skew.acceptable) return {
    mechanism, clock_skew: skew, outcome: 'failed', edit_ms: null,
    failure_reason: skew.reason || 'clock_check_not_acceptable',
  };
  await page.evaluate(selector => {
    const documentElement = document.querySelector(selector);
    // The edit confirmation follows the live document, never the arm-time
    // elements: Eigenpal re-creates the edited paragraph, so the arm-time
    // first match is detached while the typed x lands in the new first
    // matching element (HF e2-docsplus 20261111T005304106862Z-...-091 cell
    // 0004-eigenpal: before_count 0, after_count 1, mutations 0), and a
    // selector can legitimately match many document fragments. Counts, the
    // observer scope and the visibility clip are computed against every
    // element matching the selector at the moment they are needed.
    const matches = () => (selector ? [...document.querySelectorAll(selector)] : []);
    const count = () => matches().reduce((n, el) => n + ((el.textContent || '').match(/x/g) || []).length, 0);
    const inDocument = node => matches().some(el => el.contains(node));
    const before = count();
    window.__b2 = { event: null, entries: [], supported: PerformanceObserver.supportedEntryTypes.includes('event') };
    const state = window.__b2;
    // Arm only after dispatching the key: never alter the pre-key baseline
    // or delay dispatch. Dense delivery must also witness short delayed
    // reveals before witnessFrame returns.
    state.startPulse = () => {
      if (!documentElement) return;
      const box = documentElement.getBoundingClientRect();
      const corner = [[innerWidth-4,innerHeight-4],[0,innerHeight-4],[innerWidth-4,0],[0,0]]
        .find(([x,y]) => x+3<=box.left || x>=box.right || y+3<=box.top || y>=box.bottom);
      if (corner) {
        const pulse = document.createElement('div');
        pulse.style.cssText = `position:fixed;left:${corner[0]}px;top:${corner[1]}px;width:3px;height:3px;pointer-events:none;z-index:2147483647`;
        document.body.appendChild(pulse);
        let phase = false;
        state.pulse = pulse;
        const tick = () => {phase=!phase;pulse.style.background=phase?'#00f':'#0f0';};
        tick();
        state.pulseTimer = setInterval(tick,16);
      }
    };
    const intersect = (a, b) => {
      const x = Math.max(a.x, b.x), y = Math.max(a.y, b.y);
      const right = Math.min(a.x + a.width, b.x + b.width);
      const bottom = Math.min(a.y + a.height, b.y + b.height);
      return right > x && bottom > y ? {x, y, width: right-x, height: bottom-y} : null;
    };
    const textNodes = root => {
      if (root.nodeType === Node.TEXT_NODE) return [root];
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      return nodes;
    };
    const priorText = new WeakMap(matches().flatMap(el => textNodes(el)).map(n => [n, n.data]));
    state.edit_confirmation = {confirmed: false, before_count: before, expected: 'x', mutations: []};
    const visibleRects = (node, start, end) => {
      const parent = node.parentElement;
      if (!parent || !inDocument(node) ||
          !parent.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return [];
      let scope = null;
      for (let el = parent; el; el = el.parentElement) if (el.matches(selector)) { scope = el; break; }
      if (!scope) return [];
      let clip = intersect(scope.getBoundingClientRect(),
        {x: 0, y: 0, width: innerWidth, height: innerHeight});
      for (let el = parent; el && clip; el = el.parentElement) {
        const css = getComputedStyle(el);
        // Complex clipping/masks cannot be proven from bounding rectangles.
        if (css.display === 'none' || css.visibility !== 'visible' || Number(css.opacity) === 0 ||
            css.clipPath !== 'none' || css.clip !== 'auto' || css.maskImage !== 'none') return [];
        const box = el.getBoundingClientRect();
        const overflowX = ['hidden', 'clip', 'scroll', 'auto'].includes(css.overflowX);
        const overflowY = ['hidden', 'clip', 'scroll', 'auto'].includes(css.overflowY);
        if (overflowX || overflowY) clip = intersect(clip, {
          x: overflowX ? box.x + el.clientLeft : clip.x,
          y: overflowY ? box.y + el.clientTop : clip.y,
          width: overflowX ? el.clientWidth : clip.width,
          height: overflowY ? el.clientHeight : clip.height,
        });
      }
      if (!clip) return [];
      const range = document.createRange();
      range.setStart(node, start); range.setEnd(node, end);
      return [...range.getClientRects()].map(r => intersect(r, clip)).filter(Boolean);
    };
    state.insertions = [];
    state.confirmInsertion = insertion => {
      const current = insertion.ranges.flatMap(([start, end]) =>
        insertion.node.data.slice(start, end) === 'x'
          ? visibleRects(insertion.node, start, end) : []);
      // A later reveal/move cannot validate an earlier snapshot, nor can a
      // node hidden or detached since mutation delivery remain confirmed.
      return JSON.stringify(current) === JSON.stringify(insertion.proof.visible_rects) ? current : [];
    };
    state.mutationObserver = new MutationObserver(records => {
      if (!state.event?.trusted) return;
      const nodes = new Set(records.flatMap(record => record.type === 'characterData'
        ? [record.target] : [...record.addedNodes].flatMap(textNodes)));
      for (const node of nodes) {
        if (!inDocument(node)) continue;
        const old = priorText.get(node) || '', text = node.data;
        priorText.set(node, text);
        if ((text.match(/x/g) || []).length <= (old.match(/x/g) || []).length) continue;
        let start = 0, end = text.length, oldEnd = old.length;
        while (start < old.length && start < text.length && old[start] === text[start]) start++;
        while (oldEnd > start && end > start && old[oldEnd-1] === text[end-1]) { oldEnd--; end--; }
        const rects = [], ranges = [];
        for (let i = start; i < end; i++) {
          if (text[i] === 'x') {
            ranges.push([i, i+1]);
            rects.push(...visibleRects(node, i, i+1));
          }
        }
        const proof = {mutation_page_ms: performance.now(), visible_rects: rects};
        state.edit_confirmation.mutations.push(proof);
        state.insertions.push({node, ranges, proof});
      }
    });
    state.mutationObserver.observe(document.body, {subtree: true, childList: true, characterData: true});
    state.onKey = function onKey(e) {
      if (e.key !== 'x') return;
      window.__b2.event = { startTime: e.timeStamp, trusted: e.isTrusted };
      window.removeEventListener('keydown', onKey, true);
    };
    window.addEventListener('keydown', state.onKey, true);
    if (window.__b2.supported) {
      window.__b2.observer = new PerformanceObserver(list => {
        window.__b2.entries.push(...list.getEntries().map(e => ({
          name:e.name, startTime:e.startTime, duration:e.duration, interactionId:e.interactionId,
          processingEnd:e.processingEnd
        })));
        window.__b2.notify?.();
      });
      window.__b2.observer.observe({type:'event', durationThreshold:16});
    }
  }, selector);
  const baseline = await captureBaseline(page, cdp);
  let armWaitedMs = 0; // how long the arm really waited after the key press, with the recorder running
  const frame = await witnessFrame(page, cdp, {
    baseline: baseline.frame,
    windowMs: Math.max(500, frameTimeoutMs), clockCheck: skew,
    region: witnessRegion(editorId, selector),
    arm: async () => {
      if (modelOrFlagEdit) {
        await page.keyboard.press('x', { delay: 0 });
      } else {
        await cdp.send('Input.dispatchKeyEvent', {type:'keyDown', key:'x', code:'KeyX', text:'x', windowsVirtualKeyCode:88});
        await cdp.send('Input.dispatchKeyEvent', {type:'keyUp', key:'x', code:'KeyX', windowsVirtualKeyCode:88});
      }
      const event = await page.evaluate(() => {
        window.__b2.startPulse();
        const state=window.__b2;
        return {...state.event, unconfirmable:state.insertions.length>0 &&
          state.insertions.every(insertion=>insertion.proof.visible_rects.length===0)};
      });
      if (!event?.trusted) throw new Error('trusted keydown not observed');
      // Acquire the bounded witness sequence before B1's synchronous PNG
      // reader runs. Otherwise that reader can starve acknowledgements while
      // a delayed glyph is still pending. The timestamp window remains W.
      // Empty insertion proofs cannot later pass confirmInsertion's fixed
      // geometry check, so there is no settlement window to establish.
      // A canvas editor is always waited for: its edit is read from the frames of this window (#245).
      if (modelOrFlagEdit || !event.unconfirmable) {
        const waitStarted = Date.now();
        await page.waitForTimeout(settleMaxWaitMs);
        armWaitedMs = Date.now() - waitStarted;
      }
      await page.evaluate(() => clearInterval(window.__b2?.pulseTimer));
      return event.startTime;
    },
  });
  // Check the document before waiting for Event Timing delivery. A later edit
  // cannot retroactively turn an earlier caret frame into the edit's paint —
  // but MutationObserver delivery can lag the DOM change by the editor's
  // whole processing time (superdoc on HF: witness frame 6355.9 ms, delivery
  // stamp 6586.3 ms for one keydown), so the delivery timestamp is an upper
  // bound on the mutation time, never the mutation time, and must not gate
  // an insertion against the witnessed frame. Causality is proven where it
  // is measured: the settle classifier requires this insertion's own ink,
  // against the pre-key baseline, in frames at or after the input.
  const confirmation = await page.evaluate(({selector, frameTime}) => {
    const state = window.__b2;
    const proof = state.edit_confirmation;
    const nodes = selector ? [...document.querySelectorAll(selector)] : [];
    const after = nodes.reduce((n, el) => n + ((el.textContent || '').match(/x/g) || []).length, 0);
    const eligible = frameTime !== null ? state.insertions : [];
    return {...proof, after_count: after, confirmed: false,
      visible_rects: eligible.flatMap(state.confirmInsertion), changed_pixels: 0};
  }, {selector, frameTime: frame.frame_page_ms});
  if (editorId && lanePrepared) {
    const adapter = await confirmLaneEdit(page, editorId, lanePrepared.point, {
      token: 'x',
      before: lanePrepared.beforeText,
      beforeFlag: lanePrepared.beforeFlag,
      expected: 1,
    });
    confirmation.adapter = adapter;
    if (adapter.confirmed) {
      confirmation.confirmed = true;
      confirmation.after_count = Math.max(confirmation.after_count || 0, adapter.after_count || 1);
    }
  }
  let confirmationFramePageMs = frame.frame_page_ms;
  confirmation.settled_channel_tolerance = DEFAULT_CHANNEL_TOLERANCE;
  confirmation.settled_quiescence_ms = quiescenceMs;
  confirmation.settle_max_wait_ms = settleMaxWaitMs;
  confirmation.frame_collection = 'before_document_witness_decode';
  let settleFailure = null;
  const beforeShadow = pixelShadow ? {settleFailure, confirmationFramePageMs, changed: confirmation.changed_pixels,
    witness: confirmation.witness_page_ms, settled: confirmation.settled_page_ms} : null;
  let shadowError = null;
  if ((modelOrFlagEdit || pixelShadow) && baseline.frame) {
   try {
    // #245: an editor that draws its text on a canvas has no glyph rects, and
    // its own caret blink is often the first changed frame. The end event is
    // the first frame in which the settled picture of the edit is in place
    // (pixel_settle.mjs). Everything here runs after the window has elapsed
    // inside arm(); it extends no timed interval.
    const event = await page.evaluate(() => window.__b2?.event);
    const recorder = baseline.recorder;
    const clock = {
      time_origin_ms: frame.time_origin_ms,
      timestamp_kind: frame.timestamp_kind,
      monotonic_origin_ms: skew.monotonic_origin_ms,
    };
    const markerMs = typeof event?.startTime === 'number' ? event.startTime : null;
    if (markerMs === null) {
      settleFailure = 'no_trusted_keydown_time';
    } else if (clock.timestamp_kind === 'monotonic_seconds' && typeof clock.monotonic_origin_ms !== 'number') {
      settleFailure = 'monotonic_origin_missing';
    } else {
      // Where the typed character appears: the line the harness put the caret on. Editors that draw their
      // own toolbar on the same canvas change it on the first edit (WordCraft: a strip at the top, 30 ms
      // after the text), and that is not the character. The band is PIXEL_CARET_BAND_CSS_PX above and below
      // the click point, across the document's whole width; without a click point it is the whole document.
      const documentRect = frame.document_region?.rect_device_px || null;
      const dpr = frame.document_region?.device_pixel_ratio || 1;
      const point = caretPoint;
      let witnessRect = documentRect;
      if (point && documentRect) {
        const top = Math.max(documentRect.y, Math.floor((point.y - PIXEL_CARET_BAND_CSS_PX) * dpr));
        const bottom = Math.min(documentRect.y + documentRect.height, Math.ceil((point.y + PIXEL_CARET_BAND_CSS_PX) * dpr));
        witnessRect = {x: documentRect.x, y: top, width: documentRect.width, height: Math.max(0, bottom - top)};
      }
      // The caret is not the character. A caret that blinks is masked by its blinking. One that does not
      // (Docen) moves a frame before the character is drawn: 38 pixels, two columns. Where the editor's
      // input moved right on its line with the key, its place before and after gives both columns, and they
      // are left out, so that what is witnessed is what was drawn between and beyond them; the floor is then
      // the glyph's. Where it did not, nothing says where the caret is, and the larger floor applies: more
      // than any caret, so a caret move alone is refused.
      let caretColumns = null;
      let focusedAfter = null;
      if (point?.source === 'focused_input' && witnessRect) {
        focusedAfter = await readFocusedInput(page);
        const followed = focusedAfter && focusedAfter.tag === focusedInput.tag
          && Math.abs(focusedAfter.y - focusedInput.y) < 1
          && focusedAfter.x - focusedInput.x >= PIXEL_CARET_MIN_ADVANCE_CSS_PX;
        if (followed) {
          caretColumns = [focusedInput.x, focusedAfter.x].map(x => ({
            x: Math.floor(x * dpr) - 1, y: witnessRect.y, width: 3, height: witnessRect.height,
          }));
        }
      }
      const minPixels = caretColumns ? PIXEL_GLYPH_MIN_PIXELS : PIXEL_EDIT_MIN_PIXELS;
      // An edit that landed late (Docen at 250,000 words: seconds after the key) has had no time to go quiet
      // when the frame witness returns on its first changed frame. Wait until the full settle window has
      // passed since that frame; then the quiet is read up to the page's own clock, less the time a frame
      // may take to reach the recorder.
      let pageNowMs = await page.evaluate(() => performance.now());
      const firstChangedMs = typeof frame.frame_page_ms === 'number' ? frame.frame_page_ms : null;
      let lateWaitMs = 0;
      if (firstChangedMs !== null && pageNowMs - firstChangedMs < settleMaxWaitMs) {
        lateWaitMs = Math.ceil(settleMaxWaitMs - (pageNowMs - firstChangedMs));
        await page.waitForTimeout(lateWaitMs);
        pageNowMs = await page.evaluate(() => performance.now());
      }
      // Every frame recorded from the key press on. A slow editor's edit lands after the settle window
      // (Docen at 250,000 words: seconds); the page was unresponsive meanwhile, the recorder was not, and
      // the settled picture is whatever the frames show once they are quiet.
      const candidates = [];
      let unreadFrames = 0;
      for (const candidate of [...recorder.frames]) {
        const pageMs = convertFrameToPageMs(candidate, clock);
        if (pageMs === null || pageMs < markerMs) continue;
        if ((await frameAckSettled(candidate)) !== 'acked' || !candidate.data) {
          // A frame that cannot be read may be the one that shows the edit: no sample, by name, not a crash.
          unreadFrames += 1;
          continue;
        }
        // Decoded on demand: an editor that repaints all the time delivers
        // a couple of hundred frames, too many to hold decoded at once.
        candidates.push({pageMs, seq: candidate.seq, pixels: () => decodePng(Buffer.from(candidate.data, 'base64'))});
      }
      const settled = settlePixels(candidates, {
        baseline: decodePng(Buffer.from(baseline.frame.data, 'base64')),
        markerMs, maxWaitMs: Infinity, quietMs: quiescenceMs,
        // No frame up to now is no change; the arm must really have waited (measured, not assumed).
        quietUntilMs: armWaitedMs > 0 ? pageNowMs - PIXEL_FRAME_DELIVERY_MS : markerMs,
        tolerance: DEFAULT_CHANNEL_TOLERANCE, minPixels,
        region: witnessRect,
        // The clock check's 8x8 anchor and the baseline's 4x4 mark sit at the page's top-left corner.
        exclude: [{x: 0, y: 0, width: Math.ceil(HARNESS_MARK_CSS_PX * dpr), height: Math.ceil(HARNESS_MARK_CSS_PX * dpr)},
          ...(caretColumns || [])],
      });
      const {match_index, reference_index, ...evidence} = settled;
      confirmation.pixel_settle = {
        ...evidence, marker_page_ms: markerMs, min_pixels: minPixels,
        caret_columns_device_px: caretColumns, focused_input_after_css_px: focusedAfter,
        baseline_seq: baseline.frame.seq,
        witness_seq: Number.isInteger(match_index) ? candidates[match_index].seq : null,
        settled_seq: Number.isInteger(reference_index) ? candidates[reference_index].seq : null,
        first_changed_frame_page_ms: frame.frame_page_ms,
        document_rect_device_px: documentRect, witness_rect_device_px: witnessRect,
        caret_point_css_px: point ? {x: point.x, y: point.y} : null, caret_point_source: point ? point.source : null,
        focused_input_css_px: focusedInput,
        excluded_harness_mark_css_px: HARNESS_MARK_CSS_PX,
        caret_band_css_px: point ? PIXEL_CARET_BAND_CSS_PX : null,
        last_frame_page_ms: candidates.length ? Math.max(...candidates.map(c => c.pageMs)) : null,
      };
      // Where the caret is known, the edit must touch it: a change elsewhere on the line's band (a toolbar the
      // editor draws on the same canvas, an input parked away from the caret) is not the typed character.
      let touchesCaret = null;
      if (!settled.failure_reason && point?.source === 'focused_input' && settled.edit_bbox) {
        const left = focusedInput.x * dpr;
        const right = (caretColumns ? focusedAfter.x : focusedInput.x + PIXEL_CARET_REACH_CSS_PX) * dpr;
        const box = settled.edit_bbox;
        touchesCaret = box.x <= right + PIXEL_CARET_REACH_CSS_PX * dpr && box.x + box.width >= left - 4 * dpr;
      }
      confirmation.pixel_settle.edit_touches_caret = touchesCaret;
      confirmation.pixel_settle.unread_frames = unreadFrames;
      confirmation.pixel_settle.arm_waited_ms = armWaitedMs;
      confirmation.pixel_settle.late_wait_ms = lateWaitMs;
      confirmation.pixel_settle.read_until_page_ms = pageNowMs;
      const harnessFailure = unreadFrames ? 'frame_unacknowledged_in_window'
        : touchesCaret === false ? 'pixel_edit_not_at_caret' : null;
      if (settled.failure_reason || harnessFailure) {
        settleFailure = settled.failure_reason || harnessFailure;
        confirmation.pixel_settle.failure_reason = settleFailure;
      } else {
        confirmationFramePageMs = settled.match_page_ms;
        confirmation.changed_pixels = settled.edit_pixels;
        confirmation.witness_page_ms = settled.match_page_ms;
        confirmation.settled_page_ms = settled.settled_page_ms;
      }
    }
   } catch (error) {
     if (!pixelShadow) throw error;
     shadowError = String(error && error.message ? error.message : error).slice(0, 200);
   }
  }
  if (pixelShadow) {
    confirmation.pixel_settle_shadow = confirmation.pixel_settle || {failure_reason: shadowError || settleFailure || 'no_baseline_frame'};
    delete confirmation.pixel_settle;
    settleFailure = beforeShadow.settleFailure;
    confirmationFramePageMs = beforeShadow.confirmationFramePageMs;
    for (const [key, value] of [['changed_pixels', beforeShadow.changed], ['witness_page_ms', beforeShadow.witness], ['settled_page_ms', beforeShadow.settled]]) {
      if (value === undefined) delete confirmation[key]; else confirmation[key] = value;
    }
  }
  if (baseline.frame && confirmation.visible_rects.length && frame.document_region?.device_pixel_ratio > 0) {
    const event = await page.evaluate(() => window.__b2?.event);
    const recorder = baseline.recorder;
    const beforePixels = decodePng(Buffer.from(baseline.frame.data, 'base64'));
    const region = frame.document_region;
    const doc = region.rect_css_px;
    const dpr = region.device_pixel_ratio;
    const clock = {
      time_origin_ms: frame.time_origin_ms,
      timestamp_kind: frame.timestamp_kind,
      monotonic_origin_ms: skew.monotonic_origin_ms,
    };
    const markerMs = typeof event?.startTime === 'number' ? event.startTime : frame.after_page_ms;
    if (clock.timestamp_kind === 'monotonic_seconds' && typeof clock.monotonic_origin_ms !== 'number') {
      settleFailure = 'monotonic_origin_missing';
    } else if (typeof markerMs === 'number') {
      const recorded = [];
      let decision;
      const classifier = createRegionClassifier({baseline:baseline.frame.data,
        rects:confirmation.visible_rects,dpr,doc,tolerance:DEFAULT_CHANNEL_TOLERANCE});
      // Classification runs off-thread; CDP remains free to acknowledge
      // every frame while the recorded snapshot is processed.
      // W has elapsed in arm(). Snapshot all evidence BEFORE the Event
      // Timing poll — the poll only updates the entry, and a frame
      // delivered during it is not classified — sort by timestamp, and
      // classify through the decision time, including late delivery.
      const snapshot=[...recorder.frames].sort((a,b)=>
        convertFrameToPageMs(a,clock)-convertFrameToPageMs(b,clock));
      // Issue #171: the measured keydown's own Event Timing entry. Entries
      // are reported after the next paint, so when the glyph frame is the
      // last delivery the entry can lag it — poll briefly through the
      // observer's own notify hook. W already elapsed inside arm(); this
      // read extends no timed window and the sample stays the glyph frame's
      // pageMs minus the marker. The entry must be the measured keydown's
      // own: PerformanceEventTiming.startTime is the dispatched event's
      // timeStamp, so exact equality with state.event.startTime is the
      // identity check. Zero or more than one match is no verified entry
      // and is recorded as event_entry_ambiguous in the diagnostic.
      const inputEntry = await page.evaluate(async () => {
        const state = window.__b2;
        if (!state?.supported || !state.event) return null;
        const matches = () => state.entries.filter(e =>
          e.name === 'keydown' && e.startTime === state.event.startTime);
        let found = matches();
        if (!found.length) {
          await new Promise(resolve => {
            const timer = setTimeout(resolve, 500);
            state.notify = () => { if (matches().length) { clearTimeout(timer); resolve(); } };
          });
          found = matches();
        }
        return {entry: found.length === 1 ? found[0] : null, matches: found.length};
      });
      if (inputEntry) {
        confirmation.event_entry_matches = inputEntry.matches;
        if (inputEntry.matches !== 1) confirmation.event_entry_ambiguous = true;
      }
      // The entry is compared on the raw clock the rest of the lane uses:
      // edit_ms is confirmationFramePageMs - timing.event.startTime, and
      // page_offset_ms is not a conversion correction, so the entry's own
      // startTime/duration are used unshifted.
      const inputProcessing = inputEntry?.entry ? {
        startMs: inputEntry.entry.startTime,
        processingEndMs: inputEntry.entry.processingEnd,
        durationMs: inputEntry.entry.duration,
      } : null;
      try {
        for (const candidate of snapshot) {
          const pageMs = convertFrameToPageMs(candidate,clock);
          if (pageMs === null || pageMs < markerMs || pageMs > markerMs + settleMaxWaitMs) continue;
          if ((await frameAckSettled(candidate)) !== 'acked' || !candidate.data) {
            throw new Error('snapshot_frame_unacknowledged');
          }
          const classification = await classifier.classify(candidate.data);
          recorded.push({frame:candidate,pageMs,...classification});
          decision = settleFrames(recorded, {quietMs:quiescenceMs,maxWaitMs:settleMaxWaitMs,
            markerMs,minPixels:Math.ceil(DEFAULT_MIN_PIXELS*dpr*dpr),tolerance:DEFAULT_CHANNEL_TOLERANCE,
            frameIntervalMs:skew.frame_interval_ms,inputProcessing,
            eventStartMs:typeof event?.startTime === 'number' ? event.startTime : null});
          // All snapshot frames at or before this decision are now classified.
          // Include equal timestamps too, before accepting the prefix.
          const next=snapshot[snapshot.indexOf(candidate)+1];
          if (!decision.failure_reason && (!next || convertFrameToPageMs(next,clock)>pageMs)) break;
        }
        decision = settleFrames(recorded, {quietMs:quiescenceMs,maxWaitMs:settleMaxWaitMs,
          markerMs,minPixels:Math.ceil(DEFAULT_MIN_PIXELS*dpr*dpr),tolerance:DEFAULT_CHANNEL_TOLERANCE,
          frameIntervalMs:skew.frame_interval_ms,inputProcessing,
          eventStartMs:typeof event?.startTime === 'number' ? event.startTime : null});
      } finally {await classifier.close();}
      confirmation.frame_diagnostic = recorded.map(({frame,pageMs,ink_pixels,regions}) =>
        ({seq:frame.seq,page_ms:pageMs,delay_ms:pageMs-markerMs,ink_pixels,regions}));
      confirmation.settle_decision = decision;
      settleFailure = decision.failure_reason || null;
      if (!settleFailure) {
        const chosen = recorded[decision.reference_index];
        const reference = {...chosen,page_ms:chosen.pageMs};
        const first = recorded[decision.match_index];
        const match = {...first,page_ms:first.pageMs};
        if (match) {
          const matchPixels = decodePng(Buffer.from(match.frame.data, 'base64'));
          confirmation.rect_damage = rectDamageVsBaseline(
            beforePixels, matchPixels, confirmation.visible_rects, dpr, doc, DEFAULT_CHANNEL_TOLERANCE,
          );
          confirmation.changed_pixels = confirmation.rect_damage.reduce((sum, row) => sum + row.changed_pixels, 0);
          confirmation.baseline_seq = baseline.frame.seq;
          confirmation.settled_seq = reference.frame.seq;
          confirmation.witness_seq = match.frame.seq;
          confirmation.witness_page_ms = match.page_ms;
          confirmation.settled_page_ms = reference.page_ms;
          confirmation.settle_reference_seq = reference.frame.seq;
          confirmationFramePageMs = match.page_ms;
          confirmation.confirmed = (
            confirmation.after_count > confirmation.before_count
            && confirmation.changed_pixels >= DEFAULT_MIN_PIXELS
          );
        } else if (!settleFailure) {
          settleFailure = 'settle_not_reached';
        }
      }
    }
  }
  confirmation.settle_failure = settleFailure;
  // An observer delivery deadline is not a latency: durations come only
  // from matching Event Timing entries, and absence is explicitly censored.
  const timing = await page.evaluate(async () => {
    const state = window.__b2;
    const matching = () => state.entries.filter(e => e.name === 'keydown' && e.startTime === state.event.startTime);
    if (state.supported && !matching().length) await new Promise(resolve => {
      const timer = setTimeout(resolve, 500);
      state.notify = () => { if (matching().length) { clearTimeout(timer); resolve(); } };
    });
    state.observer?.disconnect();
    return { event: state.event, entries: matching(), supported:state.supported,
      outcome: !state.supported ? 'unsupported' : matching().length ? 'observed' : 'censored_below_16_ms',
      duration_threshold_ms:16, duration_step_ms:8 };
  });
  const duration = confirmationFramePageMs === null || !timing.event
    ? null
    : confirmationFramePageMs - timing.event.startTime;
  const scopedOk = modelOrFlagEdit ? frame.outcome === 'witnessed' : frame.outcome === 'witnessed' && frame.document_scoped;
  const ok = scopedOk && frame.clock_skew_acceptable && confirmation.confirmed && duration !== null && duration >= 0;
  if (modelOrFlagEdit && confirmation.pixel_settle) {
    // The pixel path's own verdict: the settled picture, and the edit confirmed in the editor. For a flag
    // editor the confirmation of each key is the arm's text count, settled after the arm (confirmArmByText).
    // As for every editor: no changed frame of the document inside the witness's window is no sample
    // (CodeRabbit, #248; the Python policy refuses it too).
    const framed = frame.outcome === 'witnessed';
    const pixelOk = !settleFailure && framed && frame.clock_skew_acceptable && duration !== null && duration >= 0;
    const confirmed = confirmation.confirmed || adapterSurface.kind === 'flag';
    return { mechanism, witness_kind: 'settled_pixels', clock_skew:skew, witness:frame, event_timing:timing,
      edit_confirmation:{...confirmation, pending_arm_text_count: adapterSurface.kind === 'flag'},
      timestamp_note: 'Uncorrected frame-to-page conversion; page_offset_ms is not a conversion correction. See clock_skew conversion bounds.',
      outcome: pixelOk && confirmed ? 'measured' : 'failed',
      failure_reason: pixelOk && confirmed ? null
        : settleFailure || (!framed ? 'frame_not_witnessed_in_window' : !frame.clock_skew_acceptable ? 'clock_check_not_acceptable'
          : duration === null || duration < 0 ? 'negative_input_latency' : 'expected_edit_not_confirmed'),
      edit_ms: pixelOk && confirmed ? duration : null, paint_ms: pixelOk ? duration : null };
  }
  return { mechanism, clock_skew:skew, witness:frame, event_timing:timing, edit_confirmation:confirmation,
    timestamp_note: 'Uncorrected frame-to-page conversion; page_offset_ms is not a conversion correction. See clock_skew conversion bounds.',
    outcome: ok ? 'measured' : 'failed',
    failure_reason: ok ? null : ((['witness_sparse','monotonic_origin_missing','glyph_before_next_paint','glyph_after_next_paint'].includes(settleFailure) ? settleFailure : null) || (!confirmation.confirmed && confirmation.changed_pixels < DEFAULT_MIN_PIXELS
      ? 'expected_edit_not_confirmed'
      : settleFailure || (!frame.clock_skew_acceptable ? 'clock_check_not_acceptable' : !frame.document_scoped ? 'not_document_scoped' : frame.outcome !== 'witnessed' ? 'no_frame' : !confirmation.confirmed ? 'expected_edit_not_confirmed' : 'negative_input_latency'))),
    edit_ms:ok ? duration : null, paint_ms:ok ? duration : null };
}

async function routeCorpus(context, routePath, bytes) {
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === routePath || u.pathname === sampleRoute) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: bytes,
      });
      return;
    }
    await route.continue();
  });
}

async function runPlaywrightPair() {
  const { chromium } = await loadPlaywright();
  const launchT0 = Date.now();
  const browser = await chromium.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  const browserLaunchMs = Date.now() - launchT0;

  const coldContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await routeCorpus(coldContext, corpusRoute, corpusBytes);
  const coldPage = await coldContext.newPage();
  const trace = await startChromeTrace(browser, coldPage, 'warm_cold');
  const cdp = await coldContext.newCDPSession(coldPage);

  const navT0 = Date.now();
  await coldPage.goto(url, { waitUntil: 'domcontentloaded', timeout: loadTimeout });
  const documentNavigationMs = Date.now() - navT0;

  const coldReady = await waitForReady(coldPage, readySelector, loadTimeout, navT0);
  const modelReadyMs = coldReady.first_usable_ms;
  let coldEdit = { edit_ms: null, paint_ms: null };
  let warmEdit = { edit_ms: null, paint_ms: null };
  const warmBurst = [];
  const coldBurst = [];
  if (!skipEdit) {
    coldEdit = await performEdit(coldPage, editSelector, cdp);
    for (let i = 0; i < 3; i++) {
      coldBurst.push(await performEdit(coldPage, editSelector, cdp));
    }
    await confirmArmByText(coldPage, coldReady, [coldEdit, ...coldBurst]);
  }

  await stopRecorder(cdp);
  const reloadT0 = Date.now();
  await coldPage.reload({ waitUntil: 'domcontentloaded', timeout: loadTimeout });
  const warmReady = await waitForReady(coldPage, readySelector, loadTimeout, reloadT0);
  const documentReloadSameContextMs = warmReady.first_usable_ms;

  if (!skipEdit) {
    warmEdit = await performEdit(coldPage, editSelector, cdp);
    for (let i = 0; i < 3; i++) {
      warmBurst.push(await performEdit(coldPage, editSelector, cdp));
    }
    await confirmArmByText(coldPage, warmReady, [warmEdit, ...warmBurst]);
  }

  await stopRecorder(cdp);
  await stopChromeTrace(browser, trace);
  await coldContext.close();
  await browser.close();

  return {
    load_timeout_ms: loadTimeout,
    browser_launch_only_ms: browserLaunchMs,
    document_navigation_only_ms: documentNavigationMs,
    model_ready_browser_ms: modelReadyMs,
    document_reload_same_context_ms: documentReloadSameContextMs,
    cold: {
      ...coldReady, ...coldEdit, burst: coldBurst,
      first_usable_ms: modelReadyMs,
      model_ready_browser_ms: modelReadyMs,
      single_edit_ms: coldEdit.edit_ms,
      presented_frame_ms: coldEdit.paint_ms,
      sustained_typing_median_ms:
        coldBurst.every(e => e.edit_ms !== null) && coldBurst.length ? coldBurst.map(e => e.edit_ms).sort((a,b) => a-b)[1] : null,
    },
    warm: {
      ...warmReady, ...warmEdit, burst: warmBurst,
      single_edit_ms: warmEdit.edit_ms,
      presented_frame_ms: warmEdit.paint_ms,
      sustained_typing_median_ms: warmBurst.every(e => e.edit_ms !== null) && warmBurst.length ? warmBurst.map(e => e.edit_ms).sort((a,b) => a-b)[1] : null,
    },
  };
}

/**
 * One page load, the requested criteria, no navigation in between.
 *
 * The page is the non-warm arm: it is the first navigation of a fresh browser
 * context, so C04 records `process_cold_fs_warm`. C07/C08/C09 run after the
 * load, the ready signal and the C04 quiescence window, which is the declared
 * preconditioning for `warm_steady` in their trial hints.
 */
async function runCriteriaSession() {
  if (driver !== 'playwright') {
    const entries = {};
    for (const id of criteriaList) {
      entries[id] = {
        criterion_id: id,
        outcome: 'unsupported',
        samples_ms: [],
        failure_reason: `criteria probe requires the playwright driver (got ${driver}): no CDP screencast frame witness`,
        assertion: { name: null, passed: false, scope: null, checks: {}, failures: ['driver'] },
        observations: [],
        notes: [],
      };
    }
    return {
      probe: 'criteria_input',
      schema: CRITERIA_SCHEMA,
      driver,
      editor_id: editorId,
      url,
      corpus_route: corpusRoute,
      criteria_requested: criteriaList.slice(),
      criteria: entries,
      paint_witness: {
        mechanism: null,
        frames_seen: 0,
        timeout_ms: frameTimeoutMs,
        message: 'driver is not playwright',
      },
    };
  }

  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await routeCorpus(context, corpusRoute, corpusBytes);
  let clipboardPermission = null;
  try {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], {
      origin: new URL(url).origin,
    });
    clipboardPermission = 'clipboard-read,clipboard-write';
  } catch (err) {
    clipboardPermission = `unavailable: ${String(err && err.message ? err.message : err)}`;
  }
  const page = await context.newPage();
  const trace = await startChromeTrace(browser, page, criteriaList[0] || 'input');
  const cdp = await context.newCDPSession(page);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: loadTimeout });
  // #196: C04's quiescence window and C07's clicks follow this ready; a select-all + copy read here
  // would add work to the one and leave the document selected for the other. C08/C09 read the text
  // themselves, outside their timed samples (#197).
  const ready = await waitForReady(page, readySelector, loadTimeout, Date.now(), { noCopy: true });
  const payload = await runCriteriaSuite({
    page,
    cdp,
    editSelector,
    criteria: criteriaList,
    frameTimeoutMs,
    quiescenceMs,
    quiescenceTimeoutMs,
    bulkChars,
    editorId,
    copyWaitMs,
    // r3c07b: each C07 point needs a fresh untouched state. Reloading the
    // same page restores it; the ready gate re-runs so a reload that breaks
    // the editor surfaces as a reload failure, not a click on a dead page.
    // The running screencast is untouched — this wait skips the clock-skew
    // calibration a full waitForReady does.
    reloadPage: async () => {
      await page.reload({ waitUntil: 'domcontentloaded', timeout: loadTimeout });
      await awaitReadySignal(page, readySelector, loadTimeout);
      if (waitAfterReadyMs > 0) {
        await page.waitForTimeout(waitAfterReadyMs);
      }
    },
  });
  await stopChromeTrace(browser, trace);
  await context.close();
  await browser.close();

  payload.editor_id = editorId;
  payload.url = url;
  payload.corpus_route = corpusRoute;
  payload.ready = {
    selector: readySelector,
    ready_ms: ready.first_usable_ms,
    first_usable_ms: ready.first_usable_ms,
    settle_ms: ready.settle_ms,
    clock_skew: ready.clock_skew,
    ready_page_ms: payload.ready.ready_page_ms,
    note: [payload.ready.note, 'ready_ms and first_usable_ms in criteria mode measure domcontentloaded to ready; pair and fresh modes include navigation.'].filter(Boolean).join(' '),
  };
  payload.clipboard_permission = clipboardPermission;
  payload.load_timeout_ms = loadTimeout;
  return payload;
}

async function coldOnlyFreshContext() {
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await routeCorpus(context, corpusRoute, corpusBytes);
  const page = await context.newPage();
  const trace = await startChromeTrace(browser, page, 'warm_cold');
  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: loadTimeout });
  const ready = await waitForReady(page, readySelector, loadTimeout, t0);
  await stopChromeTrace(browser, trace);
  await browser.close();
  return ready;
}

const collected = [];
if (criteriaList.length > 0) {
  const payload = await runCriteriaSession();
  process.stdout.write(JSON.stringify(payload));
  process.exit(0);
}
for (let i = 0; i < pairs; i++) {
  if (driver === 'puppeteer') {
    throw new Error('puppeteer input timing unsupported: requires shared CDP frame witness');
  } else {
    collected.push(await runPlaywrightPair());
  }
}

let freshContextMedians = [];
if (opt['fresh-context-probe'] !== 'false') {
  const freshSamples = [];
  for (let i = 0; i < Math.min(pairs, 3); i++) {
    freshSamples.push(await coldOnlyFreshContext());
  }
  freshContextMedians = freshSamples;
}

const result = {
  driver,
  url,
  corpus_route: corpusRoute,
  ready_selector: readySelector,
  edit_selector: editSelector,
  server_cold_pair: collected[0] || null,
  pairs: collected.map((pair, index) => ({...pair, server_cold: index === 0})),
  fresh_context_load_ms: freshContextMedians,
};

process.stdout.write(JSON.stringify(result));
