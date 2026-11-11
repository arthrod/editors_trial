"""r3c12d: C12 anchor identity — review counterexamples become behavioural tests."""
from __future__ import annotations

import json
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
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
WITNESS_SERVER = REPO / "perf" / "tests" / "fixtures" / "witness" / "server.py"
TIMEOUT_S = 90


def _node():
    return shutil.which("node")


def _playwright_ready() -> bool:
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

    spec = importlib.util.spec_from_file_location("r3c12d_fixture_server", WITNESS_SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(_node() and _playwright_ready(), "node+playwright required")
class ReflowProbeCounterexamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_mod = _load_server()
        cls.server, _thread, cls.base_url = cls.server_mod.serve(HOSTS)
        cls._corpus_dir = tempfile.TemporaryDirectory(dir=REPO / ".scratch" / "tmp")
        cls.corpus = Path(cls._corpus_dir.name) / "corpus.docx"
        cls.corpus.write_bytes(b"PK\x03\x04r3c12d")

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.shutdown()
            cls.server.server_close()
        cls._corpus_dir.cleanup()

    def _reflow(self, host_file: str) -> dict:
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
            "20000",
        ]
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=TIMEOUT_S)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_split_count1_refuses_not_measures(self):
        payload = self._reflow("split_count1.html")
        self.assertEqual(payload.get("error"), "anchor_identity_ambiguous", payload)
        with self.assertRaises(bd.ProbeRefusal):
            bd.c12_measured_sample(payload)

    def test_enter_slot_wrong_refuses_not_measures(self):
        payload = self._reflow("enter_slot_wrong.html")
        self.assertEqual(payload.get("error"), "anchor_identity_ambiguous", payload)
        with self.assertRaises(bd.ProbeRefusal):
            bd.c12_measured_sample(payload)


class C12MeasuredSampleHardening(unittest.TestCase):
    def _base(self, **overrides):
        probe = {
            "mode": "reflow",
            "moved": True,
            "window_excludes_forced_layout": True,
            "input_page_ms": 1000.0,
            "observed_shift_page_ms": 1090.0,
            "presented_frame_ms": 90.0,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "before": {"anchor_top": 100.0},
            "anchor_top_after": 160.0,
            "witness": publishable_witness_record(1090.0, 1000.0),
        }
        probe.update(overrides)
        return probe

    def test_refuses_zero_presented_frame_ms(self):
        with self.assertRaises(bd.ProbeRefusal):
            bd.c12_measured_sample(self._base(presented_frame_ms=0.0))

    def test_refuses_probe_error_even_with_duration(self):
        with self.assertRaises(bd.ProbeRefusal):
            bd.c12_measured_sample(self._base(error="anchor_identity_ambiguous"))

    def test_refuses_moved_false_even_when_after_top_lower(self):
        with self.assertRaises(bd.ProbeRefusal):
            bd.c12_measured_sample(
                self._base(
                    moved=False,
                    anchor_top_after=160.0,
                )
            )


class AnchorIdentityNode(unittest.TestCase):
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

    def test_attack_q2_count1_split_refuses(self):
        out = self.node(
            """
const snapshot = {
  caretIndex: 0,
  anchorIndex: 1,
  blockTexts: ['AAAA BBBB', 'BBBB'],
  anchorText: 'BBBB',
};
const blocks = [{ innerText: 'xAAAA' }, { innerText: 'BBBB' }];
const read = (b) => String(b.innerText || '');
const check = mod.ANCHOR_REFIND_CONTEXT_OK(snapshot, blocks, read);
assert.equal(check.ok, false);
console.log(JSON.stringify({ ok: check.ok, reason: check.reason }));
"""
        )
        self.assertFalse(out["ok"])

    def test_attack_q3_enter_slot_refuses(self):
        out = self.node(
            """
const snapshot = {
  caretIndex: 0,
  anchorIndex: 1,
  blockTexts: ['Alpha', 'Beta', 'Beta'],
  anchorText: 'Beta',
};
const blocks = [
  { innerText: 'xAlpha' },
  { innerText: 'NOT THE ANCHOR' },
  { innerText: 'Beta' },
  { innerText: 'Beta' },
];
const read = (b) => String(b.innerText || '');
const check = mod.ANCHOR_REFIND_CONTEXT_OK(snapshot, blocks, read);
assert.equal(check.ok, false);
console.log(JSON.stringify({ ok: check.ok, reason: check.reason }));
"""
        )
        self.assertFalse(out["ok"])

    def test_stable_unique_anchor_after_rerender_still_ok(self):
        out = self.node(
            """
const snapshot = {
  caretIndex: 0,
  anchorIndex: 1,
  blockTexts: ['Alpha', 'Beta', 'Gamma'],
  anchorText: 'Beta',
};
const blocks = [{ innerText: 'xAlpha' }, { innerText: 'Beta' }, { innerText: 'Gamma' }];
const read = (b) => String(b.innerText || '');
const check = mod.ANCHOR_REFIND_CONTEXT_OK(snapshot, blocks, read);
assert.equal(check.ok, true, JSON.stringify(check));
console.log(JSON.stringify(check));
"""
        )
        self.assertTrue(out["ok"])


if __name__ == "__main__":
    unittest.main()
