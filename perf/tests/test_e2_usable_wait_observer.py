"""waitForUsableSurface must not install an observer nothing reads.

The quiet-window design left a MutationObserver that wrote lastMutation and
never consulted it. C10's mount observer is a different wait and still reads
its own lastMutation. This wait only polls the usable expression. Whatever
observer it does install must still be disconnected on the way out.
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


class UsableWaitObserverTests(unittest.TestCase):
    def test_usable_wait_does_not_install_an_unread_mutation_observer(self):
        if _node() is None:
            self.skipTest("node is not on PATH")
        script = r"""
import assert from 'node:assert/strict';
const mod = await import(%s);
const seen = [];
const page = {
  async evaluate(fn) {
    const src = typeof fn === 'function' ? Function.prototype.toString.call(fn) : String(fn);
    seen.push(src);
    if (src.includes('eval(code)')) return true;
    return undefined;
  },
  async waitForTimeout() {},
};
const refusal = await mod.waitForUsableSurface(page, '1');
assert.equal(refusal, null);
const joined = seen.join('\n');
assert.equal(joined.includes('lastMutation'), false, joined);
assert.equal(joined.includes('new MutationObserver'), false, joined);
assert.equal(seen.some((src) => src.includes('__ciUsableWait') && src.includes('disconnect')), true);
console.log(JSON.stringify({ refusal, evaluates: seen.length }));
""" % json.dumps(CRITERIA.as_uri())
        proc = subprocess.run(
            [_node(), "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertIsNone(payload["refusal"])


if __name__ == "__main__":
    unittest.main()
