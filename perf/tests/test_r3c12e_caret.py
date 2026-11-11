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
    def test_refusal_reports_condition_c_and_truncated_lists(self):
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
assert.equal(diag.failed, 'd', JSON.stringify(diag));
assert.equal(diag.before_blocks.length, 3);
assert.equal(diag.after_blocks.length, 3);
assert.equal(diag.caretIndex, 0);
console.log(JSON.stringify(diag));
"""
        )
        self.assertEqual(out["failed"], "d")


if __name__ == "__main__":
    unittest.main()
