/**
 * Contract tests for fixinput3 (paint witness, click points, focus, paste settle).
 */
import { publishableRecord } from './witness_records.mjs';
import {
  assertBulkInsertBody,
  assertPreEditDocumentLoaded,
  measureBulkInsert,
  measureUndo,
  pointerTargetInsideEditable,
} from '../runner/criteria_input.mjs';

let failed = 0;
let checks = 0;
function assert(cond, msg) {
  checks += 1;
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failed += 1;
  }
}

// NIT-2: empty complex-corpus opening must refuse, not disable the gate.
assert(
  !assertPreEditDocumentLoaded(
    { text: 'anything' },
    { expectedOpeningText: null, expectedBodyText: null, openingRequired: true },
  ).ok,
  'openingRequired without opening text must refuse',
);
assert(
  assertPreEditDocumentLoaded(
    { text: 'Chapter 1: Heading' },
    {
      expectedOpeningText: 'Chapter 1:',
      expectedBodyText: null,
      openingRequired: false,
    },
  ).ok,
  'opening gate still accepts when opening is set',
);

// NIT-3: bulk insert expectation base is before.text coordinates.
const beforeDom = { text: 'LineA\nLineB', text_length: 11, selection_offset: 5 };
const fixtureWt = 'LineALineB';
const block = 'PASTE';
const bulkOpts = { expectedBodyText: fixtureWt, block };
const settledAfter = {
  text: 'LineAPASTE\nLineB',
  text_length: 'LineAPASTE\nLineB'.length,
  selection_offset: 10,
};
const bulk = assertBulkInsertBody(beforeDom, settledAfter, bulkOpts);
assert(bulk.ok, 'bulk insert uses before.text base (paragraph separators may differ from fixture)');

assert(
  pointerTargetInsideEditable({ contains: (n) => n === 'child' }, 'child'),
  'pointer hit inside editable',
);
assert(
  !pointerTargetInsideEditable({ contains: () => false }, 'footer'),
  'pointer on status bar is outside editable',
);

// BLOCKER-4: growth judged after paste settles; sample_ms still from first paint.
const bulkPaste = await (async () => {
  let reads = 0;
  const before = { text: 'ORIGINAL', text_length: 8, selection_offset: 8 };
  const page = {
    mouse: { click: async () => {} },
    keyboard: { press: async () => {} },
    locator: () => ({
      first: () => ({ boundingBox: async () => ({ x: 1, y: 1, width: 120, height: 40 }) }),
    }),
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE') {
        reads += 1;
        if (reads <= 2) return { ...before, active_inside: true };
        const growth = reads === 3 ? 3 : 8;
        const text = `ORIGINAL${'BLOCK'.slice(0, growth)}`;
        return {
          text,
          text_length: text.length,
          selection_offset: text.length,
          active_inside: true,
        };
      }
      if (typeof arg === 'string' && String(fn).includes('contains')) {
        return { inside: true, reason: null };
      }
      if (arg && typeof arg === 'object' && arg.kinds) return { t: 100 };
      if (typeof fn === 'function' && String(fn).includes('clipboard')) return null;
      if (typeof fn === 'function' && String(fn).includes('__perfCriteria')) return null;
      return null;
    },
  };
  const witness = {
    frameIntervalMs: 16.667,
    paintAfter: async (_pageMs, callOptions = {}) => {
      if (callOptions.arm) await callOptions.arm();
      return publishableRecord(140, 100);
    },
  };
  return measureBulkInsert(
    page,
    witness,
    { bulkChars: 5, block: 'BLOCK', modifier: 'Control', expectedBodyText: 'ORIGINAL' },
    {
      editable: { selector: '#doc', is_content_editable: true, text_length: 8 },
      points: [{ point: 'page_centre', x: 10, y: 10 }],
    },
  );
})();
assert(bulkPaste.outcome === 'measured', 'C08 measures when paste settles after first paint frame');

