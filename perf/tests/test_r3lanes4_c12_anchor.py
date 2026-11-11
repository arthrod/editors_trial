"""r3lanes4/r3c12b/r3c12d: the C12 anchor is the first body paragraph after the caret paragraph."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LANE_EDIT_BURST = REPO / "perf/runner/lane_edit_burst.mjs"
BENCHMARK_DOCUMENT = REPO / "perf/runner/benchmark_document.py"


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


class PickAnchorBelowCaret(NodeContract):
    pass

    def test_first_paragraph_after_the_caret_is_the_anchor(self):
        out = self.node(
            """
assert.equal(typeof mod.PICK_ANCHOR_BELOW, 'function');
const entries = [
  { text: 'In property law...', top: 100, bottom: 118 },
  { text: 'The next paragraph moves with the insertion.', top: 150, bottom: 168 },
  { text: 'duplicated paragraph', top: 200, bottom: 218 },
  { text: 'duplicated paragraph', top: 300, bottom: 318 },
  { text: 'A later page paragraph that does not move.', top: 1281.78, bottom: 1299 },
];
const picked = mod.PICK_ANCHOR_BELOW(entries, { top: 102, bottom: 118 }, 900);
assert.equal(picked.ok, true, JSON.stringify(picked));
assert.equal(picked.anchorText, 'The next paragraph moves with the insertion.');
assert.equal(picked.anchorIndex, 1);
console.log(JSON.stringify(picked));
"""
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["anchorIndex"], 1)

    def test_last_unique_block_off_viewport_is_never_the_anchor(self):
        out = self.node(
            """
const entries = [
  { text: 'caret line', top: 90, bottom: 96 },
  { text: 'first page paragraph', top: 150, bottom: 168 },
  { text: 'later page paragraph one', top: 1281.78 },
  { text: 'later page paragraph two', top: 1411.59 },
];
const picked = mod.PICK_ANCHOR_BELOW(entries, { top: 80, bottom: 96 }, 900);
assert.equal(picked.ok, true, JSON.stringify(picked));
assert.equal(picked.anchorText, 'first page paragraph');
console.log(JSON.stringify(picked));
"""
        )
        self.assertEqual(out["anchorText"], "first page paragraph")

    def test_no_block_below_the_caret_in_viewport_refuses(self):
        out = self.node(
            """
const entries = [
  { text: 'caret line', top: 90, bottom: 96 },
  { text: 'later page paragraph one', top: 1281.78, bottom: 1299 },
  { text: 'later page paragraph two', top: 1411.59, bottom: 1429 },
];
const picked = mod.PICK_ANCHOR_BELOW(entries, { top: 80, bottom: 96 }, 900);
assert.equal(picked.ok, false, JSON.stringify(picked));
assert.match(picked.reason, /off the viewport|below the caret/);
console.log(JSON.stringify(picked));
"""
        )
        self.assertFalse(out["ok"])
        self.assertTrue("below the caret" in out["reason"] or "off the viewport" in out["reason"])

    def test_anchor_is_the_next_paragraph_in_document_order(self):
        out = self.node(
            """
