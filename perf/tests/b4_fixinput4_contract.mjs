/**
 * Contract tests for fixinput4: caret overlap, painted caret samples,
 * editor-model text, and the input-surface gate.
 */
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { publishableRecord, quietWindow } from './witness_records.mjs';
import { decodePng } from '../runner/witness.mjs';
import { INK_DARK_LUMA, inkClickPoints } from '../runner/ink_points.mjs';
import {
  READ_EDITABLE_STATE,
  READ_SUPERDOC_TEXT,
  caretOverlapsLine,
  clickPaintRegion,
  comparableDocumentText,
  differsBySingleInsertion,
  measureClicks,
  prepareInputSurface,
  resolveInkClickPoints,
} from '../runner/criteria_input.mjs';

const require = createRequire(fileURLToPath(new URL('../../harness/ui/package.json', import.meta.url)));
const { chromium } = require('playwright');

let failed = 0;
let checks = 0;
function assert(cond, msg) {
  checks += 1;
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failed += 1;
  }
}

const plateCaret = { top: 877.8, bottom: 895.8, height: 18, left: 10, right: 12 };
const plateLine = { top: 880.8, bottom: 898.8 };
assert(caretOverlapsLine(plateCaret, plateLine), 'plate caret overlaps the clicked line by 15 of 18 px');
assert(
  !caretOverlapsLine({ top: 0, bottom: 18, height: 18 }, { top: 17, bottom: 40 }),
  '1 px of an 18 px caret is not on the line',
);

function clickPage(onKey, keys, pointerTimes) {
  const times = pointerTimes || [40, 90, 95, 100];
  let pointerReads = 0;
  const mouseClicks = [];
  const page = {
    mouse: {
      click: async (x, y) => {
        mouseClicks.push([x, y]);
      },
    },
    keyboard: {
      press: async (key) => {
        if (keys) keys.push(key);
      },
      type: async (text) => onKey && onKey(text),
    },
    evaluate: async (fn, arg) => {
      if (fn && fn.name === 'DOCUMENT_UNTOUCHED') {
        return { events: [], anchor_inside: false, active_inside: false, tapped: 0 };
      }
      if (fn && fn.name === 'READ_EDITABLE_STATE') {
        const lastClick = mouseClicks[mouseClicks.length - 1];
        const clickedY = lastClick ? lastClick[1] : null;
        return {
          text: 'AB',
          text_length: 2,
          is_content_editable: true,
          active_inside: true,
          anchor_inside: true,
          caret: clickedY == null
            ? { ...plateCaret, collapsed: true }
            : { top: clickedY - 9, bottom: clickedY + 9, height: 18, left: 10, right: 12, collapsed: true },
        };
      }
      if (typeof arg === 'string') return { inside: true, reason: null };
      if (arg && arg.kind === 'pointerdown') {
        const t = times[Math.min(pointerReads, times.length - 1)];
        pointerReads += 1;
        return { t, target: {} };
      }
      if (arg && arg.kind === 'keydown') return { t: 90, key: 'ArrowRight' };
      if (typeof arg === 'number') return 12;
      return null;
    },
  };
  page.mouseClicks = mouseClicks;
  return page;
}

const meta = {
  editable: { selector: '#doc', is_content_editable: true },
  points: [
    {
      point: 'first_text_line',
      x: 60,
      y: 603,
      line: { top: 594, bottom: 612 },
      hit_inside_editable: true,
    },
    {
      point: 'last_text_line',
      x: 12,
      y: 890,
      line: plateLine,
      hit_inside_editable: true,
    },
  ],
};

/**
 * r3lanes4 ruling #2: C07 has one witness per point — the FIRST click,
 * unmasked, watched over a fixed box around the click point. This builds the
 * unmasked box record the production witness emits for that click.
 */
function unmaskedBoxRecord(frameMs, markerMs, changed = 240) {
  const record = publishableRecord(frameMs, markerMs);
  const css = { x: 0, y: 876, width: 48, height: 30 };
  const device = { x: 0, y: 876, width: 48, height: 30 };
  const area = device.width * device.height;
  record.caret_masked = false;
  record.caret_mask_css = null;
  record.caret_mask_error = null;
  record.document_scoped = true;
  record.document_region = {
    source: 'rect',
    selector: null,
    rect_css_px: css,
    rect_device_px: device,
    device_pixel_ratio: 1,
  };
  record.region_pixels = area;
  record.total_pixels = area;
  record.changed_pixels = changed;
  record.diff_ratio = changed / area;
  record.max_diff_ratio = changed / area;
  record.quiet_window = quietWindow();
  return record;
}

