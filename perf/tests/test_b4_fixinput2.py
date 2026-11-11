"""B4 input lane fixinput2: text oracle, read scope, complex opening gate."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

CONTRACT = REPO / "perf" / "tests" / "b4_fixinput2_contract.mjs"


class Fixinput2Contract(unittest.TestCase):
    def test_comparison_offset_and_read_scope_contract(self):
        proc = subprocess.run(
            ["node", str(CONTRACT)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            proc.returncode,
            0,
            msg=(proc.stdout or "") + (proc.stderr or ""),
        )


class ProbeEnvComplexCorpus(unittest.TestCase):
    def test_complex_corpus_uses_opening_text_not_body_path(self):
        from perf.runner.benchmark_input import _fixture, _probe_env

        fixture, _sha, _size, row = _fixture("plate", "complex-corpus")
        self.assertEqual(row["workload_id"], "complex-corpus")
        env = _probe_env("plate", {}, fixture, workload_id="complex-corpus")
        self.assertIn("PERF_EXPECTED_OPENING_TEXT", env)
        self.assertTrue(env["PERF_EXPECTED_OPENING_TEXT"].strip())
        self.assertNotIn("PERF_EXPECTED_BODY_PATH", env)

    def test_prose_still_uses_expected_body_path(self):
        from perf.runner.benchmark_input import _fixture, _probe_env

        fixture, _sha, _size, _row = _fixture("plate", "prose-500w")
        env = _probe_env("plate", {}, fixture, workload_id="prose-500w")
        self.assertIn("PERF_EXPECTED_BODY_PATH", env)
        self.assertNotIn("PERF_EXPECTED_OPENING_TEXT", env)


if __name__ == "__main__":
    unittest.main()
