"""r3lanes4 ruling 3: docxodus C12 is measured, and the reflow anchor is the
nearest unique block below the caret in the viewport, not the last unique block.
"""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LANE_EDIT_BURST = REPO / "perf/runner/lane_edit_burst.mjs"
BENCHMARK_DOCUMENT = REPO / "perf/runner/benchmark_document.py"


class PickAnchorBelowCaret(unittest.TestCase):
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

    def test_nearest_unique_block_below_the_caret_is_the_anchor(self):
        out = self.node(
            """
assert.equal(typeof mod.PICK_ANCHOR_BELOW, 'function');
// The caret sits in a body line of the first block (top 100). A first-page
// paragraph (top 150) and a later-page paragraph (top 1281) are both unique;
// only the in-viewport one below the caret may carry the shift.
const entries = [
  { text: 'In property law...', top: 100 },
  { text: 'duplicated paragraph', top: 200 },
  { text: 'duplicated paragraph', top: 300 },
  { text: 'The next paragraph moves with the insertion.', top: 150 },
  { text: 'A later page paragraph that does not move.', top: 1281.78 },
];
const picked = mod.PICK_ANCHOR_BELOW(entries, { top: 102, bottom: 118 }, 900);
assert.equal(picked.ok, true, JSON.stringify(picked));
assert.equal(picked.anchorText, 'The next paragraph moves with the insertion.');
assert.equal(picked.anchorIndex, 3);
console.log(JSON.stringify(picked));
"""
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["anchorIndex"], 3)

    def test_last_unique_block_off_viewport_is_never_the_anchor(self):
        out = self.node(
            """
const entries = [
  { text: 'caret line', top: 90 },
  { text: 'first page paragraph', top: 150 },
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

    def test_no_unique_block_below_the_caret_in_viewport_refuses(self):
        out = self.node(
            """
const entries = [
  { text: 'caret line', top: 90 },
  { text: 'later page paragraph one', top: 1281.78 },
  { text: 'later page paragraph two', top: 1411.59 },
];
const picked = mod.PICK_ANCHOR_BELOW(entries, { top: 80, bottom: 96 }, 900);
assert.equal(picked.ok, false, JSON.stringify(picked));
assert.match(picked.reason, /below the caret/);
console.log(JSON.stringify(picked));
"""
        )
        self.assertFalse(out["ok"])
        self.assertIn("below the caret", out["reason"])

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


if __name__ == "__main__":
    unittest.main()