// BLOCKER-3 / 5: C09 refuses when focus not obtained after click on document.
const undoNoFocus = await (async () => {
  const page = {
    mouse: { click: async () => {} },
    keyboard: { type: async () => {}, press: async () => {} },
    locator: () => ({
      first: () => ({ boundingBox: async () => ({ x: 1, y: 1, width: 120, height: 40 }) }),
    }),
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE') {
        return {
          text: 'ABCDEF',
          text_length: 6,
          selection_offset: 3,
          is_content_editable: true,
          active_inside: false,
          anchor_inside: false,
          caret: { collapsed: true, top: 1, bottom: 2, left: 1, right: 2, height: 1 },
        };
      }
      if (arg && typeof arg === 'object' && arg.kind) return { inside: true };
      return null;
    },
  };
  return measureUndo(
    page,
    fakeWitness(),
    { modifier: 'Control', expectedBodyText: 'ABCDEF' },
    {
      editable: { selector: '#doc', is_content_editable: true, text_length: 6 },
      points: [{ point: 'page_centre', x: 10, y: 10, hit_inside_editable: true }],
    },
  );
})();

function fakeWitness() {
  return {
    frameIntervalMs: 16.667,
    paintAfter: async () => publishableRecord(200, 150),
  };
}

assert(
  undoNoFocus.failure_reason === 'editor_did_not_take_focus_after_click',
  'C09 names missing focus instead of blaming document text',
);

// A click whose fixed box never paints is not a sample: the FIRST click is
// the only witness (r3lanes4 ruling 2), so a dark box refuses the point with
// first_click_painted_nothing_in_click_region.
const c07CaretDom = await (async () => {
  const page = {
    mouse: { click: async () => {} },
    keyboard: { press: async () => {} },
    evaluate: async (fn, arg) => {
      if (fn.name === 'DOCUMENT_UNTOUCHED') {
        return { events: [], anchor_inside: false, active_inside: false, tapped: 0 };
      }
      if (fn.name === 'READ_EDITABLE_STATE') {
        return {
          text: 'AB',
          text_length: 2,
          is_content_editable: true,
          active_inside: true,
          anchor_inside: true,
          caret: { top: 10, bottom: 20, left: 5, right: 5, height: 10, collapsed: true },
        };
      }
      if (typeof arg === 'string' && String(fn).includes('contains')) {
        return { inside: true, reason: null };
      }
      if (arg && typeof arg === 'object' && arg.kind === 'pointerdown') return { t: 50, target: {} };
      if (typeof arg === 'number') return 32;
      if (String(fn).includes('__perfCriteria') && String(fn).includes('length = 0')) return null;
      return null;
    },
  };
  const { quietWindow } = await import('./witness_records.mjs');
  const witness = {
    frameIntervalMs: 16.667,
    paintAfter: async (_t, callOptions = {}) => {
      if (callOptions.arm) await callOptions.arm();
      return {
        outcome: 'no_frame', changed_pixels: 0, caret_masked: false,
        frames_after: 1, frames_total: 2, quiet_window: quietWindow(),
      };
    },
  };
  const { measureClicks } = await import('../runner/criteria_input.mjs');
  return measureClicks(
    page,
    {
      editable: { selector: '#doc', is_content_editable: true },
      points: [
        { point: 'first_text_line', x: 1, y: 1, line: { top: 8, bottom: 22 }, hit_inside_editable: true },
        { point: 'last_text_line', x: 30, y: 40, line: { top: 8, bottom: 22 }, hit_inside_editable: true },
      ],
    },
    { frameTimeoutMs: 2000, expectedBodyText: null, witness },
  );
})();
assert(c07CaretDom.outcome === 'failed', 'C07 refuses a click that never paints');
assert(
  String(c07CaretDom.failure_reason || '').includes('first_click_painted_nothing_in_click_region'),
  'C07 names first_click_painted_nothing_in_click_region',
);
assert(
  !(c07CaretDom.observations || []).some((observation) => observation.sample_ms != null),
  'C07 keeps no sample from a timeout clock',
);
assert(
  !(c07CaretDom.observations || []).some((observation) => observation.caret_dom_response === true),
  'C07 does not keep a caret-dom bypass',
);

if (failed) {
  process.exit(1);
}
console.log(`b4_fixinput3_contract: ${checks} checks ok`);
