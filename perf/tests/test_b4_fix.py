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

from perf.runner.criteria_input_io import (  # noqa: E402
    assert_payload_shape,
    trials_from_payload,
    write_trials_from_payload,
)
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
        self.assertIn("correctness", corrupt.get("failure_reason") or "")

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


class Issue131Writer(unittest.TestCase):
    def test_c07_trial_stores_in_process_iteration_and_frame_interval(self):
        entry = _entry(
            trial_hints={"cache_state": "warm_steady", "repetition_unit": "in_process_iteration"},
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
        self.assertEqual(trial["environment"]["repetition_unit"], "in_process_iteration")
        self.assertEqual(trial["diagnostic"].get("frame_interval_ms"), 16.667)

    def test_c08_rounding_does_not_drop_whole_payload(self):
        c07 = _entry(samples_ms=[20.0])
        c08 = _entry(cid="C08", samples_ms=[16], observations=[{"frame_ms": 118}])
        payload = _payload({"C07": c07, "C08": c08}, witness=_witness())
        with self.assertRaises(ValueError):
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
        self.assertEqual(len(written), 1)
        c07_path = written[0]
        self.assertIn("c07", Path(c07_path).name.lower())


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
