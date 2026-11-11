"""r3c12b second fairness review: wordcraft glyph row, C12 end frame, nearest anchor, gate record."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
LANE_EDIT_BURST = REPO / "perf/runner/lane_edit_burst.mjs"
DOCUMENT_PROBE = REPO / "perf/runner/document_probe.mjs"


class NodeContract(unittest.TestCase):
    def node(self, body: str) -> dict:
        script = f"""
import assert from 'node:assert/strict';
const mod = await import({json.dumps(str(LANE_EDIT_BURST))});
{body}
"""
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)


class AnchorRefindContext(NodeContract):
    def test_refuse_when_equal_text_count_increases(self):
        out = self.node(
            """
const snapshot = {
  prefixTexts: ['Alpha'],
  anchorText: 'Beta',
  anchorTextCount: 1,
  anchorOccurrence: 1,
  caretIndex: 0,
  anchorIndex: 1,
  blockTexts: ['Alpha', 'Beta'],
};
const blocks = [{ innerText: 'Alpha' }, { innerText: 'Beta' }, { innerText: 'Beta' }];
const read = (b) => String(b.innerText || '');
const check = mod.ANCHOR_REFIND_CONTEXT_OK(snapshot, blocks, read);
assert.equal(check.ok, false, JSON.stringify(check));
assert.equal(check.reason, 'anchor_identity_ambiguous');
console.log(JSON.stringify(check));
"""
        )
        self.assertFalse(out["ok"])

    def test_unique_anchor_text_skips_prefix_when_count_is_one(self):
        out = self.node(
            """
const snapshot = {
  prefixTexts: ['Alpha'],
  anchorText: 'Beta',
  anchorTextCount: 1,
  anchorOccurrence: 1,
  caretIndex: 0,
  anchorIndex: 1,
  blockTexts: ['Alpha', 'Beta', 'Gamma'],
};
const blocks = [{ innerText: 'xAlpha' }, { innerText: 'Beta' }, { innerText: 'Gamma' }];
const read = (b) => String(b.innerText || '');
const check = mod.ANCHOR_REFIND_CONTEXT_OK(snapshot, blocks, read);
assert.equal(check.ok, true, JSON.stringify(check));
console.log(JSON.stringify(check));
"""
        )
        self.assertTrue(out["ok"])

    def test_allow_when_prefix_matches_after_rerender(self):
        out = self.node(
            """
const snapshot = {
  prefixTexts: ['Alpha'],
  anchorText: 'Beta',
  anchorTextCount: 2,
  anchorOccurrence: 1,
  caretIndex: 0,
  anchorIndex: 1,
  blockTexts: ['Alpha', 'Beta', 'Beta'],
};
const blocks = [
  { innerText: 'xAlpha' },
  { innerText: 'Beta' },
  { innerText: 'Beta' },
];
const read = (b) => String(b.innerText || '');
const check = mod.ANCHOR_REFIND_CONTEXT_OK(snapshot, blocks, read);
assert.equal(check.ok, true, JSON.stringify(check));
console.log(JSON.stringify(check));
"""
        )
        self.assertTrue(out["ok"])


class PickNearestBlockBelow(NodeContract):
    def test_duplicate_text_picks_the_nearest_block_below_not_a_farther_unique_one(self):
        out = self.node(
            """
const entries = [
  { text: 'A', top: 10 },
  { text: 'B', top: 40 },
  { text: 'B', top: 80 },
  { text: 'C', top: 120 },
];
const picked = mod.PICK_ANCHOR_BELOW(entries, { top: 5, bottom: 20 }, 800);
assert.equal(picked.ok, true, JSON.stringify(picked));
assert.equal(picked.anchorText, 'B');
assert.equal(picked.anchorIndex, 1);
assert.equal(picked.anchorOccurrence, 1);
console.log(JSON.stringify(picked));
"""
        )
        self.assertEqual(out["anchorIndex"], 1)
        self.assertEqual(out["anchorOccurrence"], 1)

    def test_anchor_is_the_paragraph_after_the_caret_not_a_later_equal_one(self):
        out = self.node(
            """
