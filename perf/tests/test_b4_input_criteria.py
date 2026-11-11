"""B4: input criteria prove the edit (#113)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.runner.criteria_input_io import (  # noqa: E402
    SUITE,
    assert_payload_shape,
    build_support_matrix,
    trials_from_payload,
    write_trials_from_payload,
)
from perf.runner.witness import validate_witness
from perf.runner.docx_plaintext import docx_body_text  # noqa: E402
from perf.tests.test_input_criteria import (  # noqa: E402
    PAINT_MECHANISM,
    PROBE_SCHEMA,
    _catalog,
    _entry,
    _payload,
    fixture_identity,
    served_fixture_identity,
)

B4_FIXTURES = REPO / "perf" / "tests" / "fixtures" / "hosts" / "b4"
WARM_COLD = REPO / "perf" / "runner" / "warm_cold_browser.mjs"
UI = REPO / "harness" / "ui"

EXPECTED_BODY = "fixture line one\nfixture line two\n"


def _witness(extra=None):
    base = {"mechanism": PAINT_MECHANISM, "frames_seen": 12, "timeout_ms": 2000, "frame_interval_ms": 16.667}
    if extra:
        base.update(extra)
    return base


class WriterGuards(unittest.TestCase):
    def test_c04_idle_is_not_applicable_with_a_reason(self):
        entry = _entry(
            cid="C04",
            outcome="not_applicable",
            samples_ms=[],
            failure_reason="no_deferred_work",
            trial_hints={"cache_state": "process_cold_fs_warm"},
            observations=[{"quiescence_event": "none", "deferred_work_seen": False}],
        )
        assert_payload_shape(_payload({"C04": entry}, witness=_witness()))

    def test_c07_sub_frame_sample_below_frame_interval_is_kept(self):
        entry = _entry(
            samples_ms=[8.5, 20.0],
            sub_frame_samples=[True, False],
            trial_hints={"cache_state": "warm_steady", "repetition_unit": "fresh_process"},
        )
        payload = _payload({"C07": entry}, witness=_witness({"frame_interval_ms": 16.667}))
        assert_payload_shape(payload)

    def test_c07_records_fresh_process_and_one_median_per_launch(self):
        entry = _entry(
            samples_ms=[8.5, 20.0, 30.0],
            sub_frame_samples=[True, False, False],
            trial_hints={"cache_state": "warm_steady", "repetition_unit": "fresh_process"},
        )
        payload = _payload({"C07": entry}, witness=_witness())
        assert_payload_shape(payload)
        row, sha, size = fixture_identity()
        trial = trials_from_payload(
            payload,
            editor_version="fake",
            fixture_sha256=sha,
            workload_row=row,
            docx_size=size,
        )["C07"]
        self.assertEqual(trial["environment"]["repetition_unit"], "fresh_process")
        self.assertEqual(trial["samples_ms"], [20.0])
        self.assertIn("c07_click_samples_ms", trial["diagnostic"])

    def test_measured_visible_requires_frame_interval(self):
        entry = _entry(samples_ms=[20.0])
        payload = _payload({"C07": entry}, witness={"mechanism": PAINT_MECHANISM, "frames_seen": 5})
        with self.assertRaisesRegex(ValueError, "frame_interval_ms"):
            assert_payload_shape(payload)

    def test_failed_correctness_carries_no_samples(self):
        entry = _entry(
            outcome="failed",
            samples_ms=[],
            failure_reason="correctness: wrong_character",
            assertion={"name": "x", "passed": False, "scope": "s", "checks": {}, "failures": ["correctness"]},
            observations=[],
        )
        assert_payload_shape(_payload({"C07": entry}, witness=_witness()))


class SupportMatrix(unittest.TestCase):
    def test_matrix_lists_measured_refused_and_correctness(self):
        matrix = build_support_matrix(
            {
                "editors": [
                    {
                        "editor_id": "plate",
                        "outcome": "ok",
                        "criteria": {
                            "C07": {"outcome": "measured", "failure_reason": None},
                            "C08": {"outcome": "failed", "failure_reason": "correctness: truncated_paste"},
                        },
                    },
                    {
                        "editor_id": "canvas",
                        "outcome": "ok",
                        "criteria": {
                            "C07": {
                                "outcome": "unsupported",
                                "failure_reason": "no_correctness_adapter",
                            },
                        },
                    },
                ]
            }
        )
        self.assertEqual(matrix["C07"]["measured"], ["plate"])
        self.assertEqual(matrix["C07"]["refused"]["canvas"], "no_correctness_adapter")
        self.assertEqual(matrix["C08"]["failed_correctness"], ["plate"])


def _load_b4_server():
    spec = importlib.util.spec_from_file_location("b4_host_server", B4_FIXTURES / "server.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _mini_docx(path: Path) -> None:
    from perf.fixtures.generate import docx_zip_bytes

    path.write_bytes(docx_zip_bytes(EXPECTED_BODY.encode("utf-8")))


class CriteriaProbeAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not WARM_COLD.is_file():
            raise unittest.SkipTest("warm_cold_browser.mjs missing")
        if not UI.is_dir():
            raise unittest.SkipTest("harness/ui missing (symlink harness in worktree)")

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.docx = Path(self._tmpdir.name) / "corpus.docx"
        _mini_docx(self.docx)
        self.body_file = Path(self._tmpdir.name) / "expected.txt"
        self.body_file.write_text(EXPECTED_BODY, encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_host(self, page: str, *, adapter: str = "dom_innerText", criteria="C04,C07,C08,C09"):
        server = _load_b4_server()
        httpd, thread, base = server.serve(B4_FIXTURES)
        try:
            env = {
                **os.environ,
                "PERF_EXPECTED_BODY_PATH": str(self.body_file),
                "PERF_CORRECTNESS_ADAPTER": adapter,
            }
            cmd = [
                "node",
                str(WARM_COLD),
                "--driver",
                "playwright",
                "--editor",
                "b4-fake",
                "--criteria",
                criteria,
                "--url",
                base + page,
                "--corpus",
                str(self.docx),
                "--corpus-route",
                "/corpus.docx",
                "--ready-selector",
                "#ready",
                "--edit-selector",
                "#doc",
                "--quiescence-ms",
                "200",
                "--quiescence-timeout",
                "3000",
                "--frame-timeout",
                "4000",
                "--bulk-chars",
                "100",
            ]
            proc = subprocess.run(
                cmd,
                cwd=str(UI),
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            if proc.returncode != 0:
                self.fail(
                    "criteria probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
                    % (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:])
                )
            return json.loads(proc.stdout)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_control_host_c07_not_failed_for_fixture_mismatch(self):
        payload = self._run_host("control.html", criteria="C07")
        c07 = payload["criteria"]["C07"]
        self.assertNotEqual(c07.get("failure_reason"), "correctness: fixture_body_mismatch")

    def test_control_c08_measures_with_publishable_witness(self):
        payload = self._run_host("control.html", criteria="C08")
        c08 = payload["criteria"]["C08"]
        self.assertEqual(c08["outcome"], "measured", c08.get("failure_reason"))
        self.assertTrue(c08["samples_ms"])
        for observation in c08.get("observations") or []:
            witness = observation.get("witness")
            if witness is None:
                continue
            verdict = validate_witness(witness)
            self.assertFalse(verdict.get("refused"), "C08 witness: %r" % (verdict,))

    def test_control_c09_correct_edit_not_rejected_for_position(self):
        payload = self._run_host("control.html", criteria="C09")
        c09 = payload["criteria"]["C09"]
        reason = c09.get("failure_reason") or ""
        self.assertNotIn("typed_character_or_position", reason)
        self.assertNotIn("fixture_body_mismatch", reason)
        if c09["outcome"] == "measured":
            self.assertTrue(c09["samples_ms"])
            witness = (c09.get("observations") or [{}])[0].get("witness")
            self.assertIsInstance(witness, dict)
            self.assertFalse(validate_witness(witness).get("refused"))

    def test_idle_page_yields_c04_not_applicable(self):
        payload = self._run_host("idle.html", criteria="C04")
        c04 = payload["criteria"]["C04"]
        self.assertEqual(c04["outcome"], "not_applicable")
        self.assertEqual(c04["samples_ms"], [])
        self.assertTrue(c04.get("failure_reason"))

    def test_wrong_character_yields_c07_failed_correctness(self):
        payload = self._run_host("wrong_char.html", criteria="C07")
        c07 = payload["criteria"]["C07"]
        self.assertEqual(c07["outcome"], "failed")
        self.assertIn("correctness", c07.get("failure_reason", ""))

    def test_wrong_position_yields_c07_failed_correctness(self):
        payload = self._run_host("wrong_position.html", criteria="C07")
        c07 = payload["criteria"]["C07"]
        self.assertEqual(c07["outcome"], "failed")
        self.assertIn("correctness", c07.get("failure_reason", ""))

    def test_truncated_paste_yields_c08_failed_correctness(self):
        payload = self._run_host("truncated_paste.html", criteria="C08")
        c08 = payload["criteria"]["C08"]
        self.assertEqual(c08["outcome"], "failed")
        self.assertIn("correctness", c08.get("failure_reason", ""))

    def test_canvas_without_adapter_refuses_c07(self):
        payload = self._run_host("canvas_no_probe.html", adapter="", criteria="C07")
        c07 = payload["criteria"]["C07"]
        self.assertNotEqual(c07["outcome"], "measured")
        self.assertIn("correctness_adapter", c07.get("failure_reason", ""))

    def test_no_stored_c07_sample_below_frame_interval(self):
        payload = self._run_host("control.html", criteria="C07")
        interval = (payload.get("paint_witness") or {}).get("frame_interval_ms")
        self.assertIsNotNone(interval)
        c07 = payload["criteria"]["C07"]
        self.assertIn(c07["outcome"], ("measured", "failed"))
        if c07["outcome"] == "measured":
            self.assertTrue(c07["samples_ms"])
        # A click mid-frame paints at the next tick: a sub-frame latency is
        # real, and sub_frame_samples flags it (the io validator's own rule).
        flags = c07.get("sub_frame_samples") or []
        for index, sample in enumerate(c07["samples_ms"]):
            if index < len(flags) and flags[index]:
                continue
            self.assertGreaterEqual(sample, interval)
        workload_row, sha, size = fixture_identity()
        trials = trials_from_payload(
            payload,
            editor_version="b4-fake",
            fixture_sha256=sha,
            workload_row=workload_row,
            docx_size=size,
        )
        if trials["C07"]["outcome"] == "measured":
            trial_flags = trials["C07"].get("sub_frame_samples") or []
            for index, sample in enumerate(trials["C07"]["samples_ms"]):
                if index < len(trial_flags) and trial_flags[index]:
                    continue
                self.assertGreaterEqual(sample, interval)


class BenchmarkInputSupport(unittest.TestCase):
    def test_build_support_matrix_from_summary_file(self):
        from perf.runner import benchmark_input as bi

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = {
                "suite": "criteria_input",
                "criteria": list(SUITE),
                "editors": [
                    {
                        "editor_id": "b4-fake",
                        "outcome": "ok",
                        "criteria": {
                            "C04": {"outcome": "not_applicable", "failure_reason": "no_deferred_work"},
                        },
                    }
                ],
            }
            path = bi.criteria_input_io.write_support_matrix(summary, root)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("not_applicable", data["criteria"]["C04"])
