/**
 * Contract tests for fixinput4: caret overlap, painted caret samples,
 * editor-model text, and the input-surface gate.
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { publishableRecord } from './witness_records.mjs';
import {
  READ_EDITABLE_STATE,
  READ_SUPERDOC_TEXT,
  RESOLVE_CLICK_POINTS,
  caretOverlapsLine,
  comparableDocumentText,
  differsBySingleInsertion,
  measureClicks,
  prepareInputSurface,
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
      if (fn && fn.name === 'READ_EDITABLE_STATE') {
        return {
          text: 'AB',
          text_length: 2,
          is_content_editable: true,
          active_inside: true,
          anchor_inside: true,
          caret: { ...plateCaret, collapsed: true },
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
      point: 'last_text_line',
      x: 12,
      y: 890,
      line: plateLine,
      hit_inside_editable: true,
    },
  ],
};

const refusedPage = clickPage(null, [], [40, 90]);
const refused = await measureClicks(
  refusedPage,
  {
    frameIntervalMs: 16.667,
    paintAfter: async (_t, callOptions = {}) => {
      if (callOptions.arm) await callOptions.arm();
      return { outcome: 'no_frame', changed_pixels: 0, caret_masked: true, frames_after: 1, frames_total: 2 };
    },
  },
  { frameTimeoutMs: 2000, expectedBodyText: null },
  meta,
);
assert(refused.outcome === 'failed', 'two dark frames refuse C07');
assert(
  String(refused.failure_reason || '').includes('click_paint_not_observed'),
  'the refusal is click_paint_not_observed',
);
assert(refused.samples_ms.length === 0, 'a timeout is not a sample');
assert(
  !refused.observations.some((observation) => observation.sample_ms != null || observation.caret_dom_response === true),
  'no caret-dom sample is kept',
);

let paintCalls = 0;
let seenRetry = null;
const retryKeys = [];
const retryPage = clickPage(null, retryKeys, [40, 90]);
const paintedRetry = await measureClicks(
  retryPage,
  {
    frameIntervalMs: 16.667,
    paintAfter: async (_t, callOptions = {}) => {
      if (callOptions.arm) await callOptions.arm();
      paintCalls += 1;
      if (paintCalls === 1) {
        return { outcome: 'no_frame', changed_pixels: 0, caret_masked: true, frames_after: 1, frames_total: 2 };
      }
      seenRetry = callOptions;
      return publishableRecord(180, 90);
    },
  },
  { frameTimeoutMs: 2000, expectedBodyText: null },
  meta,
);
assert(paintedRetry.outcome === 'measured', 'the unmasked click frame is the sample');
assert(paintedRetry.samples_ms[0] === 90, 'sample is frame_page_ms minus the re-click pointerdown');
assert(paintedRetry.observations[0].caret_dom_response !== true, 'caret_dom_response is not a bypass');
assert(seenRetry && seenRetry.caretMask === false, 'the retry turns the caret mask off');
assert(seenRetry && seenRetry.region && seenRetry.region.rect, 'the retry watches the caret rect');
assert(
  retryKeys.length === 0 || (!retryKeys.includes('ArrowRight') && !retryKeys.includes('ArrowLeft')),
  'C07 never substitutes a key for the click',
);
assert(
  retryPage.mouseClicks.length >= 2 && retryPage.mouseClicks.at(-1)[0] === 12 && retryPage.mouseClicks.at(-1)[1] === 890,
  'the retry re-clicks the same point, it never presses a key',
);

let stillCalls = 0;
const stillKeys = [];
const stillPage = clickPage(null, stillKeys, [40, 90]);
const stillCaret = await measureClicks(
  stillPage,
  {
    frameIntervalMs: 16.667,
    paintAfter: async (_t, callOptions = {}) => {
      if (callOptions.arm) await callOptions.arm();
      stillCalls += 1;
      return { outcome: 'no_frame', changed_pixels: 0, caret_masked: stillCalls === 1, frames_after: 1, frames_total: 2 };
    },
  },
  { frameTimeoutMs: 2000, expectedBodyText: null },
  meta,
);
assert(stillCaret.outcome === 'failed', 'an unmasked re-click that never paints is a refusal');
assert(
  String(stillCaret.failure_reason || '').includes('click_paint_not_observed'),
  'the refusal names click_paint_not_observed',
);
assert(stillCaret.samples_ms.length === 0, 'no sample without a painted frame');
assert(
  stillKeys.length === 0 || (!stillKeys.includes('ArrowRight') && !stillKeys.includes('ArrowLeft')),
  'no ArrowRight/ArrowLeft fallback exists',
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
      if (fn && fn.name === 'RESOLVE_CLICK_POINTS') {
        return { points: [{ point: 'last_text_line', x: 8, y: 40, hit_inside_editable: true }] };
      }
      return null;
    },
  };
}

const focusedUnchanged = await prepareInputSurface(
  paintedProbePage({ inside: true, tag: 'textarea' }),
  '#editor .superdoc__document',
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
  );
  assert(
    protectedRefusal.refusal === 'document_protected_read_only',
    'a focused unchanged stripped fixture is document_protected_read_only',
  );
  const missedClick = await prepareInputSurface(
    paintedProbePage({ inside: false, tag: 'div' }),
    '#editor .superdoc__document',
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
    if (fn && fn.name === 'RESOLVE_CLICK_POINTS') {
      return { points: [{ point: 'last_text_line', x: 4, y: 4, hit_inside_editable: true }] };
    }
    if (arg && (arg.kind || arg.kinds)) return null;
    return null;
  },
};
const lockedSurface = await prepareInputSurface(locked, '#doc');
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
      <p style="margin:24px 0 0">SECOND LINE INSIDE THE EDITOR SURFACE</p>
    </div>`);
  const resolved = await page.evaluate(RESOLVE_CLICK_POINTS, '#doc');
  const first = (resolved.points || []).find((point) => point.point === 'first_text_line');
  assert(first && first.hit_inside_editable === true, 'an occluded first line moves onto a hittable line');
  assert(first && first.y > 28, 'the first-line click is below the toolbar');
} finally {
  await browser.close();
}

if (failed) process.exit(1);
console.log(`b4_fixinput4_contract: ${checks} checks ok`);
