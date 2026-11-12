"""r3c12h: C12 clock, anchor node and census fixes (issue #161).

Each acceptance criterion executes the reviewer's counterexample hosts from
``perf/tests/fixtures/hosts`` (copied unchanged from the r3c12v2 review) or a
node-level contract against ``lane_edit_burst.mjs`` — never a source grep.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import perf.runner.benchmark_document as bd

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"
LANE = REPO / "perf" / "runner" / "lane_edit_burst.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
WITNESS_SERVER = REPO / "perf" / "tests" / "fixtures" / "witness" / "server.py"
TIMEOUT_S = 90


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

    spec = importlib.util.spec_from_file_location("r3c12h_fixture_server", WITNESS_SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FixtureParagraphPair(unittest.TestCase):
    def test_pair_is_the_first_non_heading_body_and_the_next(self):
        from perf.fixtures.docx_workload import workload_for_lane
        from perf.runner.benchmark_document import c12_fixture_body_pair

        prose = workload_for_lane("prose-500w", "document")["docx"]
        caret, anchor = c12_fixture_body_pair(prose)
        self.assertTrue(caret.startswith("In property property each"), caret)
        self.assertTrue(anchor.startswith("Director partial connection"), anchor)
        corpus = workload_for_lane("complex-corpus", "document")["docx"]
        caret, anchor = c12_fixture_body_pair(corpus)
        self.assertEqual(caret, "Leading and trailing spaces are significant.")
        # w:noBreakHyphen, w:softHyphen and the Wingdings check are part of the
        # paragraph plate paints. A w:t-only join is a different string.
        self.assertEqual(
            anchor,
            "Tab separatedAfter a page break\u2011nobreak\u00adsofthyphen\u2713symafter CR",
        )

    def test_one_body_paragraph_is_not_a_pair(self):
        from perf.runner.benchmark_document import c12_fixture_body_pair, docx_paragraph_bytes

        raw = docx_paragraph_bytes(b"Only one body paragraph\n")
        with self.assertRaises(bd.ProbeRefusal) as caught:
            c12_fixture_body_pair(raw)
        self.assertEqual(caught.exception.refusal_code, "fixture_body_pair_absent")


class NodeContract(unittest.TestCase):
    def test_later_refind_success_clears_a_refusal_from_an_earlier_frame(self):
        # The frame recorder calls REFIND_ANCHOR on the Enter that replaces the
        # anchor, before the caret "x" exists. That call must not leave a
        # refusal that the successful refind, once "x" has landed, cannot clear.
        # Otherwise endIdentity refuses anchor_identity_ambiguous after the move
        # was already recorded (b3_fixdoc3_dup_rerender.html).
        payload = self.node(
            r"""
globalThis.window = globalThis;
const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const box = (top) => ({ top, bottom: top + 20, left: 0, height: 20, width: 400 });
const block = (text, top) => ({
  innerText: text,
  textContent: text,
  isConnected: true,
  getBoundingClientRect: () => box(top),
});
const caret = block('Alpha opening line of the document.', 24);
const replaced = block('Beta shared anchor line for C12.', 119);
const duplicate = block('Beta shared anchor line for C12.', 180);
globalThis.document = { querySelectorAll: () => [caret, replaced, duplicate] };
window.__c12EditorId = '';
window.__c12ExcludeSel = '';
window.__c12BeforeSnapshot = {
  blockTexts: [
    'Alpha opening line of the document.',
    'Beta shared anchor line for C12.',
    'Beta shared anchor line for C12.',
  ],
  caretIndex: 0,
  anchorIndex: 1,
  anchorText: 'Beta shared anchor line for C12.',
};
window.__c12AnchorEl = { isConnected: false, innerText: 'Beta shared anchor line for C12.', textContent: 'Beta shared anchor line for C12.' };
window.__c12AnchorRefusal = null;
const args = ['.doc-paragraph', 'Beta shared anchor line for C12.', 59, norm, null, 1];
const beforeX = mod.REFIND_ANCHOR(...args);
assert.equal(beforeX, null);
assert.equal(window.__c12AnchorRefusal, 'anchor_identity_ambiguous');
caret.innerText = 'xAlpha opening line of the document.';
caret.textContent = caret.innerText;
const afterX = mod.REFIND_ANCHOR(...args);
assert.equal(afterX, replaced);
assert.equal(window.__c12AnchorRefusal, null);
console.log(JSON.stringify({ refusal: window.__c12AnchorRefusal, found: afterX === replaced }));
"""
        )
        self.assertIsNone(payload["refusal"])
        self.assertTrue(payload["found"])

    def test_fixture_strings_locate_the_caret_and_anchor(self):
        # complex-corpus on docxodus and eigenpal censuses "Default header" / "1"
        # as indexes 0 and 1. The caret and anchor are the fixture's first
        # non-heading body paragraph and the body paragraph after it.
        payload = self.node(
            r"""
