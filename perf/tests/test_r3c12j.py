"""r3c12j: C12 text-commit delay when Enter replaces the anchor node.

The move is painted in the Enter keydown. The caret "x" lands later. A sample
is the move, and the recorder reads the matched block's rect only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import perf.runner.benchmark_document as bd
from perf.tests.witness_records import publishable_witness_record

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"
LANE = REPO / "perf" / "runner" / "lane_edit_burst.mjs"
SURFACE = REPO / "perf" / "runner" / "edit_surface.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
WITNESS_SERVER = REPO / "perf" / "tests" / "fixtures" / "witness" / "server.py"
TIMEOUT_S = 90

# One rect of the matched block per frame, plus one read of slack. A census
# reads one rect per block, which is past this constant once the host has
# more blocks than the constant.
READS_PER_FRAME = 2


def _node():
    return shutil.which("node")


def _playwright_ready() -> bool:
    if os.environ.get("WITNESS_PLAYWRIGHT"):
        return True
    for candidate in (
        REPO / "harness" / "ui" / "plate" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright-core",
    ):
        if candidate.is_dir():
            return True
    return False


def _load_server():
    import importlib.util

    spec = importlib.util.spec_from_file_location("r3c12j_fixture_server", WITNESS_SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AnchorByText(unittest.TestCase):
    def test_finds_the_fixture_text_without_reading_rects(self):
        # NFD on the element, NFC on the fixture string. Same normalization
        # as the r3c12i pair: NFC, whitespace collapse, trim. Fifty other
        # blocks must not be measured.
        payload = self.node(
            r"""
let rects = 0;
const block = (text) => ({
  textContent: text,
  innerText: text,
  isConnected: true,
  getBoundingClientRect: () => { rects += 1; return { top: 10, bottom: 30, left: 0, height: 20, width: 40 }; },
});
const fillers = Array.from({ length: 50 }, (_, i) => block('Filler block ' + i));
const anchor = block('cafe\u0301 anchor line');
const nodes = [...fillers, anchor];
globalThis.document = { querySelectorAll: () => nodes };
globalThis.window = globalThis;
const found = mod.c12AnchorElementByText('', '.doc-paragraph', '', 'caf\u00e9 anchor line', 1);
assert.equal(found, anchor);
assert.equal(rects, 0, 'rect reads ' + rects);
const pageFn = (0, eval)(`(function(){ ${mod.C12_ANCHOR_BY_TEXT_PAGE_SRC}; return c12AnchorElementByText; })()`);
rects = 0;
const viaPage = pageFn('', '.doc-paragraph', '', 'caf\u00e9 anchor line', 1);
assert.equal(viaPage, anchor);
assert.equal(rects, 0);
const first = block('Beta shared anchor line for C12.');
const second = block('Beta shared anchor line for C12.');
globalThis.document = { querySelectorAll: () => [first, second] };
assert.equal(mod.c12AnchorElementByText('', '.doc-paragraph', '', 'Beta shared anchor line for C12.', 2), second);
assert.equal(rects, 0);
console.log(JSON.stringify({ rects, found: true }));
"""
        )
        self.assertEqual(payload["rects"], 0)
        self.assertTrue(payload["found"])

    def test_scrolls_the_caret_paragraph_with_one_shared_call(self):
        # One shared call for every editor: the caret paragraph's own text,
        # occurrence 1, block center. Other blocks are not measured.
        payload = self.node(
            r"""
let rects = 0;
const scrolled = [];
const make = (text, y) => {
  const box = { top: y };
  return {
    textContent: text,
    isConnected: true,
    getBoundingClientRect: () => {
      rects += 1;
      return { top: box.top, bottom: box.top + 20, height: 20, left: 8, width: 100 };
    },
    scrollIntoView: (opts) => {
      scrolled.push(opts);
      box.top = 450;
    },
  };
};
const fillers = Array.from({ length: 40 }, (_, i) => make('Filler block ' + i, 20 + i));
const caret = make('Alpha body paragraph here', 1240);
globalThis.document = { querySelectorAll: () => [...fillers, caret] };
globalThis.window = globalThis;
const result = mod.c12ScrollCaretIntoView('', '.doc-paragraph', '', 'Alpha body paragraph here', 1);
assert.equal(result.block, 'center', JSON.stringify(result));
assert.equal(result.inline, 'nearest');
assert.equal(result.behavior, 'instant');
assert.equal(result.top_before, 1240);
assert.equal(result.top_after, 450);
assert.equal(rects, 2, 'rect reads ' + rects);
assert.equal(scrolled.length, 1);
assert.deepEqual(scrolled[0], { block: 'center', inline: 'nearest', behavior: 'instant' });
console.log(JSON.stringify({ rects, block: result.block, top_before: result.top_before, top_after: result.top_after }));
"""
        )
        self.assertEqual(payload["rects"], 2)
        self.assertEqual(payload["block"], "center")
        self.assertEqual(payload["top_before"], 1240)
        self.assertEqual(payload["top_after"], 450)

    def test_frame_tie_names_the_recorded_and_confirmed_elements(self):
        # A refusal has to say which two elements differed: tag, data-* ids,
        # normalized text prefix, rect top, and whether the node is connected.
        payload = self.node(
            r"""
