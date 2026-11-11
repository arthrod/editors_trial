"""B4 fix (#131): permanent tests from review reproducers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.tests.witness_records import publishable_witness_record
from perf.runner.criteria_input_io import (  # noqa: E402
    assert_payload_shape,
    build_support_matrix,
    trials_from_payload,
    write_trials_from_payload,
)
from perf.runner.witness import validate_witness
from perf.tests.test_input_criteria import (  # noqa: E402
    PAINT_MECHANISM,
    _entry,
    _payload,
    fixture_identity,
)

B4_FIXTURES = REPO / "perf" / "tests" / "fixtures" / "hosts" / "b4"
REPRO = REPO / "perf" / "tests" / "b4_fix_repro.mjs"


def _witness(extra=None):
    base = {
        "mechanism": PAINT_MECHANISM,
        "frames_seen": 12,
        "timeout_ms": 2000,
        "frame_interval_ms": 16.667,
    }
    if extra:
        base.update(extra)
    return base


def _run_node_repro() -> dict:
    proc = subprocess.run(
        ["node", str(REPRO)],
        cwd=str(REPO / "harness" / "ui") if (REPO / "harness" / "ui").is_dir() else str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "NODE_PATH": ""},
    )
    if proc.returncode != 0:
        raise AssertionError(
            "b4_fix_repro.mjs failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr)
        )
    return json.loads(proc.stdout.strip())


class Issue131Logic(unittest.TestCase):
    def test_c08_rejects_corrupted_prefix_not_measured(self):
        data = _run_node_repro()
        corrupt = data["corrupt_prefix"]
        self.assertNotEqual(corrupt["outcome"], "measured")
        self.assertEqual(corrupt["samples_ms"], [])
        self.assertIn("bulk_text_or_position", corrupt.get("failure_reason") or "")

    def test_c04_labels_last_activity_not_quiescence_reached(self):
        data = _run_node_repro()
        c04 = data["c04"]
        self.assertEqual(c04["quiescence_event"], "last_activity_before_quiet_window")
        self.assertEqual(c04["quiet_at"], 50)
        self.assertGreaterEqual(c04["quiescence_confirmed_ms"], 200)
        self.assertEqual(c04["quiet_window_ms"], 200)

    def test_compositor_latency_is_not_event_timing_quantized(self):
        data = _run_node_repro()
        rounding = data["rounding"]
        self.assertTrue(rounding["ok"])
        self.assertAlmostEqual(rounding["sampleMs"], 18.0, places=2)

    def test_non_dom_declared_adapter_does_not_measure_wrong_text(self):
        data = _run_node_repro()
        non_dom = data["non_dom"]
        self.assertNotEqual(non_dom["outcome"], "measured")
        self.assertEqual(non_dom["samples_ms"], [])

    def test_sample_after_input_refuses_bad_witness(self):
        data = _run_node_repro()
        refused = data["refused_witness"]
        self.assertFalse(refused["ok"])
        self.assertIn("paint_witness_refused", refused["reason"] or "")
        self.assertEqual(data["validator"]["reason"], "clock_check_not_acceptable")
        self.assertEqual(refused["witness_refusal"], "clock_check_not_acceptable")

    def test_c09_measures_insertion_at_captured_offset(self):
        data = _run_node_repro()
        c09 = data["c09_at_offset"]
        self.assertEqual(c09["outcome"], "measured")
        self.assertTrue(c09["samples_ms"])
        self.assertTrue(c09["witness"])


class Issue131Writer(unittest.TestCase):
    def test_c07_trial_stores_fresh_process_and_frame_interval(self):
        entry = _entry(
            trial_hints={"cache_state": "warm_steady", "repetition_unit": "fresh_process"},
        )
        payload = _payload({"C07": entry}, witness=_witness())
        row, sha, size = fixture_identity()
        trial = trials_from_payload(
            payload,
            editor_version="fake",
            fixture_sha256=sha,
            workload_row=row,
            docx_size=size,
        )["C07"]
        self.assertEqual(trial["environment"]["repetition_unit"], "fresh_process")
        self.assertEqual(trial["diagnostic"].get("frame_interval_ms"), 16.667)

    def test_c08_rounding_does_not_drop_whole_payload(self):
        c07 = _entry(samples_ms=[20.0, 22.0])
        c07["observations"][0]["input_ms"] = 1.0
        c07["observations"][0]["frame_ms"] = 21.0
        c07["observations"][0]["sample_ms"] = 20.0
        c07["observations"][0]["witness"] = publishable_witness_record(
            21.0, 1.0, quiet_window=dict(c07["observations"][0]["quiet_window"])
        )
        c08 = _entry(
            cid="C08",
            samples_ms=[16],
            sub_frame_samples=[True],
            observations=[
                {
                    "frame_ms": 118,
                    "sample_ms": 16,
                    "witness": publishable_witness_record(118.0, 102.0),
                },
            ],
        )
        payload = _payload({"C07": c07, "C08": c08}, witness=_witness())
        assert_payload_shape(payload)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            written = write_trials_from_payload(
                payload,
                tmp,
                editor_version="fake",
                fixture_sha256=fixture_identity()[1],
                workload_row=fixture_identity()[0],
                docx_size=fixture_identity()[2],
            )
        self.assertTrue(written["C07"]["written"])
        self.assertTrue(written["C08"]["written"])
        self.assertIn("c07", Path(written["C07"]["path"]).name.lower())
        self.assertIn("c08", Path(written["C08"]["path"]).name.lower())


class Issue138WitnessAndWriter(unittest.TestCase):
    def test_refused_witness_rejects_measured_c08_payload(self):
        bad = publishable_witness_record(
            140.0,
            100.0,
            clock_check={"acceptable": False, "reason": "anchor_lag_above_bound"},
            document_scoped=False,
            changed_pixels=0,
            frames_after=0,
            caret_masked=False,
        )
        self.assertEqual(validate_witness(bad)["reason"], "clock_check_not_acceptable")
        entry = _entry(
            cid="C08",
            samples_ms=[40.0],
            observations=[{"frame_ms": 140.0, "sample_ms": 40.0, "witness": bad}],
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
        self.assertIn("witness refused", str(ctx.exception))

    def test_skipped_criterion_keeps_refusal_and_correct_paths(self):
        good = publishable_witness_record(120.0, 100.0)
        bad = publishable_witness_record(
            101.0,
            100.0,
            clock_check={"acceptable": False, "reason": "anchor_lag_above_bound"},
            document_scoped=False,
            changed_pixels=0,
            frames_after=0,
            caret_masked=False,
        )
        c08 = _entry(
            cid="C08",
            samples_ms=[1.0],
            observations=[{"frame_ms": 101.0, "sample_ms": 1.0, "witness": bad}],
        )
        c07 = _entry(samples_ms=[20.0, 22.0])
        c07["observations"][0]["input_ms"] = 1.0
        c07["observations"][0]["frame_ms"] = 21.0
        c07["observations"][0]["sample_ms"] = 20.0
        c07["observations"][0]["witness"] = publishable_witness_record(
            21.0, 1.0, quiet_window=dict(c07["observations"][0]["quiet_window"])
        )
        payload = _payload({"C08": c08, "C07": c07})
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            written = write_trials_from_payload(
                payload,
                Path(tmp),
                editor_version="fake",
                fixture_sha256=fixture_identity()[1],
                workload_row=fixture_identity()[0],
                docx_size=fixture_identity()[2],
            )
        self.assertFalse(written["C08"]["written"])
        self.assertTrue(written["C07"]["written"])
        self.assertIn("witness refused", (written["C08"]["failure_reason"] or "").lower())
        c08_summary = {
            "outcome": "failed",
            "samples_ms": [],
            "failure_reason": written["C08"]["failure_reason"],
            "attempt_file": None,
        }
        c07_summary = {
            "outcome": "measured",
            "samples_ms": c07["samples_ms"],
            "failure_reason": None,
            "attempt_file": str(Path(written["C07"]["path"]).resolve()),
        }
        summary = {"C08": c08_summary, "C07": c07_summary}
        matrix = build_support_matrix({"editors": [{"editor_id": "fake", "outcome": "ok", "criteria": summary}]})
        self.assertIn("fake", matrix["C07"]["measured"])
        self.assertIn("fake", matrix["C08"]["refused"])


class Issue131FixtureText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ui = REPO / "harness" / "ui"
        if not ui.is_dir():
            raise unittest.SkipTest("harness/ui missing")
        pw = ui / "node_modules" / "playwright" / "index.mjs"
        if not pw.is_file():
            raise unittest.SkipTest("playwright not installed under harness/ui")

    def test_idle_inner_text_matches_fixture_body(self):
        ui = REPO / "harness" / "ui"
        script = r"""
import fs from 'node:fs';
import { chromium } from 'playwright';
const html = fs.readFileSync(%r, 'utf8');
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.setContent(html);
  const inner = await page.locator('#doc').evaluate((el) => el.innerText);
  console.log(JSON.stringify({ innerText: inner }));
} finally {
  await browser.close();
}
""" % (
            str(B4_FIXTURES / "idle.html"),
        )
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=str(ui),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            self.fail(proc.stderr or proc.stdout)
        data = json.loads(proc.stdout.strip())
        self.assertEqual(data["innerText"], "fixture line one\nfixture line two\n")