const refusedPage = clickPage(null, [], [40]);
let refusedCalls = 0;
let refusedOptions = null;
const refused = await measureClicks(
  refusedPage,
  meta,
  {
    frameTimeoutMs: 2000,
    expectedBodyText: null,
    witness: {
      frameIntervalMs: 16.667,
      paintAfter: async (_t, callOptions = {}) => {
        refusedCalls += 1;
        refusedOptions = callOptions;
        if (callOptions.arm) await callOptions.arm();
        return {
          outcome: 'no_frame', changed_pixels: 0, caret_masked: false,
          frames_after: 1, frames_total: 2, quiet_window: quietWindow(),
        };
      },
    },
  },
);
assert(refused.outcome === 'failed', 'a click that paints nothing in the box refuses C07');
assert(
  String(refused.failure_reason || '').includes('first_click_painted_nothing_in_click_region'),
  'the refusal names the first click painting nothing in the click region',
);
assert(refused.samples_ms.length === 0, 'a timeout is not a sample');
assert(refusedCalls === meta.points.length, 'one witness for one click per point; no second look');
assert(refusedOptions.caretMask === false, 'the one click runs with no caret mask');
assert(refusedOptions.region && refusedOptions.region.rect, 'the witness watches the fixed click box');
assert(refusedPage.mouseClicks.length === meta.points.length, 'no setup click, no re-click: the first click is the only click');
assert(
  !refused.observations.some((observation) => observation.sample_ms != null || observation.caret_dom_response === true),
  'no caret-dom sample is kept',
);

let paintCalls = 0;
let seenRegion = null;
let seenMask = null;
const singlePage = clickPage(null, [], [40]);
const painted = await measureClicks(
  singlePage,
  meta,
  {
    frameTimeoutMs: 2000,
    expectedBodyText: null,
    witness: {
      frameIntervalMs: 16.667,
      paintAfter: async (_t, callOptions = {}) => {
        paintCalls += 1;
        if (callOptions.arm) await callOptions.arm();
        seenRegion = callOptions.region;
        seenMask = callOptions.caretMask;
        return unmaskedBoxRecord(180, 40);
      },
    },
  },
);
assert(painted.outcome === 'measured', 'the first click frame is the sample');
assert(painted.samples_ms[0] === 140, 'sample is frame_page_ms minus the click pointerdown (180-40)');
assert(painted.observations[0].caret_dom_response !== true, 'caret_dom_response is not a bypass');
assert(paintCalls === meta.points.length, 'one click is one witness per point');
assert(seenMask === false, 'the click runs unmasked');
assert(seenRegion && seenRegion.rect, 'the witness watches a fixed box around the click point');
assert(seenRegion.rect.width === 48, 'the documented box is 48 CSS px wide');
assert(seenRegion.rect.x === 0, 'the box is centred on the click x (12 - 24 clamped to 0)');
assert(
  seenRegion.rect.y <= plateLine.top && seenRegion.rect.y + seenRegion.rect.height >= plateLine.bottom,
  'the box contains a caret of the clicked line',
);
assert(
  painted.observations[0].click_region && painted.observations[0].click_region.rect.width === 48,
  'the observation documents the click region',
);
assert(
  !Object.prototype.hasOwnProperty.call(painted.observations[0], 'caret_paint_attempt'),
  'no unmasked-reclick fields survive',
);
assert(singlePage.mouseClicks.length === meta.points.length, 'one click only per point');

let deadCalls = 0;
const deadKeys = [];
const deadPage = clickPage(null, deadKeys, [40]);
const deadScreencast = await measureClicks(
  deadPage,
  meta,
  {
    frameTimeoutMs: 2000,
    expectedBodyText: null,
    witness: {
      frameIntervalMs: 16.667,
      paintAfter: async (_t, callOptions = {}) => {
        deadCalls += 1;
        if (callOptions.arm) await callOptions.arm();
        return {
          outcome: 'no_frame', changed_pixels: 0, caret_masked: false,
          frames_after: 0, frames_total: 0, quiet_window: quietWindow(),
        };
      },
    },
  },
);
assert(deadScreencast.outcome === 'failed', 'a dead screencast is not a sample');
assert(
  String(deadScreencast.failure_reason || '').includes('no_painted_frame_within_2000ms'),
  'no frames at all is no_painted_frame, not the click refusal',
);
assert(deadScreencast.samples_ms.length === 0, 'no sample without a painted frame');
assert(deadCalls === meta.points.length && deadPage.mouseClicks.length === meta.points.length, 'still one click, one witness per point');
assert(
  deadKeys.length === 0 || (!deadKeys.includes('ArrowRight') && !deadKeys.includes('ArrowLeft')),
  'C07 never substitutes a key for the click',
);