const attrs = (id) => [{ name: 'data-block-id', value: id }, { name: 'class', value: 'layout-paragraph' }];
const el = (id, text, top, connected) => ({
  tagName: 'DIV',
  isConnected: connected,
  attributes: attrs(id),
  textContent: text,
  innerText: text,
  getBoundingClientRect: () => ({ top }),
  contains: () => false,
});
const recorded = el('block-5', 'custom namespace attribute: cs complex-script text', 480, false);
const confirmed = el('block-5', 'custom namespace attribute: cs complex-script text', 444.25, true);
const tie = mod.c12FrameTieDiagnostic(recorded, confirmed);
assert.equal(tie.recorded.tag, 'DIV');
assert.equal(tie.recorded.data['data-block-id'], 'block-5');
assert.equal(tie.recorded.text_prefix, 'custom namespace attribute: cs complex-script text');
assert.equal(tie.recorded.top, 480);
assert.equal(tie.recorded.isConnected, false);
assert.equal(tie.confirmed.tag, 'DIV');
assert.equal(tie.confirmed.data['data-block-id'], 'block-5');
assert.equal(tie.confirmed.top, 444.25);
assert.equal(tie.confirmed.isConnected, true);
assert.equal(tie.relation, 'distinct');
const child = el('block-5', 'custom namespace attribute: cs complex-script text', 444.25, true);
child.contains = (other) => other === recorded;
const wrapped = mod.c12FrameTieDiagnostic(child, recorded);
assert.equal(wrapped.relation, 'recorded_contains_confirmed');
console.log(JSON.stringify(tie));
"""
        )
        self.assertEqual(payload["recorded"]["tag"], "DIV")
        self.assertEqual(payload["recorded"]["data"]["data-block-id"], "block-5")
        self.assertFalse(payload["recorded"]["isConnected"])
        self.assertTrue(payload["confirmed"]["isConnected"])
        self.assertEqual(payload["recorded"]["text_prefix"], "custom namespace attribute: cs complex-script text")
        self.assertEqual(payload["relation"], "distinct")

    def test_same_anchor_accepts_a_replaced_block_and_a_wrapper(self):
        # Folio's recorded node is disconnected. The confirmed node is the
        # same paragraph: same data-block-id, same text, ProseMirror range
        # shifted. A node with no block id is not that paragraph. A child of
        # the confirmed node is.
        payload = self.node(
            r"""
const attrs = (pairs) => pairs.map(([name, value]) => ({ name, value }));
const el = (pairs, text, connected) => ({
  tagName: 'DIV',
  isConnected: connected,
  attributes: attrs(pairs),
  textContent: text,
  innerText: text,
  contains: () => false,
});
const text = 'Beta anchor paragraph stays';
const recorded = el(
  [['data-block-id', 'block-8'], ['data-para-id', '7A07F1B3'], ['data-pm-start', '208']],
  text,
  false,
);
const confirmed = el(
  [['data-block-id', 'block-8'], ['data-para-id', '7A07F1B3'], ['data-pm-start', '209']],
  text,
  true,
);
assert.equal(mod.c12SameAnchorElement(recorded, confirmed), true);
const other = el([['data-block-id', 'block-9'], ['data-para-id', 'OTHER']], text, true);
assert.equal(mod.c12SameAnchorElement(recorded, other), false);
const bareRecorded = el([], text, false);
const bareConfirmed = el([], text, true);
assert.equal(mod.c12SameAnchorElement(bareRecorded, bareConfirmed), false);
const bothLive = el([['data-block-id', 'block-8'], ['data-para-id', '7A07F1B3']], text, true);
assert.equal(mod.c12SameAnchorElement(bothLive, confirmed), false);
const child = el([['data-block-id', 'block-8'], ['data-para-id', '7A07F1B3']], text, true);
confirmed.contains = (other) => other === child;
assert.equal(mod.c12SameAnchorElement(child, confirmed), true);
const differentText = el([['data-block-id', 'block-8'], ['data-para-id', '7A07F1B3']], 'other paragraph', true);
assert.equal(mod.c12SameAnchorElement(recorded, differentText), false);
console.log(JSON.stringify({ replaced: true }));
"""
        )
        self.assertTrue(payload["replaced"])

    def test_census_record_keeps_the_caret_scroll(self):
        record = bd._c12_census_record(
            {
                "caret_scroll": {
                    "block": "center",
                    "inline": "nearest",
                    "behavior": "instant",
                    "top_before": 1240,
                    "top_after": 420,
                    "settle_ms": 800,
                },
                "before": {
                    "ok": False,
                    "anchorTop": 1244,
                    "viewportHeight": 900,
                    "caret_index": 7,
                    "anchor_index": 8,
                },
            }
        )
        self.assertEqual(record["caret_scroll"]["block"], "center")
        self.assertEqual(record["caret_scroll"]["top_after"], 420)
        self.assertEqual(record["caret_scroll"]["settle_ms"], 800)
        self.assertEqual(record["anchor_top"], 1244)
        self.assertEqual(record["viewport_height"], 900)

    def test_census_record_keeps_the_identity_diagnostic(self):
        record = bd._c12_census_record(
            {
                "identity_diagnostic": {
                    "failed": "b",
                    "window_from": 6,
                    "before_blocks": ["CARET", "ANCHOR"],
                    "after_blocks": ["CARET", "ANCHOR", "ANCHOR"],
                    "anchor_indexes_before": [10],
                    "anchor_indexes_after": [10, 20],
                },
                "before": {
                    "ok": True,
                    "caret_index": 9,
                    "anchor_index": 10,
                    "caret_paragraph_text": "CARET",
                    "anchor_text": "ANCHOR",
                },
            }
        )
        self.assertEqual(record["identity_diagnostic"]["window_from"], 6)
        self.assertEqual(record["identity_diagnostic"]["anchor_indexes_after"], [10, 20])
        self.assertEqual(record["caret_index"], 9)
        self.assertEqual(record["anchor_index"], 10)

    def test_caret_selection_names_the_census_block_and_offset(self):
        # window.getSelection before Enter: the anchor node's census index and
        # the offset inside that block. A node outside the census is described,
        # not dropped. No layout read.
        payload = self.node(
            r"""