const entries = [
  { text: 'A', top: 10, bottom: 20 },
  { text: 'B', top: 40, bottom: 52 },
  { text: 'B', top: 80, bottom: 92 },
];
const picked = mod.PICK_ANCHOR_BELOW(entries, { top: 5, bottom: 20 }, 800);
assert.equal(picked.anchorIndex, 1);
assert.equal(picked.anchorOccurrence, 1);
console.log(JSON.stringify(picked));
"""
        )
        self.assertEqual(out["anchorOccurrence"], 1)


class C12SampleEnd(unittest.TestCase):
    def test_refuses_a_presented_frame_before_the_anchor_shift(self):
        from perf.runner import benchmark_document as bd
        from perf.tests.witness_records import publishable_witness_record

        probe = {
            "mode": "reflow",
            "moved": True,
            "window_excludes_forced_layout": True,
            "input_page_ms": 1000.0,
            "observed_shift_page_ms": 1090.0,
            "presented_frame_ms": 10.0,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "witness": publishable_witness_record(1010.0, 1000.0),
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(probe)
        self.assertIn("precedes the anchor reflow", caught.exception.reason)

    def test_accepts_the_first_frame_at_or_after_the_anchor_shift(self):
        from perf.runner import benchmark_document as bd
        from perf.tests.witness_records import publishable_witness_record

        probe = {
            "mode": "reflow",
            "moved": True,
            "window_excludes_forced_layout": True,
            "input_page_ms": 1000.0,
            "observed_shift_page_ms": 1090.0,
            "presented_frame_ms": 90.0,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "witness": publishable_witness_record(1090.0, 1000.0),
        }
        self.assertEqual(bd.c12_measured_sample(probe), 90.0)

    def test_reflow_witness_starts_at_the_observed_shift_not_before(self):
        text = DOCUMENT_PROBE.read_text(encoding="utf-8")
        self.assertNotIn("shift.at - 40", text)
        self.assertIn("shift.at", text)


class WordcraftGlyphRow(unittest.TestCase):
    def test_content_refusal_still_records_c05_c06_glyph_not_applicable(self):
        from perf.runner import benchmark_warm_cold as bw

        payload = {
            "pairs": [
                {
                    "cold": {
                        "mechanism": "trusted_keydown",
                        "edit_confirmation": {
                            "adapter": {"adapter": "flag", "confirmed": True, "after_count": 1},
                        },
                        "content_check": {
                            "content_verified": False,
                            "surface_reason": "document_content_unverifiable",
                            "length_check": "not_run",
                            "length_enforced": False,
                            "content_check": "not_run",
                        },
                    },
                    "warm": {
                        "mechanism": "trusted_keydown",
                        "edit_confirmation": {
                            "adapter": {"adapter": "flag", "confirmed": True, "after_count": 1},
                        },
                        "content_check": {
                            "content_verified": False,
                            "surface_reason": "document_content_unverifiable",
                            "length_check": "not_run",
                            "length_enforced": False,
                            "content_check": "not_run",
                        },
                    },
                }
            ]
        }
        self.assertIsNotNone(bw._content_refusal(payload))
        glyph = bw._glyph_geometry_under_content_refusal("wordcraft", payload)
        self.assertIsNotNone(glyph)
        with tempfile.TemporaryDirectory(dir=REPO / ".scratch" / "tmp") as tmp:
            attempt_dir = Path(tmp)
            criteria_map = {
                "C05": ("presented_frame", "browser_visible"),
                "C06": ("input_to_next_paint", "browser_visible"),
            }
            from perf.fixtures.profiles import size_ladder

            content_meta = {"length_check": "applied", "length_check_reason": None}
            workload_row = next(w for w in size_ladder() if w["workload_id"] == "prose-500w")
            bw._record_glyph_na_under_content_refusal(
                attempt_dir=attempt_dir,
                editor_id="wordcraft",
                lane="browser_wordcraft",
                editor_version="wordcraft",
                workload_row=workload_row,
                fixture_sha256="a" * 64,
                docx_size=1,
                criteria_map=criteria_map,
                content_refusal=bw._content_refusal(payload),
                glyph_na=glyph,
                content_meta=content_meta,
                gate=__import__("perf.runner.benchmark_document", fromlist=["gate_length_check_for"]).gate_length_check_for(
                    "wordcraft", content_meta
                ),
            )
            for cid in ("C05", "C06"):
                paths = list(attempt_dir.glob(f"{cid.lower()}-wordcraft-*.json"))
                self.assertEqual(len(paths), 1, cid)
                trial = json.loads(paths[0].read_text(encoding="utf-8"))
                self.assertEqual(trial["outcome"], "not_applicable")
                self.assertIn("document_content_unverifiable", trial["failure_reason"])
                diag = trial["diagnostic"]
                self.assertEqual(diag["glyph_geometry"]["reason"], bw.NO_GLYPH_GEOMETRY_REASON)
                self.assertTrue(diag["glyph_geometry"]["edit_landed_in_model"])


class ContentGateRecord(unittest.TestCase):
    def test_one_builder_is_shared_by_warm_cold_and_document(self):
        from perf.runner import benchmark_document as bd
        from perf.runner import benchmark_warm_cold as bw

        meta = {"length_check": "applied", "length_check_reason": "corpus"}
        gate = {"length_check": "opening_only", "length_enforced": False, "content_check": "mounted_text_in_fixture"}
        record = bd.content_gate_record(meta, gate)
        self.assertEqual(record["content_length_check"], "opening_only")
        self.assertEqual(record["content_check"], "mounted_text_in_fixture")
        warm = bw._content_length_diagnostic(meta, gate)
        self.assertEqual(
            {k: warm[k] for k in ("content_length_check", "content_check", "content_length_enforced")},
            {k: record[k] for k in ("content_length_check", "content_check", "content_length_enforced")},
        )

    def test_lane_modules_import_the_shared_builder(self):
        for name in (
            "benchmark_input.py",
            "benchmark_memory.py",
            "benchmark_typing.py",
            "adversarial_c10_scroll.py",
            "benchmark_resources.py",
        ):
            text = (REPO / "perf/runner" / name).read_text(encoding="utf-8")
            self.assertIn("content_gate_record", text, name)


if __name__ == "__main__":
    unittest.main()