assert(
  comparableDocumentText('cafe\u0301') === comparableDocumentText('caf\u00e9'),
  'NFC equates a combining acute with a composed e',
);
assert(
  comparableDocumentText('cafe') !== comparableDocumentText('caf\u00e9'),
  'a dropped combining mark still mismatches',
);
assert(
  comparableDocumentText('a\u200d') !== comparableDocumentText('a'),
  'NFC does not hide a dropped ZWJ',
);
assert(differsBySingleInsertion('abcd', 'abxcd', 'x'), 'one inserted x is the typed character');
assert(!differsBySingleInsertion('abcd', 'abxyd', 'x'), 'a second edit is not a single insertion');
assert(differsBySingleInsertion('abcd', 'abHELLOcd', 'HELLO'), 'a pasted block inserted off the reported offset is still that block');
assert(!differsBySingleInsertion('abcd', 'abHELLOxcd', 'HELLO'), 'an extra character beside the block is not the paste');

function paintedProbePage(active) {
  return {
    mouse: { click: async () => {} },
    keyboard: { type: async () => {}, press: async () => {} },
    async evaluate(fn) {
      if (fn && fn.name === 'DESCRIBE_INPUT_SURFACE') {
        return {
          mode_button: false,
          contenteditable: false,
          selector: '#editor .superdoc__document',
          kind: 'painted_runs',
          read_only: false,
        };
      }
      if (fn && fn.name === 'READ_EDITABLE_STATE') {
        return {
          text: 'SAME',
          text_length: 4,
          text_source: 'painted_runs',
          read_only: false,
          is_content_editable: false,
          active_inside: active.inside,
          active_tag: active.tag,
          anchor_inside: false,
        };
      }
      return null;
    },
  };
}
const PROBE_POINTS = [{ point: 'last_text_line', x: 8, y: 40, hit_inside_editable: true }];

const focusedUnchanged = await prepareInputSurface(
  paintedProbePage({ inside: true, tag: 'textarea' }),
  '#editor .superdoc__document',
  null,
  PROBE_POINTS,
);
assert(
  String(focusedUnchanged.refusal || '').includes('input_did_not_change_document'),
  'a focused editor that does not change text is a missed edit without the stripped variant',
);
const previousVariant = process.env.PERF_FIXTURE_VARIANT;
process.env.PERF_FIXTURE_VARIANT = 'complex-corpus-without-document-protection';
try {
  const protectedRefusal = await prepareInputSurface(
    paintedProbePage({ inside: true, tag: 'textarea' }),
    '#editor .superdoc__document',
    null,
    PROBE_POINTS,
  );
  assert(
    protectedRefusal.refusal === 'document_protected_read_only',
    'a focused unchanged stripped fixture is document_protected_read_only',
  );
  const missedClick = await prepareInputSurface(
    paintedProbePage({ inside: false, tag: 'div' }),
    '#editor .superdoc__document',
    null,
    PROBE_POINTS,
  );
  assert(
    String(missedClick.refusal || '').includes('input_did_not_change_document'),
    'a click that never focused a control stays input_did_not_change_document',
  );
} finally {
  if (previousVariant === undefined) delete process.env.PERF_FIXTURE_VARIANT;
  else process.env.PERF_FIXTURE_VARIANT = previousVariant;
}

const modePage = {
  clicks: [],
  waits: 0,
  async click(selector) {
    this.clicks.push(selector);
  },
  async waitForFunction() {
    this.waits += 1;
    return true;
  },
  async evaluate(fn) {
    if (fn && fn.name === 'DESCRIBE_INPUT_SURFACE') {
      if (this.clicks.length === 0) {
        return { mode_button: true, contenteditable: false, selector: '#pages', kind: 'dom' };
      }
      return {
        mode_button: true,
        contenteditable: true,
        selector: '#editorHost',
        kind: 'contenteditable_descendant',
      };
    }
    return null;
  },
};
const opened = await prepareInputSurface(modePage, '#pages');
assert(modePage.clicks[0] === '#modeEditor', 'docxodus opens editor mode before measuring');
assert(opened.selector === '#editorHost', 'measurement rebinds to the editor host');
assert(opened.usable === true && opened.probed === false, 'a contenteditable editor skips the destructive probe');