let rects = 0;
function block(text) {
  const el = {
    nodeType: 1,
    tagName: 'DIV',
    textContent: text,
    parentNode: null,
    getBoundingClientRect: () => { rects += 1; return { top: 0, height: 20 }; },
  };
  const textNode = { nodeType: 3, textContent: text, parentNode: el, parentElement: el };
  el.firstChild = textNode;
  el.contains = (node) => {
    let cur = node;
    while (cur) {
      if (cur === el) return true;
      cur = cur.parentNode;
    }
    return false;
  };
  return { el, textNode };
}
function makeRange(anchorNode, anchorOffset) {
  const state = { endNode: anchorNode, endOffset: anchorOffset, block: null };
  return {
    cloneRange() { return makeRange(state.endNode, state.endOffset); },
    selectNodeContents(node) { state.block = node; },
    setEnd(node, off) { state.endNode = node; state.endOffset = off; },
    toString() {
      if (!state.block || !state.endNode) return '';
      if (state.endNode.nodeType === 3 && state.endNode.parentNode === state.block) {
        return String(state.endNode.textContent || '').slice(0, state.endOffset);
      }
      return state.endOffset > 0 ? String(state.block.textContent || '') : '';
    },
  };
}
const alpha = block('Alpha body paragraph here');
const beta = block('Beta anchor paragraph stays');
const entries = [
  { el: alpha.el, text: 'Alpha body paragraph here' },
  { el: beta.el, text: 'Beta anchor paragraph stays' },
];
globalThis.document = {
  getSelection() {
    return {
      rangeCount: 1,
      anchorNode: alpha.textNode,
      anchorOffset: 0,
      getRangeAt() { return makeRange(alpha.textNode, 0); },
    };
  },
};
const atStart = mod.c12CaretSelection(entries);
assert.equal(atStart.block_index, 0);
assert.equal(atStart.offset, 0);
assert.equal(atStart.text_prefix, 'Alpha body paragraph here');
globalThis.document = {
  getSelection() {
    return {
      rangeCount: 1,
      anchorNode: beta.textNode,
      anchorOffset: 4,
      getRangeAt() { return makeRange(beta.textNode, 4); },
    };
  },
};
const mid = mod.c12CaretSelection(entries);
assert.equal(mid.block_index, 1);
assert.equal(mid.offset, 4);
const hidden = block('hidden editor surface');
const attrs = [{ name: 'data-paragraph-id', value: 'p-hidden' }];
hidden.el.attributes = attrs;
hidden.el.getAttribute = (name) => (name === 'data-paragraph-id' ? 'p-hidden' : '');
globalThis.document = {
  getSelection() {
    return {
      rangeCount: 1,
      anchorNode: hidden.textNode,
      anchorOffset: 0,
      getRangeAt() { return makeRange(hidden.textNode, 0); },
    };
  },
};
const outside = mod.c12CaretSelection(entries);
assert.equal(outside.block_index, null);
assert.equal(outside.anchor.tag, 'DIV');
assert.equal(outside.anchor.data['data-paragraph-id'], 'p-hidden');
assert.equal(outside.anchor.text_prefix, 'hidden editor surface');
assert.equal(rects, 0, 'rect reads ' + rects);
console.log(JSON.stringify({ atStart, mid, outside, rects }));
"""
        )
        self.assertEqual(payload["atStart"]["block_index"], 0)
        self.assertEqual(payload["atStart"]["offset"], 0)
        self.assertEqual(payload["mid"]["block_index"], 1)
        self.assertEqual(payload["mid"]["offset"], 4)
        self.assertIsNone(payload["outside"]["block_index"])
        self.assertEqual(payload["outside"]["anchor"]["tag"], "DIV")
        self.assertEqual(payload["rects"], 0)

    def test_empty_inclusive_window_keeps_paragraphs_the_census_drops(self):
        # The identity window keeps an empty paragraph the census skipped, and
        # marks it with a null census index. Headings still drop. No layout read.
        payload = self.node(
            r"""
