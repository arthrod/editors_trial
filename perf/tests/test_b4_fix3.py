"""B4 fix round 3 (#138 re-review R1–R4)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.tests.witness_records import publishable_witness_record
from perf.runner.criteria_input_io import (  # noqa: E402
    trials_from_payload,
    write_trials_from_payload,
)
from perf.tests.test_input_criteria import (  # noqa: E402
    _entry,
    _payload,
    fixture_identity,
)

B4_FIX3_REPRO = REPO / "perf" / "tests" / "b4_fix3_repro.mjs"


def _run_fix3_repro() -> dict:
    proc = subprocess.run(
        ["node", str(B4_FIX3_REPRO)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "b4_fix3_repro.mjs failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr)
        )
    return json.loads(proc.stdout.strip())


class R1RefusedWitnessEvidence(unittest.TestCase):
    def test_c09_refused_keeps_record_verdict_and_errors(self):
        data = _run_fix3_repro()["c09_refused"]
        self.assertEqual(data["outcome"], "failed")
        self.assertIn("paint_witness_refused", data["failure_reason"] or "")
        self.assertIsInstance(data["witness"], dict)
        self.assertEqual(data["sentinel"], "whole-record")
        self.assertEqual(data["witness_refusal"], "clock_check_not_acceptable")
        self.assertTrue(data["witness_errors"])

    def test_c08_refused_keeps_witness_on_paste_and_fallback(self):
        data = _run_fix3_repro()["c08_refused"]
        self.assertIsInstance(data["paste_witness"], dict)
        self.assertIsInstance(data["fallback_witness"], dict)
        self.assertEqual(data["fallback_refusal"], "clock_check_not_acceptable")
        self.assertTrue(data["fallback_errors"])

    def test_writer_refusal_carries_witness_evidence(self):
        bad = publishable_witness_record(
            140.0,
            100.0,
            clock_check={"acceptable": False, "reason": "anchor_lag_above_bound"},
        )
        obs = {
            "frame_ms": 140.0,
            "sample_ms": 40.0,
            "witness": bad,
            "witness_refusal": "clock_check_not_acceptable",
            "witness_errors": ["clock anchor refused"],
        }
        entry = _entry(cid="C08", samples_ms=[40.0], observations=[obs])
        payload = _payload({"C08": entry})
        row, sha, size = fixture_identity()
        with tempfile.TemporaryDirectory() as tmp:
            written = write_trials_from_payload(
                payload,
                Path(tmp),
                editor_version="fake",
                fixture_sha256=sha,
                workload_row=row,
                docx_size=size,
            )
        c08 = written["C08"]
        self.assertFalse(c08["written"])
        self.assertIsInstance(c08.get("witness"), dict)
        self.assertEqual(c08.get("witness_refusal"), "clock_check_not_acceptable")
        self.assertTrue(c08.get("witness_errors"))


class R2C09FixtureIsolation(unittest.TestCase):
    def test_missing_keydown_restores_fixture(self):
        data = _run_fix3_repro()["c09_missing_input"]
        self.assertEqual(data["failure_reason"], "no_keydown_observed_for_typed_character")
        self.assertEqual(data["body"], "ORIGINAL")
        self.assertGreaterEqual(data["undos"], 1)


class R3SampleWitnessConsistency(unittest.TestCase):
    def test_mismatched_sample_rejected(self):
        witness = publishable_witness_record(140.0, 100.0)
        entry = _entry(
            cid="C08",
            samples_ms=[900.0],
            observations=[
                {
                    "input_ms": 100.0,
                    "frame_ms": 140.0,
                    "sample_ms": 900.0,
                    "witness": witness,
                },
            ],
        )
        payload = _payload({"C08": entry})
        row, sha, size = fixture_identity()
        with self.assertRaises(ValueError) as ctx:
            trials_from_payload(
                payload,
                editor_version="fake",
                fixture_sha256=sha,
                workload_row=row,
                docx_size=size,
            )
        self.assertIn("witness latency", str(ctx.exception).lower())


class R4ValidatorSetupRefusal(unittest.TestCase):
    def test_missing_tmpdir_returns_refusal_not_throw(self):
        data = _run_fix3_repro()["tmp_missing"]
        self.assertFalse(data.get("ok"))
        self.assertTrue(data.get("refused"))
        self.assertEqual(data.get("reason"), "witness_validator_failed")


if __name__ == "__main__":
    unittest.main()