const locked = {
  mouse: { click: async () => {} },
  keyboard: { type: async () => {}, press: async () => {} },
  async evaluate(fn, arg) {
    if (fn && fn.name === 'DESCRIBE_INPUT_SURFACE') {
      return { mode_button: false, contenteditable: false, selector: '#doc', kind: 'dom', read_only: true };
    }
    if (fn && fn.name === 'READ_EDITABLE_STATE') {
      return { text: 'LOCKED', text_length: 6, read_only: true, is_content_editable: false };
    }
    if (arg && (arg.kind || arg.kinds)) return null;
    return null;
  },
};
const lockedSurface = await prepareInputSurface(locked, '#doc', null, [
  { point: 'last_text_line', x: 4, y: 4, hit_inside_editable: true },
]);
assert(lockedSurface.refusal === 'document_protected_read_only', 'a locked surface names document_protected_read_only');

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.setContent(`<!doctype html><div id="root" class="docx-page-content">
    <p data-paragraph-id="a" data-start="0">SHORT</p>
  </div>
  <div id="super"><span class="superdoc-text-run">Hello </span><span class="superdoc-text-run">world</span></div>
  <script>
    window.__DOCX_EDITOR_E2E__ = {
      getEditor() {
        return {
          query() { return [{ text: 'AAAA' }, { text: 'BBBB' }]; },
          snapshot() { return { editable: true }; },
        };
      },
    };
  </script>`);
  const model = await page.evaluate(READ_EDITABLE_STATE, '#root [data-paragraph-id]');
  assert(model.text === 'AAAABBBB', 'eigenpal text comes from the editor model');
  assert(model.text_source === 'editor_model', 'text source is editor_model');
  assert(model.text !== 'SHORT', 'the virtualized DOM sum is not the document');
  await page.evaluate(() => {
    delete window.__DOCX_EDITOR_E2E__;
  });
  const runs = await page.evaluate(READ_EDITABLE_STATE, '#super');
  assert(runs.text === 'Hello world', 'superdoc correctness reads painted runs');
  assert(runs.text_source === 'painted_runs', 'text source is painted_runs');
  assert(runs.input_reachable === true, 'painted runs are an input surface');
  await page.evaluate(() => {
    window.__SUPERDOC_E2E__ = {
      activeEditor: { doc: { async getText() { return 'Hello world from the model'; } } },
    };
  });
  const superdocModel = await page.evaluate(READ_SUPERDOC_TEXT);
  assert(superdocModel === 'Hello world from the model', 'superdoc correctness reads activeEditor.doc.getText');
  await page.evaluate(() => {
    const host = document.createElement('div');
    host.id = 'sdhost';
    host.innerHTML = '<textarea id="sdta"></textarea>';
    document.body.appendChild(host);
    document.getElementById('sdta').focus();
    window.__SUPERDOC_E2E__ = {
      ui: {
        selection: {
          getAnchorRect() {
            return { top: 880.7, bottom: 897.7, left: 40, right: 42, width: 2, height: 17 };
          },
          getSnapshot() {
            return { empty: false, quotedText: 'word', status: 'ready' };
          },
        },
      },
    };
  });
  const caretState = await page.evaluate(READ_EDITABLE_STATE, '#sdhost');
  assert(caretState.caret && caretState.caret.height === 17, 'superdoc caret is the editor anchor rect');
  assert(caretState.caret.top === 880.7, 'the anchor rect is not the textarea selection');
  assert(caretState.caret.collapsed === false, 'an expanded superdoc selection is not a collapsed caret');
  assert(caretState.selection_expanded === true, 'the expanded selection is visible to the type gate');
  await page.setContent(`<!doctype html><div id="editorHost">
    <div id="pagination-container">
      <div id="pagination-staging"><p data-anchor contenteditable="true">STAGING</p></div>
      <div data-hf-band><p data-anchor contenteditable="true">HEADER</p></div>
      <p data-anchor contenteditable="true">BODY<a class="comment-marker">c</a></p>
    </div>
  </div>`);
  const blocks = await page.evaluate(READ_EDITABLE_STATE, '#editorHost');
  assert(blocks.text === 'BODY', 'docxodus text is the body blocks, not staging or the header');
  assert(blocks.text_source === 'editor_blocks', 'text source is editor_blocks');
  assert(!String(blocks.text).includes('STAGING') && !String(blocks.text).includes('HEADER'), 'copies are excluded');
  await page.setContent(`<!doctype html><div id="bar" style="height:28px">toolbar</div>
    <div id="doc" style="height:220px;width:420px;overflow:hidden">
      <p style="margin:0;position:relative;top:-18px">FIRST LINE UNDER THE TOOLBAR</p>
      <p style="margin:24px 0 0;line-height:24px">SECOND LINE INSIDE THE EDITOR SURFACE<br>THIRD LINE INSIDE THE EDITOR SURFACE</p>
    </div>`);
  const resolved = await resolveInkClickPoints(page, { kind: 'dom', selector: '#doc' });
  const points = (resolved && resolved.points) || [];
  assert(points.length >= 2, 'the ink scan resolves at least two distinct painted lines');
  assert(
    new Set(points.map((point) => `${point.x}|${point.y}`)).size === points.length,
    'no resolved point is measured twice',
  );
  const first = points.find((point) => point.point === 'first_text_line');
  assert(first && first.hit_inside_editable === true, 'the first line hit-tests inside the editable');
  assert(first && first.y > 28, 'the first-line click is below the toolbar');
} finally {
  await browser.close();
}

