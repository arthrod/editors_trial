"""r3c12e: C12 body caret alignment and anchor-identity refusal diagnostics."""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LANE = REPO / "perf/runner/lane_edit_burst.mjs"


class NodeContract(unittest.TestCase):
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


class C12BodyCaretIndex(NodeContract):
    def test_first_body_paragraph_skips_fixture_headings(self):
        out = self.node(
            """
const entries = [
  { text: 'Article 1. Incidental Taxes Title Force Effect Without', top: 10 },
  { text: 'In property property each completion indirect tax', top: 40 },
  { text: 'Director partial connection timely also respect.', top: 70 },
];
const pick = mod.c12FirstBodyCaretIndex(entries);
assert.equal(pick.ok, true, JSON.stringify(pick));
assert.equal(pick.caretIndex, 1);
console.log(JSON.stringify(pick));
"""
        )
        self.assertEqual(out["caretIndex"], 1)


class C12IdentityDiagnostic(NodeContract):
    def test_refusal_reports_condition_e_when_tail_mismatches(self):
        out = self.node(
            """
const snapshot = {
  caretIndex: 0,
  anchorIndex: 1,
  blockTexts: ['Alpha', 'Beta', 'Gamma'],
  anchorText: 'Beta',
};
const texts = ['xAlpha', 'Beta', 'WRONG'];
const diag = mod.C12_IDENTITY_REFUSAL_DIAGNOSTIC(snapshot, texts, (t) => String(t).trim(), 8, 80);
assert.equal(diag.failed, 'e', JSON.stringify(diag));
assert.equal(diag.before_blocks.length, 3);
assert.equal(diag.after_blocks.length, 3);
assert.equal(diag.caretIndex, 0);
console.log(JSON.stringify(diag));
"""
        )
        self.assertEqual(out["failed"], "e")

    def test_unchanged_caret_paragraph_reports_condition_c(self):
        out = self.node(
            """
const snapshot = {
  caretIndex: 1,
  anchorIndex: 2,
  blockTexts: ['H', 'In property property each completion', 'Director partial'],
  anchorText: 'Director partial',
};
const texts = ['H', 'In property property each completion', 'Director partial'];
const diag = mod.C12_IDENTITY_REFUSAL_DIAGNOSTIC(snapshot, texts, (t) => String(t).trim(), 8, 80);
assert.equal(diag.failed, 'c', JSON.stringify(diag));
console.log(JSON.stringify(diag));
"""
        )
        self.assertEqual(out["failed"], "c")

    def test_window_shows_the_pair_past_the_eight_row_clip(self):
        # The pair sits at indexes 9 and 10. A prefix of 8 rows is page chrome
        # and hides the count change. The window is caret-3 through anchor+5.
        out = self.node(
            """
const before = Array.from({ length: 20 }, (_, i) => 'block ' + i);
before[9] = 'CARET';
before[10] = 'ANCHOR';
const after = before.slice();
after.push('ANCHOR');
const snapshot = {
  caretIndex: 9,
  anchorIndex: 10,
  blockTexts: before,
  anchorText: 'ANCHOR',
};
const diag = mod.C12_IDENTITY_REFUSAL_DIAGNOSTIC(snapshot, after, (t) => String(t).trim(), 8, 80);
assert.equal(diag.failed, 'b', JSON.stringify(diag));
assert.equal(diag.window_from, 6);
assert.equal(diag.before_blocks.length, 10);
assert.equal(diag.after_blocks.length, 10);
assert.equal(diag.before_blocks[0], 'block 6');
assert.equal(diag.before_blocks[3], 'CARET');
assert.equal(diag.before_blocks[4], 'ANCHOR');
assert.deepEqual(diag.anchor_indexes_before, [10]);
assert.deepEqual(diag.anchor_indexes_after, [10, 20]);
console.log(JSON.stringify(diag));
"""
        )
        self.assertEqual(out["failed"], "b")
        self.assertEqual(out["window_from"], 6)
        self.assertEqual(out["before_blocks"][3], "CARET")
        self.assertEqual(out["before_blocks"][4], "ANCHOR")
        self.assertEqual(out["anchor_indexes_before"], [10])
        self.assertEqual(out["anchor_indexes_after"], [10, 20])

    def test_missing_indexes_fall_back_to_the_prefix(self):
        out = self.node(
            """
const blocks = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'];
const diag = mod.C12_IDENTITY_REFUSAL_DIAGNOSTIC(
  { blockTexts: blocks },
  blocks,
  (t) => String(t).trim(),
  8,
  80,
);
assert.equal(diag.failed, 'a', JSON.stringify(diag));
assert.equal(diag.window_from, 0);
assert.equal(diag.before_blocks.length, 8);
assert.equal(diag.before_blocks[0], 'a');
assert.equal(diag.before_blocks[7], 'h');
console.log(JSON.stringify(diag));
"""
        )
        self.assertEqual(out["failed"], "a")
        self.assertEqual(out["window_from"], 0)
        self.assertEqual(len(out["before_blocks"]), 8)