const entries = [
  { text: 'A', top: 10, bottom: 20 },
  { text: 'B', top: 40, bottom: 52 },
  { text: 'B', top: 80, bottom: 92 },
  { text: 'C', top: 120, bottom: 132 },
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

    def test_missing_caret_box_refuses_with_a_named_reason(self):
        out = self.node(
            """
const picked = mod.PICK_ANCHOR_BELOW([{ text: 'a', top: 10 }, { text: 'b', top: 200 }], null, 900);
assert.equal(picked.ok, false, JSON.stringify(picked));
assert.match(picked.reason, /caret/);
console.log(JSON.stringify(picked));
"""
        )
        self.assertFalse(out["ok"])
        self.assertIn("caret", out["reason"])

    def test_fewer_than_two_blocks_refuses(self):
        out = self.node(
            """
const picked = mod.PICK_ANCHOR_BELOW([{ text: 'only block', top: 10 }], { top: 0, bottom: 4 }, 900);
assert.equal(picked.ok, false, JSON.stringify(picked));
assert.match(picked.reason, /fewer than two/);
console.log(JSON.stringify(picked));
"""
        )
        self.assertFalse(out["ok"])
        self.assertIn("fewer than two", out["reason"])


class DocxodusC12IsProbed(unittest.TestCase):
    def test_the_false_host_limit_skip_is_gone(self):
        text = BENCHMARK_DOCUMENT.read_text(encoding="utf-8")
        self.assertNotIn(
            "docxodus 15.0.0 has no keyboard-driven y-shift surface",
            text,
            "the docxodus C12 skip contradicted the live probe: #modeEditor mounts "
            "[contenteditable][data-anchor] blocks whose paragraphs move on Enter",
        )
        self.assertNotIn('editor_id == "docxodus"', text.split('criterion_id == "C12"')[1].split('criterion_id == "C14"')[0])

    def test_wordcraft_skip_stays(self):
        text = BENCHMARK_DOCUMENT.read_text(encoding="utf-8")
        c12_block = text.split('criterion_id == "C12"')[1].split('criterion_id == "C14"')[0]
        self.assertIn('editor_id == "wordcraft"', c12_block)
        self.assertIn("not_applicable", c12_block)

    def test_gather_reflow_before_receives_the_picker(self):
        text = (REPO / "perf/runner/document_probe.mjs").read_text(encoding="utf-8")
        self.assertIn("PICK_ANCHOR_BELOW", text)
        self.assertIn("pickBelow", text)

    def test_c12_reflow_witness_uses_editor_host_only_for_docxodus_block_mode(self):
        text = (REPO / "perf/runner/document_probe.mjs").read_text(encoding="utf-8")
        self.assertIn("reflowDocumentRegion", text)
        burst = LANE_EDIT_BURST.read_text(encoding="utf-8")
        self.assertIn("reflowWitnessSelector", burst)
        self.assertIn("if (editorId === 'docxodus') return '#editorHost'", burst)


class ReflowBlockSelectors(NodeContract):
    def test_superdoc_reflow_blocks_stay_inside_the_editor(self):
        out = self.node(
            """
assert.equal(mod.reflowBlockSelector('superdoc', '.fallback'), '#editor .superdoc-line');
console.log(JSON.stringify(true));
"""
        )
        self.assertTrue(out)

    def test_eigenpal_uses_paragraph_fragments_not_line_spans(self):
        out = self.node(
            """
assert.equal(mod.reflowBlockSelector('eigenpal', '.fallback'), '.docx-paragraph-fragment');
console.log(JSON.stringify(true));
"""
        )
        self.assertTrue(out)


class YProxyRemoved(NodeContract):
    """r3lanes4 ruling 4: the page container is not a paragraph."""

    def test_the_y_proxy_publish_path_is_gone(self):
        text = LANE_EDIT_BURST.read_text(encoding="utf-8")
        self.assertNotIn("REFLOW_MODEL_EDITORS", text)
        self.assertNotIn("REFLOW_Y_PROXY", text)
        self.assertNotIn("useModel", text)
        self.assertNotIn("y_proxy", text)

    def test_canvas_and_docen_are_named_no_paragraph_geometry(self):
        text = (REPO / "perf/runner/document_probe.mjs").read_text(encoding="utf-8")
        self.assertIn("C12_NO_PARAGRAPH_GEOMETRY", text)
        self.assertIn("no paragraph geometry", text)
        # The refusal carries its evidence: the model paragraphs that exist and
        # the DOM blocks that do not.
        self.assertIn("model_paragraphs", text)
        self.assertIn("dom_blocks", text)

    def test_the_no_geometry_set_is_canvas_and_docen(self):
        out = self.node(
            """
assert.equal(typeof mod.C12_NO_PARAGRAPH_GEOMETRY, 'object');
assert.equal(mod.C12_NO_PARAGRAPH_GEOMETRY.has('canvas'), true);
assert.equal(mod.C12_NO_PARAGRAPH_GEOMETRY.has('docen'), true);
assert.equal(mod.C12_NO_PARAGRAPH_GEOMETRY.has('plate'), false);
console.log(JSON.stringify([...mod.C12_NO_PARAGRAPH_GEOMETRY]));
"""
        )
        self.assertEqual(sorted(out), ["canvas", "docen"])


if __name__ == "__main__":
    unittest.main()