// ------------------------------------------------------------------ r3c07
// The click-point scan is pixel based and shared by every editor: all three
// points must sit on painted ink (a caret is expected next to the click, so
// it lands inside the watched box), in the document text block — never on
// page whitespace, ribbon chrome, rulers, or a status bar.
const INK_FIXTURES = new URL('./fixtures/ink/', import.meta.url);
function inkFixture(name, clip) {
  const img = decodePng(readFileSync(fileURLToPath(new URL(name, INK_FIXTURES))));
  return { img, clip, origin: { x: 0, y: 0 } };
}
function pixelLuma(img, x, y) {
  const p = (Math.round(y) * img.width + Math.round(x)) * 4;
  return 0.299 * img.data[p] + 0.587 * img.data[p + 1] + 0.114 * img.data[p + 2];
}
function assertInkPoint(img, geo, point, label) {
  if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) {
    assert(false, `${label}: ${point && point.point} resolves a coordinate`);
    return;
  }
  const px = point.x - geo.origin.x;
  const py = point.y - geo.origin.y;
  const clip = geo.clip;
  assert(
    point.x >= clip.left && point.x < clip.right && point.y >= clip.top && point.y < clip.bottom,
    `${label}: ${point.point} stays inside the clip`,
  );
  assert(
    pixelLuma(img, px, py) < INK_DARK_LUMA,
    `${label}: ${point.point} at (${point.x},${point.y}) is on painted ink, not whitespace`,
  );
  assert(point.line && point.line.top <= point.y && point.y <= point.line.bottom, `${label}: ${point.point} carries its line box`);
  const region = clickPaintRegion(point).rect;
  assert(
    region.y <= point.line.top && region.y + region.height >= point.line.bottom,
    `${label}: the watched box contains the clicked line of ${point.point}`,
  );
}
function assertInkGrid(img, geo, label) {
  const ink = inkClickPoints(img, geo.clip);
  assert(ink.source === 'ink_runs', `${label}: the point source is named ink_runs`);
  assert(ink.points.length === 3, `${label}: three click points resolve`);
  for (const name of ['page_centre', 'first_text_line', 'last_text_line']) {
    const point = ink.points.find((p) => p.point === name);
    assertInkPoint(img, geo, point, label);
  }
  const named = ['first_text_line', 'page_centre', 'last_text_line'].map((name) =>
    ink.points.find((p) => p.point === name),
  );
  if (named.some((p) => !p)) return ink;
  const ordered = named.map((p) => p.y);
  assert(ordered[0] < ordered[1] && ordered[1] < ordered[2], `${label}: first < centre < last by painted line`);
  assert(ink.line_height_px > 4, `${label}: a line height is measured from the ink`);
  return ink;
}

