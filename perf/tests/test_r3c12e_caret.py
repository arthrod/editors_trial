"""r3c12e: C12 body caret alignment and anchor-identity refusal diagnostics."""
from __future__ import annotations

import json
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