let rects = 0;
const para = (text) => ({
  textContent: text,
  innerText: text,
  classList: { contains: () => false },
  getBoundingClientRect: () => { rects += 1; return { top: 0, height: 20 }; },
});
const nodes = [para('Article 1. Title of the agreement')];
for (let i = 0; i < 8; i += 1) nodes.push(para('Filler paragraph ' + i + ' stays here'));
nodes.push(para(''));
nodes.push(para('Alpha body paragraph here'));
nodes.push(para(''));
nodes.push(para('Beta anchor paragraph stays'));
nodes.push(para('Gamma tail paragraph after'));
const serve = (query) => (query === '.docx-paragraph-fragment' || query === '.doc-paragraph' ? nodes : []);
globalThis.document = { querySelectorAll: serve };
const snapshot = { caretIndex: 8, anchorIndex: 9 };
const win = mod.c12EmptyInclusiveWindow('eigenpal', '.doc-paragraph', '', snapshot);
assert.equal(win.from, 5);
const rows = win.rows;
const alphaAt = rows.findIndex((row) => row.text_prefix === 'Alpha body paragraph here');
assert.ok(alphaAt > 0, JSON.stringify(rows));
assert.equal(rows[alphaAt].census_index, 8);
assert.equal(rows[alphaAt].empty, false);
assert.equal(rows[alphaAt + 1].empty, true);
assert.equal(rows[alphaAt + 1].census_index, null);
assert.equal(rows[alphaAt + 2].text_prefix, 'Beta anchor paragraph stays');
assert.equal(rows[alphaAt + 2].census_index, 9);
assert.equal(rows.some((row) => String(row.text_prefix || '').startsWith('Article')), false);
assert.equal(rects, 0, 'rect reads ' + rects);
globalThis.document = { querySelectorAll: (query) => (query === '.doc-paragraph' ? nodes : []) };
const plain = mod.c12EmptyInclusiveWindow('', '.doc-paragraph', '', snapshot);
assert.equal(plain.rows[plain.rows.findIndex((row) => row.census_index === 8) + 1].census_index, null);
console.log(JSON.stringify({ from: win.from, rows, rects }));
"""
        )
        rows = payload["rows"]
        alpha = next(row for row in rows if row["text_prefix"] == "Alpha body paragraph here")
        self.assertEqual(alpha["census_index"], 8)
        gap = rows[rows.index(alpha) + 1]
        self.assertTrue(gap["empty"])
        self.assertIsNone(gap["census_index"])
        self.assertEqual(payload["rects"], 0)

    def test_census_record_keeps_the_caret_selection_and_empty_window(self):
        record = bd._c12_census_record(
            {
                "before": {
                    "caret_index": 9,
                    "anchor_index": 10,
                    "caret_paragraph_text": "CARET",
                    "anchor_text": "ANCHOR",
                    "caret_selection": {"block_index": 10, "offset": 0, "text_prefix": "ANCHOR"},
                },
                "empty_inclusive_window": {
                    "from": 6,
                    "rows": [{"text_prefix": "", "empty": True, "census_index": None}],
                },
            }
        )
        self.assertEqual(record["caret_selection"]["block_index"], 10)
        self.assertEqual(record["caret_selection"]["offset"], 0)
        self.assertIsNone(record["empty_inclusive_window"]["rows"][0]["census_index"])

    def test_census_record_keeps_the_frame_tie(self):
        record = bd._c12_census_record(
            {
                "frame_tie": {
                    "relation": "distinct",
                    "recorded": {
                        "tag": "DIV",
                        "data": {"data-block-id": "block-5"},
                        "text_prefix": "custom namespace",
                        "top": 480,
                        "isConnected": False,
                    },
                    "confirmed": {
                        "tag": "DIV",
                        "data": {"data-block-id": "block-5"},
                        "text_prefix": "custom namespace",
                        "top": 444.25,
                        "isConnected": True,
                    },
                },
                "before": {
                    "ok": True,
                    "caret_index": 4,
                    "anchor_index": 5,
                    "caret_paragraph_text": "CARET",
                    "anchor_text": "ANCHOR",
                },
            }
        )
        self.assertEqual(record["frame_tie"]["recorded"]["tag"], "DIV")
        self.assertEqual(record["frame_tie"]["recorded"]["data"]["data-block-id"], "block-5")
        self.assertFalse(record["frame_tie"]["recorded"]["isConnected"])
        self.assertTrue(record["frame_tie"]["confirmed"]["isConnected"])
        self.assertEqual(record["frame_tie"]["confirmed"]["top"], 444.25)

    def test_untied_code_refuses_the_sample(self):
        from perf.runner.refusals import RefusalCode

        code = "recorded_frame_not_confirmed_anchor"
        self.assertIn(code, {item.value for item in RefusalCode})
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(
                {
                    "error": code,
                    "moved": True,
                    "mode": "reflow",
                    "presented_frame_ms": 20,
                    "layout_reads_during_window": 1,
                    "forced_layout_ms": 0.1,
                    "anchor_frames": 1,
                    "window_excludes_forced_layout": False,
                }
            )
        self.assertEqual(caught.exception.refusal_code, code)

    def test_move_before_enter_or_no_anchor_frame_is_not_a_sample(self):
        # A published row is the Enter reflow. A frame stamped before the
        # keydown, or a window with no anchor frame, is not that row.
        witness = publishable_witness_record(40.0, 20.0)
        base = {
            "mode": "reflow",
            "moved": True,
            "window_excludes_forced_layout": False,
            "before": {"anchor_top": 100.0},
            "anchor_top_after": 520.0,
            "presented_frame_ms": 16.0,
            "input_page_ms": 1000.0,
            "observed_shift_page_ms": 1016.0,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "layout_reads_during_window": 1,
            "forced_layout_ms": 0.05,
            "anchor_frames": 1,
            "witness": witness,
        }
        early = dict(base, observed_shift_page_ms=990.0)
        with self.assertRaises(bd.ProbeRefusal) as early_caught:
            bd.c12_measured_sample(early)
        self.assertIn("precedes Enter", early_caught.exception.reason)
        empty = dict(base, anchor_frames=0, layout_reads_during_window=0)
        with self.assertRaises(bd.ProbeRefusal) as empty_caught:
            bd.c12_measured_sample(empty)
        self.assertIn("no anchor frame", empty_caught.exception.reason)
        self.assertEqual(bd.c12_measured_sample(base), 16.0)

    def test_hidden_pm_reader_returns_the_full_paragraph(self):
        # Folio's hidden editor must name the paragraph it measured. An
        # 80-character prefix that the next paragraph shares is a different
        # paragraph. The check is the same one the DOM reader uses.
        prefix = "Shared prefix paragraph that runs well past eighty characters so nobody can tell them apart "
        wrong = prefix + "WRONG paragraph the click actually owns"
        right = prefix + "RIGHT paragraph the fixture caret is"
        self.assertGreater(len(prefix), 80)
        payload = self.node(
            r"""