{
  // plate's failing point: (640, 480.5) was the geometric clip centre — an
  // inter-paragraph gap; the caret snapped to a line end outside the box.
  const { img, clip, origin } = inkFixture('plate_clip.png', { left: 190, top: 61, right: 1090, bottom: 900 });
  const ink = assertInkGrid(img, { clip, origin }, 'plate');
  const centre = ink.points.find((p) => p.point === 'page_centre');
  assert(centre && Math.abs(centre.y - 480.5) > 8, 'plate page_centre moved off the paragraph gap');
}
{
  // canvas's failing point: (640, 458) was a paragraph gap inside the
  // painted page canvas; the model caret painted 283 px below the box.
  const { img, clip, origin } = inkFixture('canvas_clip.png', { left: 232, top: 16, right: 1048, bottom: 900 });
  const ink = assertInkGrid(img, { clip, origin }, 'canvas');
  const firstLine = ink.points.find((p) => p.point === 'first_text_line');
  assert(firstLine && Math.abs(firstLine.y - 148.6) > 5, 'canvas first_text_line moved off the heading gap');
}
{
  // wordcraft paints everything — ribbon, rulers, page, status bar — into
  // one window-wide canvas; the click points must come from the document
  // text block, not the chrome.
  const { img, clip, origin } = inkFixture('wordcraft_clip.png', { left: 0, top: 0, right: 1280, bottom: 900 });
  const ink = assertInkGrid(img, { clip, origin }, 'wordcraft');
  for (const point of ink.points) {
    assert(point.y > 240 && point.y < 860, `wordcraft ${point.point} is inside the page text, not ribbon or status bar`);
    assert(point.x > 240 && point.x < 1040, `wordcraft ${point.point} is inside the page column, not a ruler`);
  }
}

// Synthetic covers: no ink, a single line, chrome above the document, a
// status bar below it, and margin ticks beside the text column.
function synthImage(width, height) {
  const data = new Uint8ClampedArray(width * height * 4).fill(255);
  return { width, height, data };
}
function synthInk(img, x0, x1, y) {
  for (let x = Math.round(x0); x < Math.round(x1); x += 1) {
    const p = (Math.round(y) * img.width + x) * 4;
    img.data[p] = 0;
    img.data[p + 1] = 0;
    img.data[p + 2] = 0;
  }
}
// A text line is ~14 px of glyph rows broken by intra-glyph white rows.
function synthLine(img, x0, x1, top) {
  for (let y = top; y < top + 14; y += 1) {
    if (y % 5 === 4) continue; // a descender gap inside the line
    let x = x0;
    while (x < x1) {
      const word = 18 + ((x / 7) % 20);
      synthInk(img, x, Math.min(x + word, x1), y);
      x += word + 6;
    }
  }
}

{
  const empty = inkClickPoints(synthImage(800, 600), { left: 0, top: 0, right: 800, bottom: 600 });
  assert(empty.points.length === 0, 'an image with no ink yields no click points');
}
{
  const img = synthImage(800, 600);
  synthLine(img, 100, 700, 100); // one painted text line only
  const geo = { clip: { left: 0, top: 0, right: 800, bottom: 600 }, origin: { x: 0, y: 0 } };
  const ink = inkClickPoints(img, geo.clip);
  assert(ink.points.length === 3, 'a single painted line still yields the three named points');
  for (const point of ink.points) assertInkPoint(img, geo, point, 'single-line');
}
{
  const img = synthImage(800, 700);
  // ribbon: dense scattered icon ink above a large gap
  for (let y = 10; y < 60; y += 2) for (let x = 20; x < 780; x += 9) synthInk(img, x, x + 3, y);
  // document: three paragraphs of two lines each
  for (const top of [200, 226, 260, 286, 320, 346]) synthLine(img, 100, 700, top);
  // status bar: a thin wide band of text below another large gap
  synthLine(img, 10, 790, 660);
  const geo = { clip: { left: 0, top: 0, right: 800, bottom: 700 }, origin: { x: 0, y: 0 } };
  const ink = inkClickPoints(img, geo.clip);
  assert(ink.points.length === 3, 'chrome around the document still yields three points');
  for (const point of ink.points) {
    assert(point.y > 190 && point.y < 370, `synthetic ${point.point} stays in the document block, off ribbon and status bar`);
    assertInkPoint(img, geo, point, 'synthetic');
  }
}
{
  const img = synthImage(800, 700);
  for (let y = 200; y < 500; y += 12) synthInk(img, 10, 13, y); // ruler ticks in the left margin
  for (const top of [210, 236, 330, 356]) synthLine(img, 100, 700, top);
  const ink = inkClickPoints(img, { left: 0, top: 0, right: 800, bottom: 700 });
  for (const point of ink.points) assert(point.x > 60, 'synthetic points stay off the ruler tick column');
}

if (failed) process.exit(1);
console.log(`b4_fixinput4_contract: ${checks} checks ok`);
