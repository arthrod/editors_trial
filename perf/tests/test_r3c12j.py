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
import unittest
from pathlib import Path

import perf.runner.benchmark_document as bd

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"
LANE = REPO / "perf" / "runner" / "lane_edit_burst.mjs"
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

    def _reflow(self, host_file: str, timeout_ms: int = 20000) -> dict:
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

    def test_recorded_frame_must_be_the_confirmed_anchor(self):
        payload = self._reflow("untied.html")
        self.assertEqual(payload.get("error"), "recorded_frame_not_confirmed_anchor", payload)
        self.assertIsNot(payload.get("moved"), True, payload)
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(payload)
        self.assertEqual(caught.exception.refusal_code, "recorded_frame_not_confirmed_anchor")


if __name__ == "__main__":
    unittest.main()