const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const entries = [
  { text: 'Default header', top: 0 },
  { text: '1', top: 20 },
  { text: 'Leading and trailing spaces are significant.', top: 80 },
  { text: 'Tab separatedAfter a page break', top: 110 },
];
const pick = mod.c12LocateFixtureParagraphs(
  entries,
  'Leading and trailing spaces are significant.',
  'Tab separatedAfter a page break',
  norm,
);
console.log(JSON.stringify(pick));
assert.equal(pick.ok, true, JSON.stringify(pick));
assert.equal(pick.caretIndex, 2);
assert.equal(pick.anchorIndex, 3);
const missing = mod.c12LocateFixtureParagraphs(entries, 'not in the census', 'Tab separatedAfter a page break', norm);
assert.equal(missing.ok, false);
assert.equal(missing.reason, 'fixture_paragraph_not_in_census');
"""
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["caretIndex"], 2)
        self.assertEqual(payload["anchorIndex"], 3)

    def test_superdoc_wrapped_paragraph_uses_one_text_function(self):
        # Two lines 20px apart are one paragraph. The census stores the join.
        # The identity re-read must return that same string from either line.
        # A line 80px below the previous one is the next paragraph.
        payload = self.node(
            r"""
const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const line = (text, top) => ({
  textContent: text,
  innerText: text,
  classList: { contains: (name) => name === 'superdoc-line' },
  getAttribute: () => '',
  closest: () => null,
  getBoundingClientRect: () => ({ top, bottom: top + 18, left: 40, height: 18, width: 400 }),
});
const wrappedA = line('In property property each completion indirect tax', 80);
const wrappedB = line('wrapped onto the next laid-out line of the same paragraph', 100);
const next = line('Director partial connection timely also respect.', 180);
const lines = [wrappedA, wrappedB, next];
globalThis.document = { querySelectorAll: () => lines };
globalThis.window = globalThis;
const expected = norm(wrappedA.textContent + ' ' + wrappedB.textContent);
const read = (block) => mod.C12_BLOCK_TEXT(block, norm);
const entries = mod.c12BlockEntries('superdoc', '#editor .superdoc-line', '', read);
const reread = mod.C12_BLOCK_TEXT(entries[0].el, norm);
const sibling = mod.C12_BLOCK_TEXT(wrappedB, norm);
console.log(JSON.stringify({
  count: entries.length,
  census: entries[0].text,
  reread,
  sibling,
  next: mod.C12_BLOCK_TEXT(next, norm),
}));
assert.equal(entries.length, 2);
assert.equal(entries[0].text, expected);
assert.equal(reread, expected);
assert.equal(sibling, expected);
assert.equal(mod.C12_BLOCK_TEXT(next, norm), next.textContent);
const pageFn = eval(mod.C12_BLOCK_TEXT_PAGE_SRC);
assert.equal(typeof pageFn, 'function');
assert.equal(pageFn(wrappedB, norm), expected);
assert.equal(pageFn(next, norm), next.textContent);
const collect = (0, eval)(`(function(){ ${mod.C12_BLOCK_ENTRIES_PAGE_SRC}; return c12BlockEntries; })()`);
const viaPage = collect('superdoc', '#editor .superdoc-line', '', read);
assert.equal(viaPage.length, 2);
assert.equal(viaPage[0].text, expected);
const pageReread = pageFn(viaPage[0].el, norm);
assert.equal(pageReread, expected);
"""
        )
        expected = (
            "In property property each completion indirect tax "
            "wrapped onto the next laid-out line of the same paragraph"
        )
        self.assertEqual(payload["census"], expected)
        self.assertEqual(payload["reread"], expected)
        self.assertEqual(payload["sibling"], expected)

    def node(self, body: str, module: Path | None = None) -> dict:
        script = """