const surface = await import(%s);
const prefix = %s;
const wrong = prefix + 'WRONG paragraph the click actually owns';
const right = prefix + 'RIGHT paragraph the fixture caret is';
const block = {
  innerText: wrong,
  textContent: wrong,
  closest() { return block; },
};
const textNode = { nodeType: 3, parentNode: block };
const range = {
  startContainer: textNode,
  startOffset: 0,
  cloneRange() {
    return { selectNodeContents() {}, setEnd() {}, toString() { return ''; } };
  },
};
const pm = {
  contains(node) { return node === block || node === textNode; },
  focus() {},
  querySelectorAll() { return [block]; },
};
const body = {};
const root = {};
globalThis.document = {
  body,
  documentElement: root,
  activeElement: { tagName: 'DIV' },
  querySelector(sel) { return String(sel).includes('ProseMirror') ? pm : null; },
  getSelection() { return { rangeCount: 1, getRangeAt() { return range; } }; },
};
const read = surface.READ_CARET_BLOCK_OFFSET({ editorId: 'folio', blockSelector: '[data-block-id]' });
assert.equal(read.source, 'hidden_pm');
assert.equal(read.offset, 0);
assert.equal(read.paragraphText, wrong);
const page = {
  async evaluate(fn, arg) { return typeof fn === 'function' ? fn(arg) : undefined; },
  async waitForTimeout() {},
  async waitForFunction() {},
};
const verdict = await surface.verifyCaretAtParagraphStart(page, 'folio', {
  expectedParagraphText: right,
  clickPoint: { x: 12, y: 24 },
});
assert.equal(verdict.ok, false);
assert.equal(verdict.detail, 'paragraph_text_mismatch');
assert.equal(verdict.paragraphText, wrong);
console.log(JSON.stringify({ offset: read.offset, paragraphText: read.paragraphText, detail: verdict.detail }));
"""
            % (json.dumps(str(SURFACE)), json.dumps(prefix))
        )
        self.assertEqual(payload["detail"], "paragraph_text_mismatch")
        self.assertEqual(payload["paragraphText"], wrong)
        self.assertEqual(wrong[:80], right[:80])
        self.assertNotEqual(wrong, right)

    @unittest.skipUnless(_node() and _playwright_ready(), "node+playwright required")
    def test_late_click_is_not_overwritten_by_the_old_paragraph(self):
        # SuperDoc applies the pointer gesture after pointerup. Re-applying the
        # snapshot from before that gesture puts the caret back on the heading.
        playwright = REPO / "harness" / "ui" / "node_modules" / "playwright" / "index.js"
        script = r"""
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require(%s);
const surface = await import(%s);
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
try {
  await page.setContent(`<!doctype html><body>
    <div id="editor">
      <div class="superdoc-line" data-source-node-id="H" style="padding:20px">HEADING stays</div>
      <div class="superdoc-line" data-source-node-id="B" style="padding:20px">BODY paragraph start</div>
    </div>
    <textarea data-v2-ime-host></textarea>
    <script>
      const state = { blockId: 'H', offset: 4, quoted: 'HEADING stays' };
      let pending = null;
      window.__cancelled = false;
      window.__SUPERDOC_E2E__ = { ui: { selection: {
        getSnapshot() {
          return {
            quotedText: state.quoted,
            selectionTarget: {
              start: { blockId: state.blockId, offset: state.offset, edge: 'start', kind: 'text' },
              end: { blockId: state.blockId, offset: state.offset, edge: 'start', kind: 'text' },
              story: { kind: 'story', storyType: 'body' },
            },
          };
        },
        apply(cmd) {
          if (pending) { clearTimeout(pending); pending = null; window.__cancelled = true; }
          state.blockId = cmd.start.blockId;
          state.offset = cmd.start.offset;
          state.quoted = state.blockId === 'B' ? 'BODY paragraph start' : 'HEADING stays';
        },
      } } };
      document.addEventListener('pointerdown', () => {
        const ime = document.querySelector('textarea');
        if (ime) ime.focus();
      }, true);
      document.addEventListener('pointerup', (event) => {
        const hit = document.elementFromPoint(event.clientX, event.clientY);
        const line = hit && hit.closest ? hit.closest('.superdoc-line') : null;
        if (!line || line.getAttribute('data-source-node-id') !== 'B') return;
        pending = setTimeout(() => {
          pending = null;
          state.blockId = 'B';
          state.offset = 0;
          state.quoted = 'BODY paragraph start';
        }, 700);
      }, true);
    </script>
  </body>`);
  const box = await page.locator('[data-source-node-id="B"]').boundingBox();
  assert.ok(box);
  await surface.placeCaret(page, 'superdoc', '.superdoc-line', {
    clickPoint: { x: box.x + 8, y: box.y + 8 },
    atBlockStart: true,
    blockSelector: '.superdoc-line',
    focusTimeoutMs: 150,
  });
  const read = await page.evaluate(surface.READ_CARET_BLOCK_OFFSET, {
    editorId: 'superdoc',
    blockSelector: '.superdoc-line',
  });
  const cancelled = await page.evaluate(() => window.__cancelled === true);
  assert.equal(read.paragraphText, 'BODY paragraph start');
  assert.equal(read.offset, 0);
  assert.equal(cancelled, false);
  console.log(JSON.stringify({ offset: read.offset, paragraphText: read.paragraphText, cancelled }));
} finally {
  await browser.close();
}
""" % (
            json.dumps(str(playwright)),
            json.dumps(str(SURFACE)),
        )
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["paragraphText"], "BODY paragraph start")
        self.assertFalse(payload["cancelled"])

    def node(self, body: str) -> dict:
        script = """
