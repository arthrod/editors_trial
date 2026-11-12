"""adapterGate names the adapter it refused, and the usable-wait skip says why.

A missing adapter is `no_correctness_adapter: null`, not a canvas. The skip
of the usable wait is correct only because every adapter-refused editor also
cannot satisfy a usable wait, or the refusal is decided anyway.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRITERIA = REPO / "perf" / "runner" / "criteria_input.mjs"


def _node() -> str | None:
    return shutil.which("node")


class AdapterGateReasonTests(unittest.TestCase):
    def test_missing_adapter_is_named_null(self):
        if _node() is None:
            self.skipTest("node is not on PATH")
        script = r"""
import assert from 'node:assert/strict';
const mod = await import(%s);
assert.equal(typeof mod.adapterGate, 'function');
assert.equal(mod.adapterGate(null), 'no_correctness_adapter: null');
assert.equal(mod.adapterGate(undefined), 'no_correctness_adapter: null');
assert.equal(mod.adapterGate(''), 'no_correctness_adapter: null');
assert.equal(mod.adapterGate(false), 'no_correctness_adapter: null');
assert.equal(mod.adapterGate('dom_innerText'), null);
assert.equal(mod.adapterGate('dom_text'), null);
assert.equal(mod.adapterGate('pixel_probe'), 'correctness_adapter_not_implemented: pixel_probe');
console.log(JSON.stringify({ missing: mod.adapterGate(null) }));
""" % json.dumps(CRITERIA.as_uri())
        proc = subprocess.run(
            [_node(), "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["missing"], "no_correctness_adapter: null")

    def test_usable_skip_comment_states_when_it_is_correct(self):
        text = CRITERIA.read_text()
        self.assertNotIn("canvas surface without model API or pixel probe", text)
        skip = text.split("const adapterAlreadyRefused", 1)[0]
        tail = skip[-800:]
        self.assertIn("every adapter-refused editor", tail)
        self.assertIn("cannot satisfy a usable wait", tail)
        self.assertIn("refusal is decided anyway", tail)


if __name__ == "__main__":
    unittest.main()