class C12BodyCaretUsesAdapter(unittest.TestCase):
    def test_place_c12_body_caret_calls_shared_place_caret(self):
        lane = (REPO / "perf/runner/lane_edit_burst.mjs").read_text(encoding="utf-8")
        probe = (REPO / "perf/runner/document_probe.mjs").read_text(encoding="utf-8")
        surface = (REPO / "perf/runner/edit_surface.mjs").read_text(encoding="utf-8")
        self.assertIn("placeCaret", lane)
        self.assertIn("verifyCaretAtParagraphStart", surface)
        self.assertNotIn("placeC12BodyCaretPage", probe)
        place_fn = lane.split("export async function placeC12BodyCaret")[1].split("export async function ensureReflowCaret")[0]
        self.assertIn("placeCaret(", place_fn)
        self.assertNotIn("placeC12BodyCaretPage", place_fn)

    def test_edit_not_observed_is_a_named_refusal(self):
        lane = (REPO / "perf/runner/lane_edit_burst.mjs").read_text(encoding="utf-8")
        probe = (REPO / "perf/runner/document_probe.mjs").read_text(encoding="utf-8")
        self.assertIn("edit_not_observed", lane)
        self.assertIn("waitForC12CaretEdit", lane)
        self.assertIn("edit_not_observed", probe)
        self.assertIn("caret_not_at_paragraph_start", lane)
        # C12_NEVER_PAYLOAD is the reviewer's captured never.json. The default
        # runs never.html. A confirm timeout reported as anchor_identity_ambiguous
        # fails this assertion.
        payload_path = os.environ.get("C12_NEVER_PAYLOAD")
        if payload_path:
            payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
        else:
            from perf.tests.test_r3c12h import reflow_host_payload

            payload = reflow_host_payload("never.html", timeout_ms=2000)
        self.assertEqual(payload.get("error"), "edit_not_observed", payload)
        from perf.runner import benchmark_document as bd

        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(payload)
        self.assertEqual(caught.exception.refusal_code, "edit_not_observed", caught.exception.reason)

    def test_superdoc_caret_verify_reads_model_paragraph(self):
        surface = (REPO / "perf/runner/edit_surface.mjs").read_text(encoding="utf-8")
        self.assertIn("READ_SUPERDOC_CARET_MODEL", surface)
        self.assertIn("PLACE_SUPERDOC_PARAGRAPH_START", surface)
        self.assertIn("PLACE_FOLIO_PARAGRAPH_START", surface)
        self.assertIn("expectedParagraphText", surface)
        offset_fn = surface.split("export const READ_CARET_BLOCK_OFFSET")[1].split(
            "\nexport async function verifyCaretAtParagraphStart"
        )[0]
        self.assertNotIn("READ_SUPERDOC_CARET_MODEL()", offset_fn)
        lane = (REPO / "perf/runner/lane_edit_burst.mjs").read_text(encoding="utf-8")
        self.assertIn("expectedParagraphText: pick.caretText", lane)


if __name__ == "__main__":
    unittest.main()