import assert from 'node:assert/strict';
const mod = await import(%s);
%s
""" % (
            json.dumps(str(LANE)),
            body,
        )
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)


@unittest.skipUnless(_node() and _playwright_ready(), "node+playwright required")
class RerenderHosts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (REPO / ".scratch" / "tmp").mkdir(parents=True, exist_ok=True)
        cls.server_mod = _load_server()
        cls.server, _thread, cls.base_url = cls.server_mod.serve(HOSTS)
        cls._corpus_dir = tempfile.TemporaryDirectory(dir=REPO / ".scratch" / "tmp")
        cls.corpus = Path(cls._corpus_dir.name) / "corpus.docx"
        cls.corpus.write_bytes(b"PK\x03\x04r3c12j")

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.shutdown()
            cls.server.server_close()
        cls._corpus_dir.cleanup()

    def _reflow(self, host_file: str, timeout_ms: int = 20000, extra: list | None = None) -> dict:
        cmd = [
            _node(),
            str(PROBE),
            "--mode",
            "reflow",
            "--url",
            "%s/%s" % (self.base_url, host_file),
            "--corpus",
            str(self.corpus),
            "--doc-selector",
            ".doc-paragraph",
            "--page-model",
            "continuous_flow",
            "--edit-selector",
            ".doc-paragraph",
            "--timeout-ms",
            str(timeout_ms),
        ]
        if extra:
            cmd.extend(extra)
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=TIMEOUT_S)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        return json.loads(proc.stdout)

    def test_rerender_sample_is_the_enter_move_not_the_text_commit(self):
        payload = self._reflow("rerender.html")
        self.assertIsNone(payload.get("error"), payload)
        self.assertTrue(payload.get("moved"), payload)
        shift_after_input = payload["observed_shift_page_ms"] - payload["input_page_ms"]
        self.assertLess(shift_after_input, 100, payload)
        self.assertLess(payload["presented_frame_ms"], 100, payload)
        self.assertEqual(bd.c12_measured_sample(payload), payload["presented_frame_ms"])

    def test_rerender_layout_reads_are_not_the_block_count(self):
        payload = self._reflow("rerender-many.html")
        self.assertIsNone(payload.get("error"), payload)
        self.assertTrue(payload.get("moved"), payload)
        blocks = payload.get("block_count_before")
        reads = payload.get("layout_reads_during_window")
        frames = payload.get("anchor_frames")
        self.assertGreaterEqual(blocks, 40, payload)
        self.assertGreaterEqual(frames, 1, payload)
        self.assertLessEqual(reads, frames * READS_PER_FRAME, payload)
        self.assertLess(reads, blocks, payload)
        self.assertLess(payload["presented_frame_ms"], 100, payload)

    def test_clock_stays_about_one_frame(self):
        payload = self._reflow("clock.html")
        self.assertIsNone(payload.get("error"), payload)
        self.assertTrue(payload.get("moved"), payload)
        self.assertLess(payload["presented_frame_ms"], 100, payload)
        self.assertEqual(bd.c12_measured_sample(payload), payload["presented_frame_ms"])

    def test_stale_never_and_duplicate_hosts_keep_their_results(self):
        stale = self._reflow("stale.html")
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(stale)
        self.assertIsNot(stale.get("moved"), True, stale)
        self.assertTrue(
            "anchor_identity_ambiguous" in caught.exception.reason or "did not move down" in caught.exception.reason,
            caught.exception.reason,
        )

        never = self._reflow("never.html", timeout_ms=2000)
        self.assertEqual(never.get("error"), "edit_not_observed", never)
        with self.assertRaises(bd.ProbeRefusal) as never_caught:
            bd.c12_measured_sample(never)
        self.assertEqual(never_caught.exception.refusal_code, "edit_not_observed")

        dup_anchor = self._reflow("b3_fixdoc3_dup_anchor.html")
        self.assertEqual(dup_anchor.get("error"), "anchor_identity_ambiguous", dup_anchor)
        self.assertNotIsInstance(dup_anchor.get("anchor_top_after"), (int, float), dup_anchor)
        self.assertFalse(dup_anchor.get("moved"), dup_anchor)

        dup = self._reflow("b3_fixdoc3_dup_rerender.html")
        before = (dup.get("before") or {}).get("anchor_top")
        after = dup.get("anchor_top_after")
        self.assertIsInstance(before, (int, float), dup)
        self.assertIsInstance(after, (int, float), dup)
        self.assertGreater(after, before, dup)
        self.assertTrue(dup.get("moved"), dup)
        self.assertEqual((dup.get("before") or {}).get("anchor_occurrence"), 1)
        self.assertIsInstance(bd.c12_measured_sample(dup), float)

    def test_offscreen_anchor_is_scrolled_before_the_snapshot(self):
        payload = self._reflow(
            "offscreen.html",
            extra=[
                "--c12-caret-text",
                "Alpha body paragraph here",
                "--c12-anchor-text",
                "Beta anchor paragraph stays",
            ],
        )
        self.assertNotIn("off the viewport", str(payload.get("error")), payload)
        scroll = payload.get("caret_scroll") or {}
        self.assertEqual(scroll.get("block"), "center", payload)
        self.assertEqual(scroll.get("inline"), "nearest", payload)
        self.assertEqual(scroll.get("behavior"), "instant", payload)
        self.assertIsInstance(scroll.get("top_before"), (int, float), payload)
        self.assertIsInstance(scroll.get("top_after"), (int, float), payload)
        before = payload.get("before") or {}
        self.assertIsInstance(before.get("anchor_top"), (int, float), payload)
        self.assertLess(before["anchor_top"], 900, payload)
        self.assertIsNone(payload.get("error"), payload)
        self.assertTrue(payload.get("moved"), payload)
        self.assertEqual(bd.c12_measured_sample(payload), payload["presented_frame_ms"])

    def test_recorded_frame_must_be_the_confirmed_anchor(self):
        payload = self._reflow("untied.html")
        self.assertEqual(payload.get("error"), "recorded_frame_not_confirmed_anchor", payload)
        self.assertIsNot(payload.get("moved"), True, payload)
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(payload)
        self.assertEqual(caught.exception.refusal_code, "recorded_frame_not_confirmed_anchor")

    def test_recorded_frame_refusal_names_both_elements(self):
        payload = self._reflow("untied.html")
        self.assertEqual(payload.get("error"), "recorded_frame_not_confirmed_anchor", payload)
        tie = payload.get("frame_tie") or {}
        for side in ("recorded", "confirmed"):
            element = tie.get(side) or {}
            self.assertIsInstance(element.get("tag"), str, payload)
            self.assertIsInstance(element.get("data"), dict, payload)
            self.assertTrue(str(element.get("text_prefix") or "").startswith("Beta anchor"), payload)
            self.assertIsInstance(element.get("top"), (int, float), payload)
            self.assertIsInstance(element.get("isConnected"), bool, payload)
        self.assertIs(tie["recorded"]["isConnected"], False, payload)
        self.assertIs(tie["confirmed"]["isConnected"], True, payload)
        self.assertIsNot(payload.get("moved"), True, payload)

    def test_folio_replacement_of_the_same_block_is_measured(self):
        payload = self._reflow("folio-replace.html")
        self.assertIsNone(payload.get("error"), payload)
        self.assertTrue(payload.get("moved"), payload)
        self.assertLess(payload["presented_frame_ms"], 100, payload)
        self.assertEqual(bd.c12_measured_sample(payload), payload["presented_frame_ms"])

    def test_placed_caret_selection_is_the_census_caret_paragraph(self):
        payload = self._reflow("rerender.html")
        before = payload.get("before") or {}
        selection = before.get("caret_selection") or {}
        self.assertEqual(selection.get("block_index"), before.get("caret_index"), payload)
        self.assertEqual(selection.get("offset"), 0, payload)
        self.assertTrue(str(selection.get("text_prefix") or "").startswith("Alpha body"), payload)

    def test_caret_in_another_paragraph_is_refused(self):
        # The click point sits on the caret paragraph, and a later paragraph
        # covers that point. Offset 0 in the covering paragraph is not the
        # caret paragraph. Same check for every editor.
        payload = self._reflow("wrong-paragraph.html")
        self.assertEqual(payload.get("error"), "caret_not_at_paragraph_start", payload)
        verify = (payload.get("caret_placement") or {}).get("caret_verify") or {}
        self.assertEqual(verify.get("detail"), "paragraph_text_mismatch", payload)
        self.assertEqual(verify.get("offset"), 0, payload)

    def test_glyph_rect_places_the_caret_when_the_block_corner_is_the_next_paragraph(self):
        # The caret block's top-left belongs to the next paragraph. The caret
        # paragraph's own first character does not. Placement has to land on
        # that character, and the paragraph-text check still applies.
        payload = self._reflow("block-corner.html")
        self.assertIsNone(payload.get("error"), payload)
        before = payload.get("before") or {}
        selection = before.get("caret_selection") or {}
        self.assertEqual(selection.get("offset"), 0, payload)
        self.assertEqual(selection.get("block_index"), before.get("caret_index"), payload)
        self.assertTrue(str(selection.get("text_prefix") or "").startswith("Alpha body"), payload)
        self.assertTrue(payload.get("moved"), payload)
        self.assertEqual(bd.c12_measured_sample(payload), payload["presented_frame_ms"])

    def test_identity_refusal_keeps_the_empty_paragraph_in_the_window(self):
        payload = self._reflow("empty-gap.html", timeout_ms=2500)
        self.assertEqual(payload.get("error"), "anchor_identity_ambiguous", payload)
        rows = (payload.get("empty_inclusive_window") or {}).get("rows") or []
        indexes = [row.get("census_index") for row in rows]
        self.assertIn(None, indexes, payload)
        gap_at = indexes.index(None)
        self.assertGreater(gap_at, 0, payload)
        self.assertIsNotNone(indexes[gap_at - 1], payload)
        self.assertLess(gap_at + 1, len(indexes), payload)
        self.assertIsNotNone(indexes[gap_at + 1], payload)
        self.assertIs(rows[gap_at].get("empty"), True, payload)

    def test_move_recorded_before_enter_is_refused(self):
        # The anchor moves when the recorder arms. Enter moves nothing.
        # That frame is not the Enter reflow.
        payload = self._reflow("pre-enter-move.html")
        self.assertEqual(payload.get("error"), "recorded_move_before_input", payload)
        self.assertIsNot(payload.get("moved"), True, payload)
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(payload)
        self.assertEqual(caught.exception.refusal_code, "recorded_move_before_input")

    def test_shared_prefix_is_not_the_caret_paragraph(self):
        # The covering paragraph shares the first 80 characters and nothing
        # else. Offset 0 there is still the wrong paragraph, and the refusal
        # is the caret check, not a later identity timeout.
        started = time.monotonic()
        payload = self._reflow("same-prefix.html")
        elapsed = time.monotonic() - started
        self.assertEqual(payload.get("error"), "caret_not_at_paragraph_start", payload)
        verify = (payload.get("caret_placement") or {}).get("caret_verify") or {}
        self.assertEqual(verify.get("detail"), "paragraph_text_mismatch", payload)
        self.assertEqual(verify.get("offset"), 0, payload)
        self.assertNotEqual(verify.get("paragraphText"), verify.get("expected"), payload)
        self.assertLess(elapsed, 8, payload)

    def test_late_move_census_stays_outside_the_window(self):
        # The anchor moves 250 ms after Enter. The confirm census waits for
        # that frame. In-window reads stay at the recorder's one rect per
        # frame, for both hosts, including the one whose x commits early.
        for host in ("late250-many.html", "late250-fastx-many.html"):
            payload = self._reflow(host)
            self.assertIsNone(payload.get("error"), payload)
            self.assertTrue(payload.get("moved"), payload)
            frames = payload.get("anchor_frames")
            reads = payload.get("layout_reads_during_window")
            self.assertGreaterEqual(frames, 1, payload)
            self.assertLessEqual(reads, frames * READS_PER_FRAME, (host, payload))
            self.assertEqual(bd.c12_measured_sample(payload), payload["presented_frame_ms"])


if __name__ == "__main__":
    unittest.main()