import assert from 'node:assert/strict';
const mod = await import(%s);
%s
""" % (
            json.dumps(str(module or LANE)),
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
class ReflowProbeHosts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_mod = _load_server()
        cls.server, _thread, cls.base_url = cls.server_mod.serve(HOSTS)
        cls._corpus_dir = tempfile.TemporaryDirectory(dir=REPO / ".scratch" / "tmp")
        cls.corpus = Path(cls._corpus_dir.name) / "corpus.docx"
        cls.corpus.write_bytes(b"PK\x03\x04r3c12h")

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.shutdown()
            cls.server.server_close()
        cls._corpus_dir.cleanup()

    def _reflow(self, host_file: str, timeout_ms: int = 20000, extra: list[str] | None = None) -> dict:
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
            *(extra or []),
        ]
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=TIMEOUT_S)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    # Item 1, BLOCKER 2: the sample is Enter keydown -> first presented frame
    # in which the anchor moved. The anchor moves immediately; the caret text
    # (and therefore the edit confirmation) lands 1.6 s later, so a sample that
    # includes the confirm wait is ~1.6 s or worse. About one frame is < 500 ms.
    def test_clock_sample_is_enter_to_first_moved_frame_not_the_confirm(self):
        payload = self._reflow("clock.html")
        self.assertIsNone(payload.get("error"), payload)
        self.assertTrue(payload.get("moved"), payload)
        shift_after_input = payload["observed_shift_page_ms"] - payload["input_page_ms"]
        self.assertLess(shift_after_input, 500, payload)
        self.assertLess(payload["presented_frame_ms"], 500, payload)
        self.assertEqual(bd.c12_measured_sample(payload), payload["presented_frame_ms"])

    # Item 1: layout reads inside the measured window are counted, not hidden.
    def test_in_window_layout_reads_are_reported_not_claimed_absent(self):
        payload = self._reflow("clock.html")
        self.assertIsNone(payload.get("error"), payload)
        reads = payload.get("layout_reads_during_window")
        forced = payload.get("forced_layout_ms")
        frames = payload.get("anchor_frames")
        self.assertIsInstance(reads, int, payload)
        self.assertIsInstance(forced, (int, float), payload)
        self.assertIsInstance(frames, int, payload)
        self.assertGreaterEqual(frames, 1, payload)
        # Every recorded frame performed an anchor-top read; nothing uncounted.
        self.assertGreaterEqual(reads, frames, payload)
        self.assertFalse(payload.get("window_excludes_forced_layout"), payload)

    # Item 2, BLOCKER 1. stale.html keeps the old anchor connected, with the
    # same text, strips .doc-paragraph, and moves that orphan to top 700px.
    # The census paragraph with the anchor text stays at 60px. A measured
    # sample is the orphan, not the anchor.
    def test_stale_orphan_is_not_a_measured_anchor(self):
        payload = self._reflow("stale.html")
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(payload)
        self.assertIsNot(payload.get("moved"), True, payload)
        self.assertTrue(
            "anchor_identity_ambiguous" in caught.exception.reason or "did not move down" in caught.exception.reason,
            caught.exception.reason,
        )

    # Item 3, BLOCKER 3. never.html swallows Enter and x. The confirm wait
    # times out on an unchanged census. That is edit_not_observed, not an
    # ambiguous anchor.
    def test_never_edit_times_out_as_edit_not_observed(self):
        payload = self._reflow("never.html", timeout_ms=2000)
        self.assertEqual(payload.get("error"), "edit_not_observed", payload)
        self.assertIsNone(payload.get("presented_frame_ms"), payload)
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(payload)
        self.assertEqual(caught.exception.refusal_code, "edit_not_observed", caught.exception.reason)


class ProbeRefusalCodes(unittest.TestCase):
    def test_edit_miss_and_caret_miss_carry_refusal_codes(self):
        from perf.runner.refusals import RefusalCode

        for code in (
            "edit_not_observed",
            "caret_not_at_paragraph_start",
            "fixture_paragraph_not_in_census",
            "fixture_body_pair_absent",
            "fixture_symbol_unmapped",
        ):
            self.assertIn(code, {item.value for item in RefusalCode})
            with self.assertRaises(bd.ProbeRefusal) as caught:
                bd.c12_measured_sample({"error": code})
            self.assertEqual(caught.exception.refusal_code, code)


if __name__ == "__main__":
    unittest.main()
