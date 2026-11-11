"""B4 input lane fixinput3: paint witness, click points, paste settle, focus."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

CONTRACT = REPO / "perf" / "tests" / "b4_fixinput3_contract.mjs"


class Fixinput3Contract(unittest.TestCase):
    def test_fixinput3_contract(self):
        proc = subprocess.run(
            ["node", str(CONTRACT)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            proc.returncode,
            0,
            msg=(proc.stdout or "") + (proc.stderr or ""),
        )


class ProbeEnvOpeningRequired(unittest.TestCase):
    def test_empty_complex_opening_sets_required_flag(self):
        from unittest.mock import patch

        from perf.runner.benchmark_input import _fixture, _probe_env

        fixture, _sha, _size, row = _fixture("plate", "complex-corpus")
        self.assertEqual(row["workload_id"], "complex-corpus")
        with patch("perf.runner.benchmark_document.corpus_opening_text", return_value=""):
            env = _probe_env("plate", {}, fixture, workload_id="complex-corpus")
        self.assertEqual(env.get("PERF_INPUT_OPENING_REQUIRED"), "1")
        self.assertNotIn("PERF_EXPECTED_OPENING_TEXT", env)


if __name__ == "__main__":
    unittest.main()
